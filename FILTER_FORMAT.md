# Filter Format for Chart APIs

## Filter Structure

Filters are sent as a JSON object where:
- **Keys** = Field names (from Kobo form, e.g., `"province"`, `"info/Province"`, `"district"`)
- **Values** = Filter values (string, array, or null)

## Examples

### Empty Filters (No Filtering)
```json
{
  "form_id": 1,
  "group_by": "province",
  "filters": {}
}
```

### Single Value Filter
```json
{
  "form_id": 1,
  "group_by": "district",
  "filters": {
    "province": "Kabul"
  }
}
```

### Multiple Values Filter (OR logic - match any)
```json
{
  "form_id": 1,
  "group_by": "district",
  "filters": {
    "province": ["Kabul", "Herat", "Balkh"]
  }
}
```

### Multiple Filters (AND logic - all must match)
```json
{
  "form_id": 1,
  "group_by": "district",
  "filters": {
    "province": "Kabul",
    "gender": "Female",
    "edge": "Urban"
  }
}
```

### Mixed Filters
```json
{
  "form_id": 1,
  "group_by": "district",
  "filters": {
    "province": ["Kabul", "Herat"],  // Array: match any
    "gender": "Female",                // String: exact match
    "age_group": null                  // null: ignored
  }
}
```

## Filter Logic

### Single Value (String)
- **Exact match**: `"province": "Kabul"` matches only submissions where province equals "Kabul"
- **Case-sensitive**: `"Kabul"` ≠ `"kabul"`

### Multiple Values (Array)
- **IN logic**: `"province": ["Kabul", "Herat"]` matches submissions where province is Kabul OR Herat
- **At least one match required**

### Empty/Null Values
- **Ignored**: `"province": null` or `"province": ""` or `"province": []` are ignored
- **Not applied as filter**

### Multiple Filters
- **AND logic**: All non-empty filters must match
- Example: `{"province": "Kabul", "gender": "Female"}` = province is Kabul AND gender is Female

## Field Names

Use the exact field names from your Kobo form:
- `"province"` - if field name is "province"
- `"info/Province"` - if field is nested like `info.Province`
- `"district"` - if field name is "district"
- `"gender"` - if field name is "gender"

The backend will try to find fields using:
1. Exact match
2. Case-insensitive match
3. Nested path (for `info/Province`)
4. Flattened notation (for `info_Province`)

## Frontend Implementation Examples

### React/TypeScript
```typescript
// Empty filters
const filters = {};

// Single filter
const filters = {
  province: "Kabul"
};

// Multiple values
const filters = {
  province: ["Kabul", "Herat"]
};

// Multiple filters
const filters = {
  province: "Kabul",
  gender: "Female"
};

// API call
const response = await axios.post('/api/charts/bar_chart', {
  form_id: 1,
  group_by: "district",
  filters: filters
});
```

### JavaScript
```javascript
// Build filters object
const filters = {};

if (selectedProvince) {
  filters.province = selectedProvince;
}

if (selectedGenders && selectedGenders.length > 0) {
  filters.gender = selectedGenders; // Array
}

// Remove empty filters
Object.keys(filters).forEach(key => {
  if (filters[key] === null || filters[key] === "" || 
      (Array.isArray(filters[key]) && filters[key].length === 0)) {
    delete filters[key];
  }
});

// API call
fetch('/api/charts/bar_chart', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    form_id: 1,
    group_by: "district",
    filters: filters
  })
});
```

## Complete Request Examples

### Bar Chart with Filters
```json
POST /api/charts/bar_chart
{
  "form_id": 1,
  "group_by": "district",
  "filters": {
    "province": "Kabul",
    "gender": "Female"
  }
}
```

### Box Plot with Filters
```json
POST /api/charts/box_plot
{
  "form_id": 1,
  "column": "hh_size",
  "filters": {
    "province": ["Kabul", "Herat"],
    "edge": "Urban"
  }
}
```

### Daily Data Load with Filters (if supported)
```json
GET /api/data/load?date=2024-01-15&form_id=1
```

## Notes

1. **Filters are optional** - You can always send `{}` (empty object)
2. **Field names** - Use the exact field names from your Kobo form schema
3. **Value types** - Strings for single values, arrays for multiple values
4. **Null handling** - null, "", or [] values are ignored
5. **Case sensitivity** - Field values are compared as strings (case-sensitive)

