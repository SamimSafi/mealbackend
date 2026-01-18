# Cross-Tabulation Analysis API

## Endpoint

```
GET /api/analysis/cross-tabulation
```

---

## Request

### Query Parameters

| Parameter | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| `form_id` | integer | ✅ | KoBo Form ID | `123` |
| `row_field` | string | ✅ | Variable for rows | `"gender"` |
| `column_field` | string | ✅ | Variable for columns | `"education_level"` |
| `date_from` | string (ISO 8601) | ❌ | Filter from date | `"2024-01-01"` |
| `date_to` | string (ISO 8601) | ❌ | Filter to date | `"2024-12-31"` |

### Example Request URLs

**Basic request (no date filters):**
```
GET /api/analysis/cross-tabulation?form_id=123&row_field=gender&column_field=education_level
```

**With date filters:**
```
GET /api/analysis/cross-tabulation?form_id=123&row_field=gender&column_field=education_level&date_from=2024-01-01&date_to=2024-12-31
```

**With authentication (Bearer Token):**
```
GET /api/analysis/cross-tabulation?form_id=123&row_field=gender&column_field=education_level
Authorization: Bearer {access_token}
```

---

## Response

### Success Response (200 OK)

```json
{
  "success": true,
  "form_id": 123,
  "row_field": "gender",
  "column_field": "education_level",
  "total_responses": 1500,
  "excluded_count": 0,
  "table": {
    "rows": [
      {
        "label": "Male",
        "count": 800,
        "columns": [
          {
            "label": "No Education",
            "count": 224,
            "percentage": 28.0
          },
          {
            "label": "Primary",
            "count": 280,
            "percentage": 35.0
          },
          {
            "label": "Secondary",
            "count": 200,
            "percentage": 25.0
          },
          {
            "label": "Higher",
            "count": 96,
            "percentage": 12.0
          }
        ]
      },
      {
        "label": "Female",
        "count": 700,
        "columns": [
          {
            "label": "No Education",
            "count": 322,
            "percentage": 46.0
          },
          {
            "label": "Primary",
            "count": 224,
            "percentage": 32.0
          },
          {
            "label": "Secondary",
            "count": 126,
            "percentage": 18.0
          },
          {
            "label": "Higher",
            "count": 28,
            "percentage": 4.0
          }
        ]
      }
    ],
    "column_totals": {
      "No Education": 546,
      "Primary": 504,
      "Secondary": 326,
      "Higher": 124
    },
    "grand_total": 1500
  },
  "insights": [
    "46% of female respondents have no education vs 28% of males",
    "Higher education attainment is 12% for males vs 4% for females",
    "Gender disparity is most pronounced in higher education",
    "79.8% of all respondents were male",
    "Smallest group: female with 20.2% of respondents"
  ],
  "metadata": {
    "generated_at": "2024-01-15T10:30:00Z",
    "date_filter_applied": false,
    "form_name": "Household Survey"
  }
}
```

### Response Schema

**`DetailedCrossTabResponse`**

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | Always `true` for successful response |
| `form_id` | integer | Internal form ID |
| `row_field` | string | Row field name |
| `column_field` | string | Column field name |
| `total_responses` | integer | Total submissions in form (within date range) |
| `excluded_count` | integer | Submissions with missing values in either field |
| `table` | object | Cross-tabulation table |
| `insights` | array[string] | Auto-generated insights (up to 5) |
| `metadata` | object | Response metadata |

**`table` object**

| Field | Type | Description |
|-------|------|-------------|
| `rows` | array[CrossTabRowItem] | Array of row data |
| `column_totals` | object | Column totals (key: label, value: count) |
| `grand_total` | integer | Total count across all cells |

**`CrossTabRowItem`**

| Field | Type | Description |
|-------|------|-------------|
| `label` | string | Row category label |
| `count` | integer | Total count for this row |
| `columns` | array[CrossTabColumnItem] | Column items for this row |

**`CrossTabColumnItem`**

| Field | Type | Description |
|-------|------|-------------|
| `label` | string | Column category label |
| `count` | integer | Count for this cell |
| `percentage` | float | Percentage of row total (0-100) |

**`metadata` object**

| Field | Type | Description |
|-------|------|-------------|
| `generated_at` | string (ISO 8601) | Response generation timestamp |
| `date_filter_applied` | boolean | Whether date filters were used |
| `form_name` | string | Name of the form |

---

## Error Responses

### 400 - Bad Request (Missing Parameters)

