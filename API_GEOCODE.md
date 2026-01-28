# Reverse Geocoding API – Frontend Usage

Reverse geocoding fills **location_name** (and related fields) from **location_lat** / **location_lng** using Nominatim. Submissions need `location_lat` and `location_lng` (e.g. from `start-geopoint` or `gps_location` in Kobo).

---

## 1. Trigger geocoding: `POST /api/submissions/geocode-pending`

Runs reverse geocoding on submissions that have GPS but are missing `location_name`, or (with `validate_only=true`) checks form vs GPS for all with coordinates.

| | |
|--|--|
| **URL** | `POST /api/submissions/geocode-pending` |
| **Auth** | `Authorization: Bearer <access_token>` (admin) |

### Query parameters

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `form_id` | int | — | Limit to one form. Omit to process all forms. |
| `limit` | int | `50` | Max submissions to process per request. (Nominatim ~1 req/s; 50 ≈ 1 min.) |
| `validate_only` | bool | `false` | `false`: fill `location_name` and set `gps_consistent`. `true`: only set `gps_resolved_*` and `gps_consistent` (for form vs GPS checks), do **not** change `location_name`. |

### Request examples

**Geocode one form (fill `location_name` for up to 100 pending):**
```http
POST /api/submissions/geocode-pending?form_id=1&limit=100
Authorization: Bearer <token>
```
*(Empty body; all parameters in query.)*

**Geocode all forms, default limit:**
```http
POST /api/submissions/geocode-pending
Authorization: Bearer <token>
```

**Validate only (form vs GPS; do not change `location_name`):**
```http
POST /api/submissions/geocode-pending?form_id=1&validate_only=true&limit=200
Authorization: Bearer <token>
```

### Response (200)

```json
{
  "updated": 12,
  "processed": 50,
  "message": "Geocoded 12 of 50 pending."
}
```

| Field | Meaning |
|-------|---------|
| `updated` | Submissions whose `location_name` or `cleaned_data` (e.g. `gps_consistent`) was changed. |
| `processed` | Submissions that had GPS and were considered (up to `limit`). |
| `message` | Summary string. |

### Example (fetch + JS)

```javascript
// Geocode up to 100 pending for form 1
const res = await fetch(
  `${API_BASE}/api/submissions/geocode-pending?form_id=1&limit=100`,
  {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${token}` },
  }
);
const data = await res.json();
// { updated: 12, processed: 50, message: "Geocoded 12 of 50 pending." }
```

### Polling until “no more pending”

If you want to process all pending for a form, call in a loop until `processed === 0` or `updated === 0` (depending on whether you care about `validate_only`):

```javascript
async function geocodeAllPending(formId, limit = 50) {
  let totalUpdated = 0;
  while (true) {
    const res = await fetch(
      `${API_BASE}/api/submissions/geocode-pending?form_id=${formId}&limit=${limit}`,
      { method: 'POST', headers: { 'Authorization': `Bearer ${token}` } }
    );
    const { updated, processed } = await res.json();
    totalUpdated += updated;
    if (processed === 0) break;
  }
  return totalUpdated;
}
```

---

## 2. Submission fields set by geocoding

After geocoding, these fields are set or updated. Use them in submission detail views, tables, or filters.

### Top-level (e.g. `GET /api/forms/{form_id}/submissions`, `GET /api/submissions/{id}`)

| Field | Type | Description |
|-------|------|-------------|
| `location_lat` | float \| null | From Kobo (e.g. start-geopoint). |
| `location_lng` | float \| null | From Kobo. |
| `location_name` | string \| null | **Filled by geocoding** when missing: e.g. `"Village, Province"` or province only. If form has province/district, those can be used first; GPS is fallback. |
| `province` | string \| null | From form (user input). |
| `district` | string \| null | From form (user input). |

### Inside `submission_data` / `cleaned_data`

These live in the `submission_data` (or `cleaned_data`) dict returned by the API:

| Key | Type | Description |
|-----|------|-------------|
| `gps_resolved_province` | string | Province from coordinates (Nominatim). |
| `gps_resolved_location` | string | More detailed place, e.g. `"Village, Province"`. |
| `gps_consistent` | boolean | `true` if form province matches `gps_resolved_province` (or both empty); `false` if they disagree. |
| `survey_location_warning` | string \| null | Set when `gps_consistent === false`, e.g. *"Form province (X) does not match GPS (Y). Verify survey location."* |

### Example submission (after geocoding)

```json
{
  "id": 42,
  "form_id": 1,
  "kobo_submission_id": "abc123",
  "submitted_at": "2025-01-15T10:30:00",
  "location_lat": 36.75,
  "location_lng": 68.11,
  "location_name": "Sholgara, Balkh",
  "province": "Balkh",
  "district": "Sholgara",
  "submission_data": {
    "gps_resolved_province": "Balkh",
    "gps_resolved_location": "Sholgara, Balkh",
    "gps_consistent": true
  }
}
```

### Example with mismatch (form vs GPS)

```json
{
  "id": 43,
  "location_lat": 34.52,
  "location_lng": 69.18,
  "location_name": "Sholgara, Balkh",
  "province": "Balkh",
  "district": "Sholgara",
  "submission_data": {
    "gps_resolved_province": "Kabul",
    "gps_resolved_location": "Kabul",
    "gps_consistent": false,
    "survey_location_warning": "Form province (Balkh) does not match GPS (Kabul). Verify survey location."
  }
}
```

---

## 3. When geocoding runs automatically

- **After sync:** Each sync (form or “all”) runs 2 passes of `geocode_pending_submissions(limit=500)` in the background. No extra call from the frontend is required.
- **After webhook:** Geocoding runs in a background thread (limit 50) for the synced form.

You can still call **`POST /api/submissions/geocode-pending`** after a sync to process more, or to run `validate_only=true` for form vs GPS checks.

---

## 4. Frontend usage summary

| Action | API | Payload / query |
|--------|-----|------------------|
| Geocode one form | `POST /api/submissions/geocode-pending?form_id=1&limit=100` | No body; query only. |
| Geocode all forms | `POST /api/submissions/geocode-pending?limit=50` | No body. |
| Validate form vs GPS only | `POST /api/submissions/geocode-pending?form_id=1&validate_only=true&limit=200` | No body. |

**Response (all):**
```json
{ "updated": 12, "processed": 50, "message": "Geocoded 12 of 50 pending." }
```

**Display:** Use `location_name` for place; use `submission_data.gps_consistent` and `submission_data.survey_location_warning` to show mismatches between form location and GPS.
