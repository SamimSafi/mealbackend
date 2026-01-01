# Box Plot API - 400 Bad Request Error Guide

## What Causes 400 Bad Request?

The `POST /api/charts/box_plot` endpoint returns **400 Bad Request** when it cannot find any numeric values for the specified column after applying filters.

### Error Location
- **Code:** Line 791-792 in `mealbackend/main.py`
- **Error Message:** `"No numeric data available for box plot"`

### When This Happens

The error occurs when the `values` list is empty, which happens if:

1. **Column doesn't exist** in the submission data
2. **Column exists but all values are null/empty** (`None`, `""`)
3. **Column exists but values are non-numeric** (e.g., text, "N/A", codes)
4. **Filters exclude all rows** that have numeric values in that column
5. **Form has no submissions** at all
6. **Column name is misspelled** or uses wrong case

---

## Correct Request Payload Examples

### ✅ Example 1: Basic Request (No Filters)
```json
{
  "form_id": 1,
  "column": "hh_size",
  "filters": {}
}
```
**Expected Response (200 OK):**
```json
{
  "form_id": 1,
  "column": "hh_size",
  "q1": 4.0,
  "median": 6.0,
  "q3": 8.0,
  "whisker_min": 2.0,
  "whisker_max": 12.0,
  "outliers": [15.0, 18.0]
}
```

### ✅ Example 2: With Filter (Narrows Data, Still Shows All Provinces in Result)
```json
{
  "form_id": 1,
  "column": "hh_size",
  "filters": {
    "gender": "Female"  // Filter narrows data to only females
  }
}
```
**Expected Response (200 OK):**
```json
{
  "form_id": 1,
  "column": "hh_size",
  "q1": 4.5,
  "median": 6.5,
  "q3": 8.5,
  "whisker_min": 2.0,
  "whisker_max": 12.0,
  "outliers": [15.0]
}
```
**Note:** Filters narrow the dataset but don't affect grouping. For grouping by province, use the **bar chart API** with `group_by: "province"`.

### ✅ Example 3: With Multiple Filters
```json
{
  "form_id": 1,
  "column": "age",
  "filters": {
    "province": "Kabul",
    "gender": "Female"
  }
}
```
**Expected Response (200 OK):**
```json
{
  "form_id": 1,
  "column": "age",
  "q1": 25.0,
  "median": 35.0,
  "q3": 45.0,
  "whisker_min": 18.0,
  "whisker_max": 60.0,
  "outliers": [75.0]
}
```

### ✅ Example 4: Multiple Filter Values (IN logic)
```json
{
  "form_id": 1,
  "column": "hh_size",
  "filters": {
    "province": ["Kabul", "Herat"]
  }
}
```
**Expected Response (200 OK):**
```json
{
  "form_id": 1,
  "column": "hh_size",
  "q1": 4.5,
  "median": 6.5,
  "q3": 8.5,
  "whisker_min": 2.0,
  "whisker_max": 14.0,
  "outliers": []
}
```

### ✅ Example 5: Empty Filters (Same as no filters)
```json
{
  "form_id": 1,
  "column": "age",
  "filters": {}
}
```

### ✅ Example 6: Filters with null/empty values (ignored)
```json
{
  "form_id": 1,
  "column": "hh_size",
  "filters": {
    "province": null,
    "district": ""
  }
}
```
**Note:** Null/empty filters are ignored, so this is equivalent to `{"filters": {}}`

---

## ❌ Request Payloads That Cause 400 Bad Request

### ❌ Example 1: Column Doesn't Exist
```json
{
  "form_id": 1,
  "column": "non_existent_column",
  "filters": {}
}
```
**Error Response (400 Bad Request):**
```json
{
  "detail": "No numeric data available for box plot"
}
```
**Reason:** The column `non_existent_column` doesn't exist in any submission data.

---

### ❌ Example 2: Column Exists But All Values Are Null/Empty
```json
{
  "form_id": 1,
  "column": "optional_numeric_field",
  "filters": {}
}
```
**Error Response (400 Bad Request):**
```json
{
  "detail": "No numeric data available for box plot"
}
```
**Reason:** All submissions have `null` or `""` for this column.

**How to Fix:**
- Check if the column name is correct
- Verify that submissions actually have data in this column
- Try a different column that you know has numeric values

---

### ❌ Example 3: Column Has Non-Numeric Values
```json
{
  "form_id": 1,
  "column": "province",
  "filters": {}
}
```
**Error Response (400 Bad Request):**
```json
{
  "detail": "No numeric data available for box plot"
}
```
**Reason:** `province` contains text values like "Kabul", "Herat" which cannot be converted to `float()`.

**How to Fix:**
- Use `province` with the **bar chart** API instead (for categorical grouping)
- Use a **numeric column** like `hh_size`, `age`, `count`, etc.

