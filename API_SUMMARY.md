# API Endpoints Summary

## ✅ **Working Endpoints**

### Authentication
- `POST /api/auth/login` - Login and get JWT token
- `POST /api/auth/register` - Register new user
- `GET /api/auth/me` - Get current user info

### Forms
- `GET /api/forms` - List all forms ✅
- `GET /api/forms/{form_id}` - Get form details ✅
- `GET /api/forms/{form_id}/schema` - Get form schema ✅
- `GET /api/forms/{form_id}/filter-fields` - Get available filter fields ✅
- `GET /api/forms/{form_id}/debug-schema` - Debug form schema structure ✅
- `GET /api/forms/{form_id}/indicators` - Get form indicators summary ✅
- `DELETE /api/forms/{form_id}/data` - Clear form data (admin only) ✅

### Submissions
- `GET /api/submissions` - List submissions (optional `form_id` query param) ✅
- `GET /api/submissions/{submission_id}` - Get submission details ✅
- `GET /form/{form_id}/submissions` - Public alias for form submissions ✅

### Chart Data (FIXED)
- `POST /api/forms/{form_id}/chart-data` - Get chart data with filters ✅ **FIXED**
  - Now uses `get_nested_field_value` for nested fields
  - Now uses `cleaned_data` first, then `submission_data`
  - Now converts codes to labels using schema maps
  - Supports: bar, pie, donut, line, stacked_bar, histogram, scatter

### Chart Statistics
- `POST /api/charts/box_plot` - Get box plot statistics ✅
  - Uses nested field extraction
  - Handles numeric fields with variations (beneficiary/hh_size, etc.)
- `POST /api/charts/bar_chart` - Get categorical bar chart ✅
  - Auto-detects group_by from filters
  - Converts codes to labels dynamically
  - Works for any field automatically

### Indicators
- `GET /api/indicators` - List indicators ✅
- `GET /api/indicators/{indicator_id}` - Get indicator details ✅
- `GET /form/{form_id}/indicators` - Public alias for form indicators ✅

### Dashboard
- `GET /api/dashboard/summary` - Get dashboard summary ✅
- `GET /api/dashboard/indicators` - Get indicator dashboard data ✅
- `GET /api/dashboard/accountability` - Get accountability/complaints dashboard ✅

### Sync (Admin only)
- `POST /api/sync` - Sync forms from Kobo ✅
- `GET /api/sync/logs` - Get sync logs ✅

### User Management (Admin only)
- `GET /api/users` - List users ✅
- `GET /api/users/{user_id}` - Get user details ✅
- `PUT /api/users/{user_id}` - Update user ✅
- `POST /api/users/{user_id}/permissions` - Add user permission ✅

### Webhooks
- `POST /api/webhooks/kobo` - Webhook endpoint for Kobo submissions ✅

### Data Loading
- `GET /api/data/load` - Load data by date ✅

---

## 🔧 **Recent Fixes**

### 1. Chart Data Endpoint (`/api/forms/{form_id}/chart-data`)
**Issue**: Returning empty data
**Fix**:
- ✅ Now uses `get_nested_field_value()` to handle nested fields like `info/province`
- ✅ Uses `cleaned_data` first (normalized), then falls back to `submission_data`
- ✅ Converts codes (p1, p2, p3) to labels (Kabul, Balkh, Jalalabad) using schema maps
- ✅ Handles empty filter arrays correctly (shows all data)

### 2. Bar Chart Endpoint (`/api/charts/bar_chart`)
**Issue**: Showing codes instead of labels
**Fix**:
- ✅ Implements Kobo best practices with schema maps
- ✅ Builds `question_map` and `choice_map` for efficient lookup
- ✅ Dynamic field matching (works for any field)
- ✅ Converts codes to labels automatically

### 3. Box Plot Endpoint (`/api/charts/box_plot`)
**Issue**: 400 Bad Request for numeric fields
**Fix**:
- ✅ Tries field name variations (hh_size → beneficiary/hh_size)
- ✅ Better error messages with available fields
- ✅ Handles nested field paths

---

## 📊 **API Usage Examples**

### Get Chart Data (Donut Chart)
```json
POST /api/forms/1/chart-data
{
    "chart_type": "donut",
    "dimension": "info/province",
    "filters": {
        "info/province": []  // Empty array = no filter, show all
    }
}
```

**Response**:
```json
{
    "form_id": 1,
    "chart_type": "donut",
    "dimension": "info/province",
    "data": [
        {"name": "Kabul", "value": 1},
        {"name": "Balkh", "value": 1},
        {"name": "Jalalabad", "value": 1}
    ],
    "total": 3
}
```

### Get Bar Chart with Labels
```json
POST /api/charts/bar_chart
{
    "form_id": 1,
    "filters": {
        "info/province": []
    }
}
```

**Response**:
```json
{
    "form_id": 1,
    "group_by": "info/province",
    "items": [
        {"category": "Kabul", "count": 1},
        {"category": "Balkh", "count": 1},
        {"category": "Jalalabad", "count": 1}
    ],
    "total_submissions": 3,
    "unique_values": 3,
    "field_label": "Province"
}
```

### Get Box Plot
```json
POST /api/charts/box_plot
{
    "form_id": 1,
    "column": "hh_size",  // Will try beneficiary/hh_size automatically
    "filters": {}
}
```

---

## 🎯 **Key Features**

1. **Dynamic Field Handling**: Works with any field name automatically
2. **Code to Label Conversion**: Automatically converts Kobo codes to human-readable labels
3. **Nested Field Support**: Handles nested paths like `info/province`, `beneficiary/hh_size`
4. **Schema Maps**: Efficient lookup using Kobo best practices
5. **Multiple Chart Types**: bar, pie, donut, line, stacked_bar, histogram, scatter

---

## ⚠️ **Important Notes**

1. **Empty Filter Arrays**: `"filters": {"field": []}` means "no filter" - shows all data
2. **Field Names**: Use exact field names from Kobo (e.g., `info/province`)
3. **Authentication**: Most endpoints require JWT token (except webhooks)
4. **Admin Endpoints**: Sync and user management require admin role

---

## 🐛 **Known Issues / To Test**

- [ ] Test with real Kobo data after re-sync
- [ ] Verify label conversion works for all field types
- [ ] Test with multiple forms
- [ ] Test edge cases (empty data, missing fields, etc.)

---

**Last Updated**: After implementing Kobo best practices and fixing chart-data endpoint