```json
{
  "detail": "form_id, row_field, and column_field are required"
}
```

### 400 - Bad Request (Field Not Found)

```json
{
  "detail": "Field 'gender' not found in form. Available fields: ['age_group', 'location', 'education_level']"
}
```

### 404 - Form Not Found

```json
{
  "detail": "Form with ID 999 not found"
}
```

### 422 - Invalid Date Format

```json
{
  "detail": "date_from and date_to must be in YYYY-MM-DD format"
}
```

### 500 - Internal Server Error

```json
{
  "detail": "Internal server error message"
}
```

---

## Frontend Integration Examples

### JavaScript/TypeScript (Fetch API)

```javascript
const fetchCrossTabulation = async (formId, rowField, columnField, dateFrom = null, dateTo = null) => {
  const params = new URLSearchParams({
    form_id: formId,
    row_field: rowField,
    column_field: columnField
  });

  if (dateFrom) params.append('date_from', dateFrom);
  if (dateTo) params.append('date_to', dateTo);

  const response = await fetch(`/api/analysis/cross-tabulation?${params}`, {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${accessToken}`,
      'Content-Type': 'application/json'
    }
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to fetch cross-tabulation');
  }

  return await response.json();
};

// Usage
try {
  const data = await fetchCrossTabulation(123, 'gender', 'education_level', '2024-01-01', '2024-12-31');
  console.log('Cross-tabulation data:', data);
  
  // Display table
  displayCrossTabTable(data.table);
  
  // Display insights
  displayInsights(data.insights);
  
} catch (error) {
  console.error('Error:', error);
}
```

### React Hook Example

```typescript
import { useState, useEffect } from 'react';

interface CrossTabData {
  success: boolean;
  form_id: number;
  row_field: string;
  column_field: string;
  total_responses: number;
  excluded_count: number;
  table: any;
  insights: string[];
  metadata: any;
}