---

### ❌ Example 4: Filters Exclude All Numeric Values
```json
{
  "form_id": 1,
  "column": "hh_size",
  "filters": {
    "province": "NonExistentProvince"
  }
}
```
**Error Response (400 Bad Request):**
```json
{
  "detail": "No numeric data available for box plot"
}
```
**Reason:** No submissions match the filter, so `values` list is empty.

**How to Fix:**
- Check filter values are correct: `GET /api/forms/1/filter-fields` to see available options
- Remove or correct the filter
- Use valid filter values

---

### ❌ Example 5: Column Name Typo or Wrong Case
```json
{
  "form_id": 1,
  "column": "HH_Size",  // Wrong case
  "filters": {}
}
```
**Error Response (400 Bad Request):**
```json
{
  "detail": "No numeric data available for box plot"
}
```
**Reason:** Python dictionary keys are case-sensitive. If the actual column is `hh_size`, `HH_Size` won't match.

**How to Fix:**
- Use exact column name from `GET /api/forms/{form_id}/filter-fields`
- Check the actual submission data to see the exact field name

---

### ❌ Example 6: Form Has No Submissions
```json
{
  "form_id": 999,  // Form with no submissions
  "column": "hh_size",
  "filters": {}
}
```
**Error Response (400 Bad Request):**
```json
{
  "detail": "No numeric data available for box plot"
}
```
**Reason:** Form exists but has no submissions, so `values` list is empty.

**How to Fix:**
- Sync the form: `POST /api/sync` with `{"form_id": 999}`
- Use a form that has submissions

---

## How to Debug 400 Errors

### Step 1: Verify the Column Exists
```bash
# Get all filterable fields for the form
GET /api/forms/{form_id}/filter-fields
```

Look for fields with `type: "integer"` or `type: "decimal"` - these are numeric columns suitable for box plots.

### Step 2: Check Actual Submission Data
```bash
# Get sample submissions
GET /api/submissions?form_id={form_id}&limit=10
```

Check the `cleaned_data` or `submission_data` to see:
- Does the column exist?
- What are the actual values?
- Are they numeric?

### Step 3: Test Without Filters
```json
{
  "form_id": 1,
  "column": "hh_size",
  "filters": {}
}
```

If this works, your filters might be too restrictive.

### Step 4: Verify Form Has Submissions
```bash
# Check form details (includes submission_count)
GET /api/forms/{form_id}
```

### Step 5: Check Column Name Variations
Some columns might be in `cleaned_data` vs `submission_data`:
- Check both if one doesn't work
- Backend tries `cleaned_data` first, then falls back to `submission_data`

---

## Common Numeric Column Names

Typical numeric columns you might use:
- `hh_size` - Household size
- `age` - Age of respondent
- `age_of_respondent` - Age (alternative name)
- `respondent_age` - Age (alternative name)
- `count` - Count field
- `number_of_children` - Number of children
- `income` - Income amount
- `score` - Score/numeric rating
- `duration` - Duration in minutes/seconds
- `quantity` - Quantity field
- `qty` - Quantity (abbreviated)

**Note:** Always verify the exact column names using `GET /api/forms/{form_id}/filter-fields`

---

## Request Body Schema

### BoxPlotRequest Schema
```json
{
  "form_id": 1,              // Required: integer
  "column": "hh_size",       // Required: string (must be numeric column)
  "filters": {               // Optional: object
    "province": "Kabul",     // String: exact match
    "district": ["D1", "D2"], // Array: IN logic (match any)
    "ignored": null,         // Null/empty: ignored
    "also_ignored": ""       // Empty string: ignored
  }
}
```

### Filter Logic
- **String value:** Exact match (`str(value) == str(filter_value)`)
- **Array value:** IN logic (`value in filter_array`)
- **Null/empty:** Ignored (doesn't filter)
- **Multiple filters:** AND logic (all must match)

---

## Example cURL Commands

### ✅ Working Example
```bash
curl -X POST "http://localhost:8000/api/charts/box_plot" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "form_id": 1,
    "column": "hh_size",
    "filters": {
      "province": "Kabul"
    }
  }'
```

### ❌ Example That Causes 400
```bash
curl -X POST "http://localhost:8000/api/charts/box_plot" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "form_id": 1,
    "column": "province",  // Wrong: province is text, not numeric
    "filters": {}
  }'
```

---

## Summary

**400 Bad Request = No numeric data found**

To fix:
1. ✅ Use a **numeric column** (integer/decimal type)
2. ✅ Verify column exists: `GET /api/forms/{form_id}/filter-fields`
3. ✅ Check column has values: Look at actual submission data
4. ✅ Ensure filters are valid and not too restrictive
5. ✅ Verify form has submissions
6. ✅ Use exact column name (case-sensitive)

