#!/usr/bin/env python3
"""
Benchmark all chart and analysis endpoints for performance.

Usage:
  python scripts/benchmark_charts_analysis.py [--base-url http://localhost:8000] [--runs 2]

Environment:
  BENCHMARK_USER, BENCHMARK_PASS  - auth (default: admin, admin123)
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from dataclasses import dataclass, field
from typing import Any

try:
    import requests
except ImportError:
    print("Install: pip install requests")
    sys.exit(1)

# Defaults
DEFAULT_BASE = os.environ.get("BENCHMARK_BASE_URL", "http://localhost:8000")
DEFAULT_USER = os.environ.get("BENCHMARK_USER", "admin")
DEFAULT_PASS = os.environ.get("BENCHMARK_PASS", "admin123")


@dataclass
class Result:
    endpoint: str
    method: str
    status: int
    elapsed_ms: float
    error: str | None = None
    detail: str | None = None


@dataclass
class EndpointSummary:
    endpoint: str
    method: str
    runs: int
    ok: int
    fail: int
    min_ms: float
    max_ms: float
    avg_ms: float
    p95_ms: float | None
    last_status: int
    last_error: str | None = None


def login(base: str, user: str, password: str) -> str:
    r = requests.post(f"{base}/api/auth/login", json={"username": user, "password": password}, timeout=10)
    r.raise_for_status()
    return r.json()["access_token"]


def get_forms(base: str, token: str) -> list[dict]:
    r = requests.get(f"{base}/api/forms", headers={"Authorization": f"Bearer {token}"}, timeout=10)
    r.raise_for_status()
    return r.json()


def get_analysis_filters(base: str, token: str, form_id: int | str) -> dict:
    r = requests.get(
        f"{base}/api/analysis/filters",
        params={"form_id": str(form_id)},
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


def measure(
    method: str,
    url: str,
    *,
    headers: dict,
    params: dict | None = None,
    json: dict | None = None,
    timeout: int = 60,
) -> Result:
    t0 = time.perf_counter()
    try:
        if method == "GET":
            resp = requests.get(url, headers=headers, params=params, timeout=timeout)
        else:
            resp = requests.post(url, headers=headers, params=params, json=json, timeout=timeout)
        elapsed = (time.perf_counter() - t0) * 1000
        detail = None
        try:
            b = resp.json()
            if isinstance(b, dict) and "detail" in b:
                detail = str(b["detail"])[:200]
        except Exception:
            pass
        return Result(
            endpoint=url,
            method=method,
            status=resp.status_code,
            elapsed_ms=elapsed,
            detail=detail,
        )
    except Exception as e:
        elapsed = (time.perf_counter() - t0) * 1000
        return Result(endpoint=url, method=method, status=-1, elapsed_ms=elapsed, error=str(e)[:200])


def summarize_results(results: list[Result]) -> EndpointSummary:
    if not results:
        return EndpointSummary("", "", 0, 0, 0, 0, 0, 0, None, -1, None)
    ep = results[0].endpoint
    method = results[0].method
    ok = sum(1 for r in results if 200 <= r.status < 300)
    fail = len(results) - ok
    times = [r.elapsed_ms for r in results]
    p95 = None
    if len(times) >= 2:
        times_sorted = sorted(times)
        idx = max(0, int(len(times_sorted) * 0.95) - 1)
        p95 = times_sorted[idx]
    last = results[-1]
    return EndpointSummary(
        endpoint=ep,
        method=method,
        runs=len(results),
        ok=ok,
        fail=fail,
        min_ms=min(times),
        max_ms=max(times),
        avg_ms=statistics.mean(times),
        p95_ms=p95,
        last_status=last.status,
        last_error=last.error or (last.detail if last.status >= 400 else None),
    )


def run_benchmark(base: str, token: str, form_id: int, filters: dict, runs: int) -> list[Result]:
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    results: list[Result] = []

    cat = [c["name"] for c in filters.get("categorical_fields", [])]
    num = [n["name"] for n in filters.get("numeric_fields", [])]
    date_f = [d["name"] for d in filters.get("date_fields", [])]
    dr = filters.get("date_range", {}) or {}
    date_from = dr.get("min") or "2020-01-01"
    date_to = dr.get("max") or "2030-12-31"
    c1 = cat[0] if cat else "info/province"  # fallback; may 404
    c2 = cat[1] if len(cat) > 1 else c1
    n1 = num[0] if num else "age"
    d1 = date_f[0] if date_f else "start"  # often exists in Kobo

    # ---- Analysis ----
    for _ in range(runs):
        r = measure("GET", f"{base}/api/analysis/filters", params={"form_id": form_id}, headers=headers)
        r.endpoint = "GET /api/analysis/filters"
        results.append(r)

    for _ in range(runs):
        r = measure(
            "GET",
            f"{base}/api/analysis/report",
            params={"form_id": form_id, "row": c1, "column": c2},
            headers=headers,
        )
        r.endpoint = "GET /api/analysis/report"
        results.append(r)

    for _ in range(runs):
        r = measure(
            "GET",
            f"{base}/api/analysis/crosstab",
            params={"form_id": form_id, "row": c1, "column": c2},
            headers=headers,
        )
        r.endpoint = "GET /api/analysis/crosstab"
        results.append(r)

    for _ in range(runs):
        r = measure(
            "GET",
            f"{base}/api/analysis/cross-tabulation",
            params={"form_id": form_id, "row_field": c1, "column_field": c2},
            headers=headers,
        )
        r.endpoint = "GET /api/analysis/cross-tabulation"
        results.append(r)

    for _ in range(runs):
        r = measure(
            "GET",
            f"{base}/api/analysis/stacked-bar",
            params={"form_id": form_id, "x": c1, "stack": c2},
            headers=headers,
        )
        r.endpoint = "GET /api/analysis/stacked-bar"
        results.append(r)

    if num:
        for _ in range(runs):
            r = measure(
                "GET",
                f"{base}/api/analysis/numeric-summary",
                params={"form_id": form_id, "field": n1},
                headers=headers,
            )
            r.endpoint = "GET /api/analysis/numeric-summary"
            results.append(r)

        for _ in range(runs):
            r = measure(
                "GET",
                f"{base}/api/analysis/numeric-distribution",
                params={"form_id": form_id, "field": n1},
                headers=headers,
            )
            r.endpoint = "GET /api/analysis/numeric-distribution"
            results.append(r)

    if cat:
        for _ in range(runs):
            r = measure(
                "GET",
                f"{base}/api/analysis/ordinal-scale",
                params={"form_id": form_id, "field": c1},
                headers=headers,
            )
            r.endpoint = "GET /api/analysis/ordinal-scale"
            results.append(r)

        for _ in range(runs):
            r = measure(
                "GET",
                f"{base}/api/analysis/ordinal-trends",
                params={"form_id": form_id, "field": c1, "granularity": "month", "date_from": date_from, "date_to": date_to},
                headers=headers,
            )
            r.endpoint = "GET /api/analysis/ordinal-trends"
            results.append(r)

    for _ in range(runs):
        r = measure(
            "GET",
            f"{base}/api/analysis/time-series",
            params={"form_id": form_id, "date_from": date_from, "date_to": date_to, "group_by": "month"},
            headers=headers,
        )
        r.endpoint = "GET /api/analysis/time-series"
        results.append(r)

    if cat:
        for _ in range(runs):
            r = measure(
                "GET",
                f"{base}/api/analysis/multiselect",
                params={"form_id": form_id, "field": c1},
                headers=headers,
            )
            r.endpoint = "GET /api/analysis/multiselect"
            results.append(r)

    # ---- Charts (main.py) ----
    if num:
        for _ in range(runs):
            r = measure(
                "POST",
                f"{base}/api/charts/box_plot",
                json={"form_id": form_id, "column": n1, "filters": {}},
                headers=headers,
            )
            r.endpoint = "POST /api/charts/box_plot"
            results.append(r)

    if cat:
        for _ in range(runs):
            r = measure(
                "POST",
                f"{base}/api/charts/bar_chart",
                json={"form_id": form_id, "group_by": c1, "filters": {}},
                headers=headers,
            )
            r.endpoint = "POST /api/charts/bar_chart"
            results.append(r)

        for _ in range(runs):
            r = measure(
                "POST",
                f"{base}/api/charts/polar_area",
                json={"form_id": form_id, "field": c1, "filters": {}},
                headers=headers,
            )
            r.endpoint = "POST /api/charts/polar_area"
            results.append(r)

    # ---- Form chart-data ----
    for _ in range(runs):
        r = measure(
            "POST",
            f"{base}/api/forms/{form_id}/chart-data",
            json={"chart_type": "bar", "dimension": c1, "filters": {}},
            headers=headers,
        )
        r.endpoint = "POST /api/forms/{form_id}/chart-data (bar)"
        results.append(r)

    if num and len(num) > 1:
        for _ in range(runs):
            r = measure(
                "POST",
                f"{base}/api/forms/{form_id}/chart-data",
                json={"chart_type": "scatter", "dimension": num[0], "secondary_dimension": num[1], "filters": {}},
                headers=headers,
            )
            r.endpoint = "POST /api/forms/{form_id}/chart-data (scatter)"
            results.append(r)

    if date_f:
        for _ in range(runs):
            r = measure(
                "POST",
                f"{base}/api/forms/{form_id}/chart-data",
                json={"chart_type": "line", "dimension": n1 if num else c1, "time_dimension": d1, "filters": {}},
                headers=headers,
            )
            r.endpoint = "POST /api/forms/{form_id}/chart-data (line)"
            results.append(r)

    if num:
        for _ in range(runs):
            r = measure(
                "POST",
                f"{base}/api/forms/{form_id}/chart-data",
                json={"chart_type": "histogram", "dimension": n1, "bin_count": 10, "filters": {}},
                headers=headers,
            )
            r.endpoint = "POST /api/forms/{form_id}/chart-data (histogram)"
            results.append(r)

    # ---- Dashboard & reports ----
    for _ in range(runs):
        r = measure("GET", f"{base}/api/dashboard/summary", headers=headers)
        r.endpoint = "GET /api/dashboard/summary"
        results.append(r)

    for _ in range(runs):
        r = measure(
            "GET",
            f"{base}/api/reports/submissions/time-series",
            params={"form_id": form_id, "start": f"{date_from}T00:00:00", "end": f"{date_to}T23:59:59", "group_by": "day"},
            headers=headers,
        )
        r.endpoint = "GET /api/reports/submissions/time-series"
        results.append(r)

    return results


def main():
    ap = argparse.ArgumentParser(description="Benchmark chart and analysis endpoints")
    ap.add_argument("--base-url", default=DEFAULT_BASE, help="API base URL")
    ap.add_argument("--runs", type=int, default=2, help="Runs per endpoint")
    ap.add_argument("--user", default=DEFAULT_USER, help="Login user")
    ap.add_argument("--password", default=DEFAULT_PASS, help="Login password")
    ap.add_argument("--form-id", type=int, default=None, help="Form ID (default: first from /api/forms)")
    ap.add_argument("--json", action="store_true", help="Output JSON only")
    args = ap.parse_args()

    base = args.base_url.rstrip("/")

    if not args.json:
        print("Login...")
    token = login(base, args.user, args.password)

    if not args.json:
        print("Fetching forms...")
    forms = get_forms(base, token)
    if not forms:
        print("No forms. Sync data first.")
        sys.exit(1)
    form_id = args.form_id or forms[0]["id"]

    if not args.json:
        print(f"Fetching analysis filters for form_id={form_id}...")
    filters = get_analysis_filters(base, token, form_id)

    if not args.json:
        print(f"Running benchmark ({args.runs} runs per endpoint)...")
    raw = run_benchmark(base, token, form_id, filters, args.runs)

    # Group by endpoint
    by_ep: dict[str, list[Result]] = {}
    for r in raw:
        k = r.endpoint
        if k not in by_ep:
            by_ep[k] = []
        by_ep[k].append(r)

    summaries = [summarize_results(by_ep[k]) for k in sorted(by_ep.keys())]

    if args.json:
        out = {
            "form_id": form_id,
            "runs_per_endpoint": args.runs,
            "endpoints": [
                {
                    "endpoint": s.endpoint,
                    "method": s.method,
                    "runs": s.runs,
                    "ok": s.ok,
                    "fail": s.fail,
                    "min_ms": round(s.min_ms, 2),
                    "max_ms": round(s.max_ms, 2),
                    "avg_ms": round(s.avg_ms, 2),
                    "p95_ms": round(s.p95_ms, 2) if s.p95_ms is not None else None,
                    "last_status": s.last_status,
                    "last_error": s.last_error,
                }
                for s in summaries
            ],
        }
        print(json.dumps(out, indent=2))
        return

    # Human report
    print()
    print("=" * 90)
    print("Charts & Analysis Performance Report")
    print("=" * 90)
    print(f"Form ID: {form_id}  |  Runs per endpoint: {args.runs}  |  Base: {base}")
    print()

    total_ok = sum(s.ok for s in summaries)
    total_fail = sum(s.fail for s in summaries)
    print(f"Total: {total_ok} OK, {total_fail} failed")
    print()

    # Table
    fmt = "%-50s %6s %6s %8s %8s %8s %6s  %s"
    print(fmt % ("Endpoint", "Runs", "OK", "Min(ms)", "Avg(ms)", "Max(ms)", "P95", "Status/Error"))
    print("-" * 120)
    for s in summaries:
        p95 = f"{s.p95_ms:.0f}" if s.p95_ms is not None else "-"
        err = ""
        if s.fail:
            err = (s.last_error or str(s.last_status))[:40]
        print(fmt % (s.endpoint[:50], s.runs, s.ok, f"{s.min_ms:.0f}", f"{s.avg_ms:.0f}", f"{s.max_ms:.0f}", p95, err))

    # Slow endpoints (> 1s avg)
    slow = [s for s in summaries if s.avg_ms > 1000 and s.ok > 0]
    if slow:
        print()
        print("Slow (avg > 1s):")
        for s in slow:
            print(f"  - {s.endpoint}: avg={s.avg_ms:.0f} ms")

    # Failures
    failed = [s for s in summaries if s.fail > 0]
    if failed:
        print()
        print("Failures (last error):")
        for s in failed:
            print(f"  - {s.endpoint}: {s.last_error or s.last_status}")

    print()
    print("=" * 90)


if __name__ == "__main__":
    main()
