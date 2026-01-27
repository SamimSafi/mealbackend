#!/usr/bin/env python3
"""
Upload random data to Kobo forms (v2 /assets/{uid}/submissions/ or KC v1 fallback).

- Tries POST /api/v2/assets/{asset_uid}/submissions/ first; falls back to KC v1 if 404/405.
- Fetches form schema/choices from Kobo (no hardcoded field lists).
- select_one / select_multiple: choice names (not labels). geopoint: "lat lon alt acc".
- Repeats: arrays of objects. Retry on 429/5xx. Progress and per-form summary.

Dates: from January 1 (current year) to today. GPS: Afghanistan only (lat 29.4–38.5, lon 60.5–74.9).
Always sets start-geopoint (Afghanistan). Fills start/end and schema geopoint fields when present.

CLI: --token, --server, --asset-uids, --per-form 100 (and --forms, --delay, --dry-run).
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import random
import re
import time
import uuid
from datetime import date, datetime, timedelta
from typing import Any

import requests

# Load config for KOBO_API_URL and KOBO_API_TOKEN
try:
    from config import settings
except Exception:
    settings = None

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

KOBO_API_URL = os.getenv("KOBO_API_URL") or (getattr(settings, "KOBO_API_URL", None) or "https://kf.kobotoolbox.org/api/v2")
KOBO_API_TOKEN = os.getenv("KOBO_API_TOKEN") or (getattr(settings, "KOBO_API_TOKEN", None) or "")
KOBO_KC_URL = (os.getenv("KOBO_KC_URL") or "https://kc.kobotoolbox.org").rstrip("/")
KC_SUBMISSION_URL = f"{KOBO_KC_URL}/api/v1/submissions.json"
KOBO_KC_USERNAME = os.getenv("KOBO_KC_USERNAME", "")
KOBO_KC_PASSWORD = os.getenv("KOBO_KC_PASSWORD", "")

# ---------------------------------------------------------------------------
# KF client (list forms, get form schema)
# ---------------------------------------------------------------------------

def _kc_auth(token: str | None = None) -> tuple[Any, dict[str, str]]:
    """Return (auth, headers) for KC POST. Prefer Basic if KOBO_KC_USERNAME/PASSWORD set, else Token."""
    if KOBO_KC_USERNAME and KOBO_KC_PASSWORD:
        return (KOBO_KC_USERNAME, KOBO_KC_PASSWORD), {"Content-Type": "application/json"}
    return None, _headers(token)


def _headers(token: str | None = None) -> dict[str, str]:
    t = token or KOBO_API_TOKEN
    return {"Authorization": f"Token {t}", "Content-Type": "application/json"}


def get_forms(api_base: str | None = None, token: str | None = None) -> list[dict[str, Any]]:
    base = (api_base or KOBO_API_URL).rstrip("/")
    url = f"{base}/assets"
    r = requests.get(url, headers=_headers(token), params={"limit": 200}, timeout=60)
    r.raise_for_status()
    return r.json().get("results", [])


def get_form(uid: str, api_base: str | None = None, token: str | None = None) -> dict[str, Any] | None:
    base = (api_base or KOBO_API_URL).rstrip("/")
    url = f"{base}/assets/{uid}"
    r = requests.get(url, headers=_headers(token), timeout=60)
    if r.status_code != 200:
        return None
    return r.json()


def get_deployment_uuid(asset: dict[str, Any], uid: str, api_base: str | None = None, token: str | None = None) -> str | None:
    dep = asset.get("deployment__uuid")
    if dep:
        return dep
    base = (api_base or KOBO_API_URL).rstrip("/")
    url = f"{base}/assets/{uid}/deployment/"
    try:
        r = requests.get(url, headers=_headers(token), timeout=30)
        if r.status_code == 200:
            d = r.json()
            return d.get("uuid") or d.get("identifier") or None
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Schema: survey + choices -> list of data fields
# ---------------------------------------------------------------------------

def _parse_choice_filter(expr: str) -> str | None:
    m = re.search(r"\$\{(\w+)\}", expr or "")
    return m.group(1) if m else None


def _is_relevant(relevant: str | None, values: dict[str, Any], name_to_path: dict[str, str]) -> bool:
    if not relevant or not relevant.strip():
        return True
    for ref in re.findall(r"\$\{(\w+)\}", relevant):
        path = name_to_path.get(ref)
        if path is None:
            continue
        val = str(values.get(path, "") or "").strip()
        # Common: "${x} = 'yes'", "${x} = 'no'"
        if "= 'yes'" in relevant or "= 'yes' " in relevant:
            return val == "yes"
        if "= 'no'" in relevant or "= 'no' " in relevant:
            return val == "no"
        if "!= 'yes'" in relevant:
            return val != "yes"
    return True


def _build_choice_map(content: dict) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for c in content.get("choices") or []:
        ln = c.get("list_name") or c.get("name")
        if not ln:
            continue
        if ln not in out:
            out[ln] = []
        out[ln].append(dict(c))
    return out


def _build_fields_and_names(
    survey: list[dict], choice_map: dict[str, list[dict]]
) -> tuple[list[dict], dict[str, str], dict[str, list[dict]], dict[str, str | None]]:
    name_to_path: dict[str, str] = {}
    fields: list[dict] = []
    stack: list[str] = []
    repeat_stack: list[str] = []
    repeat_groups: dict[str, list[dict]] = {}
    repeat_parent: dict[str, str | None] = {}

    SKIP_TYPES = {"end_group", "begin_group", "calculate", "note", "acknowledge", "hidden", "trigger", "image", "audio", "video", "file"}

    for row in survey or []:
        typ = (row.get("type") or "").strip()
        name = (row.get("name") or "").strip()

        if typ == "begin_repeat" and name:
            repeat_parent[name] = repeat_stack[-1] if repeat_stack else None
            repeat_stack.append(name)
            repeat_groups[name] = []
            continue
        if typ == "end_repeat":
            if repeat_stack:
                repeat_stack.pop()
            continue
        if typ == "begin_group" and name:
            stack.append(name)
            continue
        if typ == "end_group":
            if stack:
                stack.pop()
            continue
        if typ in SKIP_TYPES or not name:
            continue

        list_name = row.get("select_from_list_name") or row.get("choice")
        choice_filter = row.get("choice_filter") or ""
        relevant = row.get("relevant") or ""

        if repeat_stack:
            repeat_groups[repeat_stack[-1]].append({
                "name": name, "type": typ, "select_from_list_name": list_name,
                "choice_filter": choice_filter, "relevant": relevant,
            })
            name_to_path[name] = name
            continue

        path = "/".join(stack + [name]) if stack else name
        name_to_path[name] = path
        fields.append({
            "path": path, "name": name, "type": typ, "select_from_list_name": list_name,
            "choice_filter": choice_filter, "relevant": relevant, "required": bool(row.get("required")),
        })
    return fields, name_to_path, repeat_groups, repeat_parent


def _filter_choices(choices: list[dict], choice_filter: str, values: dict[str, Any], name_to_path: dict[str, str]) -> list[dict]:
    if not choice_filter:
        return choices
    ref = _parse_choice_filter(choice_filter)
    if not ref:
        return choices
    path = name_to_path.get(ref)
    if path is None:
        return choices
    want = values.get(path)
    # e.g. choice_filter "province=${province}" and choice has "province": "p1"
    filtered = [c for c in choices if c.get(ref) == want]
    return filtered if filtered else choices


# ---------------------------------------------------------------------------
# Random value generators
# ---------------------------------------------------------------------------

def _rand_text(seed: int, field_name: str, max_len: int = 80) -> str:
    rng = random.Random(seed)
    words = [
        "Alpha", "Beta", "Gamma", "Delta", "East", "West", "North", "South",
        "Village", "District", "Center", "Remote", "Urban", "Rural", "Site", "Camp",
        "Household", "Family", "Member", "Beneficiary", "Respondent", "Head",
    ]
    n = rng.randint(2, 5)
    return " ".join(rng.choices(words, k=n))[:max_len]


def _rand_int(seed: int, field_name: str, lo: int = 0, hi: int = 100) -> int:
    rng = random.Random(seed)
    if "age" in field_name.lower():
        return rng.randint(0, 99)
    if "hh_size" in field_name.lower() or "size" in field_name.lower() or "household" in field_name.lower():
        return rng.randint(1, 15)
    return rng.randint(lo, hi)


def _rand_decimal(seed: int, lo: float = 0.0, hi: float = 1000.0, decimals: int = 2) -> str:
    rng = random.Random(seed)
    v = rng.uniform(lo, hi)
    return f"{round(v, decimals)}"


# Afghanistan bounding box (lat 29.38–38.49 N, lon 60.52–74.89 E). Slightly conservative.
AFG_LAT_MIN, AFG_LAT_MAX = 29.4, 38.5
AFG_LON_MIN, AFG_LON_MAX = 60.5, 74.9


def _date_jan1_to_today(seed: int) -> date:
    """Random date from January 1 (current year) to today."""
    rng = random.Random(seed)
    y = date.today().year
    start = date(y, 1, 1)
    end = date.today()
    if end < start:
        return start
    days = (end - start).days
    return start + timedelta(days=rng.randint(0, days))


def _datetime_jan1_to_today(seed: int) -> datetime:
    """Random datetime from January 1 (current year) to today."""
    rng = random.Random(seed)
    d = _date_jan1_to_today(seed)
    h, m, s = rng.randint(6, 20), rng.randint(0, 59), rng.randint(0, 59)
    return datetime(d.year, d.month, d.day, h, m, s)


def _rand_date(seed: int) -> str:
    """Date from Jan 1 (current year) to today."""
    return _date_jan1_to_today(seed).isoformat()


def _rand_datetime(seed: int) -> str:
    """Datetime from Jan 1 (current year) to today."""
    return _datetime_jan1_to_today(seed).strftime("%Y-%m-%dT%H:%M:%S")


def _rand_geopoint(seed: int) -> str:
    """Geopoint in Afghanistan: 'lat lon alt acc' (Kobo format)."""
    rng = random.Random(seed)
    lat = rng.uniform(AFG_LAT_MIN, AFG_LAT_MAX)
    lon = rng.uniform(AFG_LON_MIN, AFG_LON_MAX)
    alt = rng.uniform(200, 3500)
    acc = rng.uniform(2, 25)
    return f"{lat} {lon} {alt} {acc}"


def _rand_select_one(choices: list[dict], seed: int) -> str | None:
    if not choices:
        return None
    rng = random.Random(seed)
    c = rng.choice(choices)
    return c.get("name")


def _rand_select_multiple(choices: list[dict], seed: int, max_select: int = 3) -> str | None:
    if not choices:
        return None
    rng = random.Random(seed)
    k = min(rng.randint(0, max_select), len(choices))
    if k == 0:
        return None
    sel = rng.sample(choices, k)
    return " ".join(c.get("name") or "" for c in sel if c.get("name"))


# ---------------------------------------------------------------------------
# Build one random submission (flat dict path -> value)
# ---------------------------------------------------------------------------

def _build_repeat_array(
    repeat_name: str,
    repeat_groups: dict[str, list[dict]],
    repeat_parent: dict[str, str | None],
    choice_map: dict[str, list[dict]],
    values_outer: dict[str, Any],
    name_to_path: dict[str, str],
    base_seed: int,
) -> list[dict[str, Any]]:
    rfields = repeat_groups.get(repeat_name, [])
    children = [k for k, p in repeat_parent.items() if p == repeat_name]
    rng = random.Random(base_seed)
    n = max(1, rng.randint(1, 3))
    arr: list[dict[str, Any]] = []
    for i in range(n):
        inst: dict[str, Any] = {}
        for c in children:
            inst[c] = _build_repeat_array(c, repeat_groups, repeat_parent, choice_map, {**values_outer, **inst}, name_to_path, base_seed + (i + 1) * 10007)
        for j, rf in enumerate(rfields):
            values_ctx = {**values_outer, **inst}
            if not _is_relevant(rf.get("relevant"), values_ctx, name_to_path):
                continue
            seed = base_seed + i * 31 + j * 7
            typ = rf.get("type", "")
            list_name = rf.get("select_from_list_name")
            choice_filter = rf.get("choice_filter") or ""
            name = rf.get("name", "")
            if typ == "text":
                inst[name] = _rand_text(seed, name)
            elif typ == "integer":
                inst[name] = str(_rand_int(seed, name))
            elif typ in ("decimal", "float"):
                inst[name] = _rand_decimal(seed)
            elif typ == "date":
                inst[name] = _rand_date(seed)
            elif typ in ("datetime", "start"):
                inst[name] = _rand_datetime(seed)
            elif typ == "end":
                inst[name] = _rand_datetime(seed + 100)
            elif typ == "geopoint":
                inst[name] = _rand_geopoint(seed)
            elif typ == "select_one" and list_name:
                choices = _filter_choices(choice_map.get(list_name, []), choice_filter, values_ctx, name_to_path)
                v = _rand_select_one(choices, seed)
                if v is not None:
                    inst[name] = v
            elif typ == "select_multiple" and list_name:
                choices = _filter_choices(choice_map.get(list_name, []), choice_filter, values_ctx, name_to_path)
                v = _rand_select_multiple(choices, seed)
                if v:
                    inst[name] = v
            elif typ in ("barcode", "username"):
                inst[name] = f"rnd{seed % 100000}"
        arr.append(inst)
    return arr


def build_one_random_submission(
    fields: list[dict],
    choice_map: dict[str, list[dict]],
    name_to_path: dict[str, str],
    record_index: int,
    form_seed: int,
    repeat_groups: dict[str, list[dict]] | None = None,
    repeat_parent: dict[str, str | None] | None = None,
) -> dict[str, Any]:
    repeat_groups = repeat_groups or {}
    repeat_parent = repeat_parent or {}
    values: dict[str, Any] = {}
    base_seed = form_seed + record_index * 10007

    # One date/datetime and one Afghanistan geopoint per record (Jan 1 to today)
    record_date = _date_jan1_to_today(base_seed)
    record_dt = _datetime_jan1_to_today(base_seed + 1)
    record_end_dt = record_dt + timedelta(minutes=random.Random(base_seed + 2).randint(2, 10))
    record_geopoint = _rand_geopoint(base_seed + 199)

    for i, f in enumerate(fields):
        path = f["path"]
        typ = f["type"]
        list_name = f.get("select_from_list_name")
        choice_filter = f.get("choice_filter") or ""
        relevant = f.get("relevant") or ""

        if not _is_relevant(relevant, values, name_to_path):
            continue

        seed = base_seed + i * 31

        if typ == "text":
            values[path] = _rand_text(seed, f["name"])
        elif typ == "integer":
            values[path] = str(_rand_int(seed, f["name"]))
        elif typ == "decimal" or typ == "float":
            values[path] = _rand_decimal(seed)
        elif typ == "date":
            values[path] = record_date.isoformat()
        elif typ in ("datetime", "start"):
            values[path] = record_dt.strftime("%Y-%m-%dT%H:%M:%S")
        elif typ == "end":
            values[path] = record_end_dt.strftime("%Y-%m-%dT%H:%M:%S")
        elif typ == "geopoint":
            values[path] = record_geopoint
        elif typ == "select_one" and list_name:
            choices = choice_map.get(list_name, [])
            choices = _filter_choices(choices, choice_filter, values, name_to_path)
            val = _rand_select_one(choices, seed)
            if val is not None:
                values[path] = val
        elif typ == "select_multiple" and list_name:
            choices = choice_map.get(list_name, [])
            choices = _filter_choices(choices, choice_filter, values, name_to_path)
            val = _rand_select_multiple(choices, seed)
            if val:
                values[path] = val
        elif typ == "barcode" or typ == "username":
            values[path] = f"rnd{seed % 100000}"
        # else: skip other types (image, file, etc.)

    # Repeats as arrays (top-level only; nested built inside _build_repeat_array)
    for rname, rfields in repeat_groups.items():
        if repeat_parent.get(rname) is not None:
            continue
        values[rname] = _build_repeat_array(rname, repeat_groups, repeat_parent, choice_map, values, name_to_path, base_seed + 99)

    # start-geopoint: ODK/Kobo metadata (device GPS). Always set with Afghanistan point.
    values["start-geopoint"] = record_geopoint
    return values


# ---------------------------------------------------------------------------
# Convert flat path dict to nested submission (Kobo expects group/field)
# ---------------------------------------------------------------------------

def _nest_submission(flat: dict[str, Any]) -> dict[str, Any]:
    """Convert { 'info/province': 'p1', 'info/district': 'p1_d1' } to { 'info': { 'province': 'p1', 'district': 'p1_d1' } }."""
    out: dict[str, Any] = {}
    for key, value in flat.items():
        if value is None or value == "":
            continue
        parts = key.split("/")
        d = out
        for p in parts[:-1]:
            if p not in d:
                d[p] = {}
            d = d[p]
        d[parts[-1]] = value
    return out


# ---------------------------------------------------------------------------
# HTTP POST with retry on 429 / 5xx
# ---------------------------------------------------------------------------

def _post_with_retry(
    url: str, *, auth: Any = None, headers: dict[str, str], json: dict, timeout: int = 60, max_retries: int = 3
) -> requests.Response:
    for attempt in range(max_retries):
        try:
            r = requests.post(url, auth=auth, headers=headers, json=json, timeout=timeout)
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            time.sleep(2 ** attempt)
            continue
        if r.status_code in (404, 405, 400, 401, 403):
            return r
        if r.status_code == 429 or r.status_code >= 500:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
        return r
    return r


# ---------------------------------------------------------------------------
# V2 POST /api/v2/assets/{asset_uid}/submissions/ (if supported)
# ---------------------------------------------------------------------------

def _submit_v2(asset_uid: str, flat_values: dict[str, Any], dry_run: bool, api_base: str, token: str) -> bool:
    nested = _nest_submission(flat_values)
    body = {"meta": {"instanceID": f"uuid:{uuid.uuid4()}"}, **nested}
    url = f"{api_base.rstrip('/')}/assets/{asset_uid}/submissions/"
    if dry_run:
        logger.debug("  [DRY-RUN] would POST v2 %s", url)
        return True
    try:
        r = _post_with_retry(url, auth=None, headers=_headers(token), json=body, timeout=60)
        if r.status_code in (200, 201):
            return True
        if r.status_code in (404, 405):
            return False
        logger.warning("  v2 POST %s: %s", r.status_code, r.text[:200])
        return False
    except Exception as e:
        logger.warning("  v2 POST error: %s", e)
        return False


# ---------------------------------------------------------------------------
# KC v1 submit (fallback when v2 not available)
# ---------------------------------------------------------------------------

def _submit_kc(form_id: str, formhub_uuid: str, flat_values: dict[str, Any], dry_run: bool, token: str | None = None) -> bool:
    nested = _nest_submission(flat_values)
    payload = {
        "id": form_id,
        "submission": {
            "formhub": {"uuid": formhub_uuid},
            "meta": {"instanceID": f"uuid:{uuid.uuid4()}"},
            **nested,
        },
    }
    if dry_run:
        logger.info("  [DRY-RUN] would POST KC %s", json.dumps(payload, indent=2)[:500] + "...")
        return True
    auth, headers = _kc_auth(token)
    try:
        r = _post_with_retry(KC_SUBMISSION_URL, auth=auth, headers=headers, json=payload, timeout=60)
        if r.status_code in (200, 201):
            return True
        logger.warning("  KC POST %s: %s", r.status_code, r.text[:200])
        return False
    except Exception as e:
        logger.warning("  KC POST error: %s", e)
        return False


def _submit(asset_uid: str, dep_uuid: str | None, flat: dict[str, Any], dry_run: bool, kf_base: str, token: str) -> bool:
    """Try v2 /assets/{uid}/submissions/ then KC v1. Uses retry on 429/5xx."""
    if dry_run:
        logger.info("  [DRY-RUN] would POST %s", list(flat.keys())[:5])
        return True
    if _submit_v2(asset_uid, flat, dry_run=False, api_base=kf_base, token=token):
        return True
    if dep_uuid and _submit_kc(asset_uid, dep_uuid, flat, dry_run=False, token=token):
        return True
    return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description="Upload random data to Kobo forms (v2 /assets/{uid}/submissions/ or KC v1)")
    ap.add_argument("--token", type=str, default=None, help="Kobo API token (overrides KOBO_API_TOKEN)")
    ap.add_argument("--server", type=str, default=None, help="Kobo KF server base (e.g. https://kf.kobotoolbox.org)")
    ap.add_argument("--asset-uids", type=str, default=None, help="Comma-separated asset UIDs (default: fetch first N forms)")
    ap.add_argument("--per-form", type=int, default=100, help="Submissions per form (default 100)")
    ap.add_argument("--records", dest="per_form", type=int, help="Alias for --per-form")
    ap.add_argument("--forms", type=int, default=16, help="Max forms when not using --asset-uids (default 16)")
    ap.add_argument("--delay", type=float, default=0.5, help="Seconds between submissions (default 0.5)")
    ap.add_argument("--dry-run", action="store_true", help="Do not POST, only log")
    args = ap.parse_args()

    token = args.token or KOBO_API_TOKEN
    if not token:
        logger.error("KOBO_API_TOKEN or --token is required.")
        raise SystemExit(1)

    # KF API base: --server or KOBO_API_URL or default
    raw = args.server or KOBO_API_URL or "https://kf.kobotoolbox.org"
    raw = raw.rstrip("/")
    if "/api/v2" not in raw:
        kf_base = f"{raw}/api/v2"
    else:
        kf_base = raw

    n_per_form = args.per_form

    # Build asset list: --asset-uids or get_forms
    if args.asset_uids:
        uids = [u.strip() for u in args.asset_uids.split(",") if u.strip()]
        to_process = []
        for uid in uids:
            full = get_form(uid, api_base=kf_base, token=token)
            if full:
                to_process.append({"uid": uid, "full": full, "title": full.get("name") or full.get("title") or uid})
            else:
                logger.warning("Asset %s not found, skipping.", uid)
    else:
        all_forms = get_forms(api_base=kf_base, token=token)
        survey_forms = [f for f in all_forms if (f.get("asset_type") or "survey") == "survey"]
        deployed = [f for f in survey_forms if f.get("has_deployment") or f.get("deployment__uuid")]
        to_process = (deployed or survey_forms)[: args.forms]
        to_process = [{"uid": f.get("uid") or f.get("id"), "full": None, "title": f.get("name") or f.get("title") or (f.get("uid") or "?")} for f in to_process if (f.get("uid") or f.get("id"))]

    logger.info("KF=%s | per-form=%d | forms=%d", kf_base, n_per_form, len(to_process))

    total_ok = 0
    total_fail = 0
    form_results: list[tuple[str, str, int, int]] = []

    for idx, item in enumerate(to_process):
        uid = item.get("uid")
        title = item.get("title") or uid or "?"
        full = item.get("full")
        if not full:
            full = get_form(uid, api_base=kf_base, token=token)
        if not full:
            logger.warning("Form %s (%s) could not be fetched, skipping.", uid, title)
            form_results.append((uid or "?", title, 0, 0))
            continue

        dep_uuid = full.get("deployment__uuid") or get_deployment_uuid(full, uid, api_base=kf_base, token=token)
        content = full.get("content") or {}
        survey = content.get("survey") or []
        choice_map = _build_choice_map(content)
        fields, name_to_path, repeat_groups, repeat_parent = _build_fields_and_names(survey, choice_map)

        if not fields and not repeat_groups:
            logger.warning("Form %s (%s) has no data fields, skipping.", uid, title)
            form_results.append((uid or "?", title, 0, 0))
            continue

        logger.info("Form %d/%d: %s (uid=%s) fields=%d repeats=%d", idx + 1, len(to_process), title, uid, len(fields), len(repeat_groups))

        ok, fail = 0, 0
        for r in range(n_per_form):
            flat = build_one_random_submission(fields, choice_map, name_to_path, r, idx * 1000 + r, repeat_groups=repeat_groups, repeat_parent=repeat_parent)
            ok_one = _submit(uid, dep_uuid, flat, args.dry_run, kf_base, token)
            if ok_one:
                ok += 1
            else:
                fail += 1
            if (r + 1) % 25 == 0:
                logger.info("  %s: %d/%d ok=%d fail=%d", uid, r + 1, n_per_form, ok, fail)
            if not args.dry_run and args.delay > 0:
                time.sleep(args.delay)

        total_ok += ok
        total_fail += fail
        form_results.append((uid or "?", title, ok, fail))
        logger.info("  %s done: ok=%d fail=%d", uid, ok, fail)

    # Final summary
    logger.info("=== Summary ===")
    for uid, title, o, f in form_results:
        logger.info("  %s | %s | ok=%d fail=%d", uid, (title or "")[:40], o, f)
    logger.info("Total: ok=%d fail=%d", total_ok, total_fail)


if __name__ == "__main__":
    main()