const useCrossTabulation = (formId: number, rowField: string, columnField: string, dateFrom?: string, dateTo?: string) => {
  const [data, setData] = useState<CrossTabData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const params = new URLSearchParams({
          form_id: String(formId),
          row_field: rowField,
          column_field: columnField
        });

        if (dateFrom) params.append('date_from', dateFrom);
        if (dateTo) params.append('date_to', dateTo);

        const response = await fetch(`/api/analysis/cross-tabulation?${params}`, {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('access_token')}`
          }
        });

        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }

        const result = await response.json();
        setData(result);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [formId, rowField, columnField, dateFrom, dateTo]);

  return { data, loading, error };
};

export default useCrossTabulation;
```

### React Component Example

```tsx
import React from 'react';
import useCrossTabulation from './useCrossTabulation';

interface CrossTabTableProps {
  formId: number;
  rowField: string;
  columnField: string;
  dateFrom?: string;
  dateTo?: string;
}

const CrossTabTable: React.FC<CrossTabTableProps> = ({ 
  formId, 
  rowField, 
  columnField, 
  dateFrom, 
  dateTo 
}) => {
  const { data, loading, error } = useCrossTabulation(formId, rowField, columnField, dateFrom, dateTo);

  if (loading) return <div>Loading...</div>;
  if (error) return <div className="error">Error: {error}</div>;
  if (!data) return <div>No data available</div>;

  return (
    <div className="cross-tab-container">
      <div className="header">
        <h2>{data.metadata.form_name}</h2>
        <p className="subtitle">
          {data.row_field} vs {data.column_field}
        </p>
      </div>

      {/* Metadata */}
      <div className="metadata">
        <span>Total Responses: {data.total_responses}</span>
        <span>Excluded: {data.excluded_count}</span>
        <span>Generated: {new Date(data.metadata.generated_at).toLocaleDateString()}</span>
      </div>

      {/* Cross-Tabulation Table */}
      <table className="crosstab-table">
        <thead>
          <tr>
            <th>{data.row_field}</th>
            {Object.keys(data.table.column_totals).map(col => (
              <th key={col}>{col}</th>
            ))}
            <th>Total</th>
          </tr>
        </thead>
        <tbody>
          {data.table.rows.map(row => (
            <tr key={row.label}>
              <td className="row-label">{row.label}</td>
              {row.columns.map(col => (
                <td key={col.label} className="cell">
                  <div className="count">{col.count}</div>
                  <div className="percentage">{col.percentage}%</div>
                </td>
              ))}
              <td className="row-total">{row.count}</td>
            </tr>
          ))}
          <tr className="totals-row">
            <td>Total</td>
            {Object.entries(data.table.column_totals).map(([col, total]) => (
              <td key={col} className="total">{total}</td>
            ))}
            <td className="grand-total">{data.table.grand_total}</td>
          </tr>
        </tbody>
      </table>

      {/* Insights */}
      {data.insights.length > 0 && (
        <div className="insights">
          <h3>Key Insights</h3>
          <ul>
            {data.insights.map((insight, idx) => (
              <li key={idx}>{insight}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};

export default CrossTabTable;
```

### CSS Styling

```css
.cross-tab-container {
  padding: 20px;
  background: #f9f9f9;
  border-radius: 8px;
  margin: 20px 0;
}

.header h2 {
  margin: 0 0 5px 0;
  color: #333;
}

.subtitle {
  margin: 0;
  color: #666;
  font-size: 0.9em;
}

.metadata {
  display: flex;
  gap: 20px;
  margin: 15px 0;
  font-size: 0.9em;
  color: #666;
}

.crosstab-table {
  width: 100%;
  border-collapse: collapse;
  background: white;
  margin: 20px 0;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}

.crosstab-table thead {
  background: #f0f0f0;
  border-bottom: 2px solid #ddd;
}

.crosstab-table th {
  padding: 12px;
  text-align: left;
  font-weight: 600;
  color: #333;
}

.crosstab-table td {
  padding: 12px;
  border-bottom: 1px solid #eee;
}

.crosstab-table .cell {
  background: #f9f9f9;
  text-align: center;
}

.cell .count {
  font-weight: 600;
  color: #333;
}

.cell .percentage {
  font-size: 0.85em;
  color: #666;
}

.row-label {
  font-weight: 600;
  background: #f0f0f0;
}

.row-total,
.totals-row .total,
.grand-total {
  font-weight: 600;
  background: #f0f0f0;
  text-align: center;
}

.grand-total {
  background: #e8e8e8;
  color: #333;
}

.insights {
  margin-top: 20px;
  padding: 15px;
  background: #e8f4f8;
  border-left: 4px solid #0288d1;
  border-radius: 4px;
}

.insights h3 {
  margin: 0 0 10px 0;
  color: #0288d1;
}

.insights ul {
  margin: 0;
  padding-left: 20px;
}

.insights li {
  margin: 5px 0;
  color: #333;
}
```

---

## Data Processing Tips

### Calculate Percentages by Row
Each cell's percentage is calculated as: `(cell_count / row_total) * 100`

### Calculate Percentages by Column (Optional)
If you need column percentages: `(cell_count / column_total) * 100`

### Access Total Responses
- **Total responses in form**: `data.total_responses`
- **Responses with valid data**: `data.total_responses - data.excluded_count`
- **Grand total in table**: `data.table.grand_total`

### Filter Insights
```javascript
// Show only high-percentage insights
const highImpactInsights = data.insights.filter(insight => 
  insight.includes('%') && parseInt(insight.split('%')[0]) > 30
);
```

---

## Common Use Cases

### 1. Display in Dashboard
```typescript
const handleDashboardDisplay = (crossTabData) => {
  return {
    title: `${crossTabData.row_field} vs ${crossTabData.column_field}`,
    table: formatTableForDisplay(crossTabData.table),
    stats: {
      totalResponses: crossTabData.total_responses,
      coverage: ((crossTabData.total_responses - crossTabData.excluded_count) / crossTabData.total_responses * 100).toFixed(1)
    },
    topInsights: crossTabData.insights.slice(0, 3)
  };
};
```

### 2. Export to Excel
```typescript
const exportToExcel = (crossTabData) => {
  const ws = XLSX.utils.json_to_sheet([
    ['Cross-Tabulation Report'],
    [`${crossTabData.row_field} vs ${crossTabData.column_field}`],
    [''],
    ...formatTableForExport(crossTabData.table)
  ]);
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, 'Cross-Tab');
  XLSX.writeFile(wb, `crosstab_${Date.now()}.xlsx`);
};
```

### 3. Create Visualizations
```typescript
const prepareForChart = (crossTabData) => {
  return {
    labels: crossTabData.table.rows.map(r => r.label),
    datasets: Object.keys(crossTabData.table.column_totals).map(col => ({
      label: col,
      data: crossTabData.table.rows.map(row => 
        row.columns.find(c => c.label === col)?.count || 0
      )
    }))
  };
};
```
