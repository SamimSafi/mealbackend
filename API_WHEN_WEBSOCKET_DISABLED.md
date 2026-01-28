# API Usage When WebSockets Are Disabled

Use these HTTP APIs when `ENABLE_WEBSOCKETS=0` (e.g. PythonAnywhere free). All require `Authorization: Bearer <token>` unless noted.

---

## 1. Start a sync

**`POST /api/sync`** (admin)

- Body: `{ "form_id": 123 | null, "sync_type": "incremental" | "full" }`  
  - `form_id`: optional; omit to sync all forms.
- Response: `{ "id": 42, "status": "running", "form_id": 123, "sync_type": "incremental", ... }`
- Use `id` as `sync_id` for progress below.

---

## 2. Sync progress (choose one)

### Option A: Polling

**`GET /api/sync/{sync_id}/progress`**

- Response (JSON):
  - `status`: `"running"` | `"success"` | `"error"`
  - `progress_percentage`: 0–100
  - `current_form_index`, `total_forms`, `current_form_title`
  - `current_submission_index`, `total_submissions`
  - `records_added`, `records_updated`, `records_processed`
  - `message`: short human-readable status
  - `completed_at`, `error_message` when done
- Poll every 1–2 seconds while `status === "running"`.

### Option B: Server-Sent Events (SSE)

**`GET /api/sync/{sync_id}/stream`**

- When **ENABLE_WEBSOCKETS=0** (e.g. PythonAnywhere free): returns **409** `{"code": "SSE_DISABLED", "message": "Use GET /api/sync/{id}/progress"}` immediately—no stream, no long pending. Frontend should use polling.
- Auth: `Authorization: Bearer <token>` or `?token=<token>` (EventSource cannot set headers).
- `Accept: text/event-stream`
- Events: `data: {"sync_id":...,"status":...,"progress_percentage":...,...}\n\n`
- Stops when `status` is `"success"` or `"error"`.
- JS: `new EventSource('/api/sync/' + syncId + '/stream?token=' + token)` or `fetch` + `ReadableStream`.

**If SSE stays “pending” or hangs on your host** (strict timeouts, nginx, PythonAnywhere, etc.): use **polling** (`GET /api/sync/{id}/progress` every 1–2 s) instead; it works everywhere. **PythonAnywhere:** you will get **504 Gateway Time-out** after ~10–12 minutes; the gateway closes long-running requests. **Use polling** on PythonAnywhere (`GET /api/sync/{id}/progress` every 1–2 s) so long syncs work.

**Why SSE can fail when hosted:** (1) **504 / gateway timeout** — e.g. PythonAnywhere closes the connection after ~10–12 min even with keepalives. (2) **Auth and DB before first byte** — slow DB delays the first chunk. (3) **Proxy buffering** — `X-Accel-Buffering: no` helps nginx only. (4) **Single worker** — `/stream` can wait if the worker is busy.

---

## 3. After sync finishes

- When `status === "success"` (or `"error"`), stop polling/close SSE.
- **Form data:** Refetch what you show, e.g.:
  - `GET /api/forms/{form_id}`
  - `GET /api/forms/{form_id}/submissions`
  - `GET /api/forms/{form_id}/indicators`
- There is no HTTP push for “form updated”; refetch after sync completes.

---

## 4. Sync history

**`GET /api/sync/logs`**

- Returns list of sync logs (including `id`, `status`, `form_id`, `records_added`, `started_at`, `completed_at`, etc.).

---

## Quick flow

1. `POST /api/sync` with `{ "form_id": null, "sync_type": "incremental" }` → get `id`.
2. **Poll** `GET /api/sync/{id}/progress?token=<token>` every 1–2 s until `status` is `"success"` or `"error"`. (On PythonAnywhere, use polling; avoid `/stream` or you will get 504 after ~10–12 min.)
3. On `"success"`, refetch `/api/forms`, `/api/forms/{form_id}/submissions`, etc.
