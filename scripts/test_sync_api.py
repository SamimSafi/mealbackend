#!/usr/bin/env python3
"""
Test sync API: form_id=1 (works) vs another form (form_id=2 etc, often does not work on hosted).

Login API:
  POST {API_BASE}/api/auth/login
  Body: {"username": "admin", "password": "admin123"}

Env:
  API_BASE    (default: https://samimsafi.pythonanywhere.com)
  API_USER    (default: admin)
  API_PASS    (default: admin123)
  FORM_ID_OTHER (default: 2) – form id to test as "other form"

Example (override if needed):
  set API_BASE=https://samimsafi.pythonanywhere.com
  set API_USER=admin
  set API_PASS=admin123
  set FORM_ID_OTHER=2
  python scripts/test_sync_api.py
"""
import os
import sys
import time

import requests

API_BASE = os.getenv("API_BASE", "https://samimsafi.pythonanywhere.com").rstrip("/")
API_USER = os.getenv("API_USER", "admin")
API_PASS = os.getenv("API_PASS", "admin123")
FORM_ID_OTHER = int(os.getenv("FORM_ID_OTHER", "2"))
POLL_INTERVAL = 2
MAX_WAIT = 180  # 3 min per sync


def login() -> str:
    r = requests.post(f"{API_BASE}/api/auth/login", json={"username": API_USER, "password": API_PASS}, timeout=30)
    r.raise_for_status()
    return r.json()["access_token"]


def run_sync(token: str, form_id: int | None, timeout: int = 60) -> dict:
    payload = {"sync_type": "incremental"}
    if form_id is not None:
        payload["form_id"] = form_id
    r = requests.post(
        f"{API_BASE}/api/sync",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
        timeout=timeout,
    )
    r.raise_for_status()
    return r.json()


def get_progress(token: str, sync_id: int) -> dict:
    r = requests.get(
        f"{API_BASE}/api/sync/{sync_id}/progress",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def poll_until_done(token: str, sync_id: int, max_wait: int, label: str) -> bool:
    start = time.time()
    last_status = None
    while (time.time() - start) < max_wait:
        p = get_progress(token, sync_id)
        s = p.get("status")
        msg = p.get("message") or s
        if s != last_status or p.get("progress_percentage", 0) == 100:
            print(f"  [{label}] {s} | {p.get('progress_percentage', 0):.0f}% | {msg}")
            last_status = s
        if s in ("success", "error"):
            em = p.get("error_message") or ""
            print(f"  [{label}] done: {s}" + (f" – {em}" if em else ""))
            return s == "success"
        time.sleep(POLL_INTERVAL)
    print(f"  [{label}] TIMEOUT after {max_wait}s (status={last_status})")
    return False


def main():
    print(f"Base: {API_BASE}")
    print(f"Other form id: {FORM_ID_OTHER}\n")

    try:
        token = login()
        print("Login OK\n")
    except Exception as e:
        print(f"Login failed: {e}")
        sys.exit(1)

    # 1) form_id=1 (known to work)
    print("1) POST /api/sync { \"sync_type\": \"incremental\", \"form_id\": 1 }")
    try:
        res = run_sync(token, form_id=1)
        sid = res.get("id")
        print(f"   sync_log id={sid}, status={res.get('status')}\n")
        ok1 = poll_until_done(token, sid, MAX_WAIT, "form_id=1")
    except Exception as e:
        print(f"   Error: {e}\n")
        ok1 = False

    # 2) other form (form_id=2 or FORM_ID_OTHER) – often hangs on hosted
    print(f"\n2) POST /api/sync {{ \"sync_type\": \"incremental\", \"form_id\": {FORM_ID_OTHER} }}")
    try:
        res = run_sync(token, form_id=FORM_ID_OTHER)
        sid = res.get("id")
        print(f"   sync_log id={sid}, status={res.get('status')}\n")
        ok2 = poll_until_done(token, sid, MAX_WAIT, f"form_id={FORM_ID_OTHER}")
        if not ok2:
            print(f"   -> If form_id={FORM_ID_OTHER} stays 'running' or times out: other forms may have more data and hit PythonAnywhere's ~5 min worker limit, or 'Form not found' if that form does not exist.")
    except Exception as e:
        print(f"   Error: {e}")
        if hasattr(e, "response") and e.response is not None and getattr(e.response, "status_code", None) == 404:
            print("   -> Form not found. Ensure FORM_ID_OTHER exists (e.g. from GET /api/forms).")
        elif "timed out" in str(e).lower() or "timeout" in str(e).lower():
            print("   -> POST /api/sync timed out. Server may be busy or form 2 triggers slow work before the response is sent.")
        print()
        ok2 = False

    print("\nDone.")
    print("Summary: form_id=1 ->", "OK" if ok1 else "FAIL")
    print(f"         form_id={FORM_ID_OTHER} ->", "OK" if ok2 else "FAIL")


if __name__ == "__main__":
    main()
