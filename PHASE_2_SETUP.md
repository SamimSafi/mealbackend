# Phase 2: Setup & Deployment Guide

## Quick Start (5 steps)

### Step 1: Initialize Database & Create Tables

The system uses SQLAlchemy's `Base.metadata.create_all()` which automatically creates all tables from models.

**Option A: Run directly (automatic)**
```bash
python -c "from database import init_db; init_db()"
```

**Option B: Using FastAPI startup**
Just start the server - tables will be created automatically:
```bash
python main.py
# or
uvicorn main:app --reload
```

**Verify tables created:**
```bash
python -c "
from database import engine, SessionLocal
from sqlalchemy import inspect

inspector = inspect(engine)
tables = inspector.get_table_names()
print('Tables created:')
for table in sorted(tables):
    print(f'  ✓ {table}')
"
```

Expected new tables:
- `kpi_definitions` - KPI metadata
- `kpi_values` - Computed KPI values
- `report_cache` - Cached reports
- `form_field_mappings` - Field mappings per form

---

### Step 2: Seed Standard KPI Definitions

Register all standard NGO/UN indicators (WASH, Nutrition, Protection, Education, Food Security, Livelihoods):

```bash
python scripts/seed_kpis.py
```

Output:
```
======================================================================
SEEDING KPI DEFINITIONS
======================================================================
✓ water_access_rate         | WASH            | % Households with Access to Safe Water
✓ sanitation_facility_rate  | WASH            | % Households with Access to Improved San...
✓ hand_washing_practice     | WASH            | % Households with Hand Washing Facilities
✓ child_malnutrition_rate   | Nutrition       | % Children with Acute Malnutrition (MUAC <...
...
======================================================================
✓ KPI Seeding Complete: 14 KPIs registered
======================================================================
```

---

### Step 3: Configure Form Field Mappings (Optional but Recommended)

Map your form fields to standard dimensions (age, gender, location):

```bash
python scripts/setup_form_field_mappings.py
```

Interactive walkthrough:
```
Form: Child Protection Assessment (ID: 2)
------
Available fields in form schema:
  1. demographics/age_group    → Age Group
  2. child/sex                 → Child's Sex
  3. protection/status         → Protection Status
  4. location/district         → District

Enter field names for demographics (or leave blank to auto-detect):
  Age field: demographics/age_group
  Gender field: child/sex
  Household size field: 
  Location field: location/district
✓ Mapping created
```

**Why this matters:**
- Demographics report won't work without age/gender fields
- Geo report needs location field
- Auto-detection finds ~80% of fields, but mapping is more reliable

---

### Step 4: Start the Server

```bash
python main.py
# or
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Expected output:
```
✅ Database tables created successfully
📋 Tables created: branding, forms, indicators, kpi_definitions, kpi_values, ...
✓ Default organization created
✓ Default admin user created (username: 'admin', password: 'admin123')
Initializing report services...
✓ Report services initialized
Application startup complete
```

---

### Step 5: Test Report Endpoints

Login first:
```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'
```

Response:
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer"
}
```

**Test endpoint (use the token):**
```bash
curl http://localhost:8000/api/reports/demographics?form_id=16 \
  -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc..."
```

---

## Available Report Endpoints

### 1. Survey Summary
```bash
GET /api/reports/survey-summary/{form_id}?date_from=2024-01-01&date_to=2024-12-31
```
**Returns:**
- Total submissions
- Completion rate
- Validation rate
- Per-question summaries (counts + percentages)

**Response structure:**
```json
{
  "metadata": {...},
  "form_id": 16,
  "form_title": "Child Protection Assessment",
  "summary": {
    "total_submissions": 150,
    "completion_rate": 87.5,
    "validation_rate": 92.0
  },
  "question_summaries": [
    {
      "field": "demographics/age_group",
      "field_label": "Age Group",
      "response_type": "categorical",
      "valid_responses": 150,
      "null_responses": 0,
      "options": [
        {"label": "0-5", "count": 30, "percentage": 20.0},
        {"label": "6-17", "count": 85, "percentage": 56.7},
        ...
      ]
    }
  ]
}
```

---

### 2. Indicators (KPI Report)
```bash
GET /api/reports/indicators?category=Nutrition&date_from=2024-01-01
```
**Returns:**
- All KPIs with current values
- Comparison to baseline + target
- Progress to target (%)
- Broken down by category

**Example response:**
```json
{
  "metadata": {...},
  "kpis": [
    {
      "kpi_code": "child_malnutrition_rate",
      "kpi_label": "% Children with Acute Malnutrition",
      "value": 22.5,
      "unit": "%",
      "baseline": 28.0,
      "target": 15.0,
      "progress_to_target_pct": 18.5,
      "sample_size": 150
    }
  ],
  "by_category": {
    "Nutrition": [...],
    "WASH": [...]
  }
}
```

---

### 3. Demographics
```bash
GET /api/reports/demographics?form_id=16
```
**Returns:**
- Age distribution by groups (0-5, 6-17, 18-60, 60+)
- Gender distribution
- Household size statistics (if applicable)
- Cross-tabulation (e.g., gender × age)

**Auto-detects demographic fields** from form schema or mapping

---

### 4. Geospatial
```bash
GET /api/reports/geo?form_id=16
```
**Returns:**
- GPS points with submission counts
- Coverage by location
- Geographic bounds (north, south, east, west)

**For mapping visualization** (Leaflet, MapBox, etc.)

---

### 5. Trends
```bash
GET /api/reports/trends/{kpi_code}?granularity=monthly&date_from=2024-01-01
```
**Granularities:** daily, weekly, monthly, quarterly, annual

**Returns:**
- KPI values over time
- Trend direction (up/down/stable)
- % change from first to last period

**Example:**
```json
{
  "kpi_code": "water_access_rate",
  "time_granularity": "monthly",
  "trend_data": [
    {"period": "2024-01", "value": 50.0, "sample_size": 30},
    {"period": "2024-02", "value": 54.2, "sample_size": 35},
    {"period": "2024-03", "value": 58.3, "sample_size": 40}
  ],
  "summary": {
    "overall_trend": "up",
    "trend_pct_change": 16.7,
    "avg_monthly_improvement": 2.78
  }
}
```

---

### 6. Program Comparison
```bash
GET /api/reports/program-comparison?dimension=form_id&kpi_code=water_access_rate
```
**Compares KPIs across:**
- Forms/Programs
- Locations/Districts
- Any custom field

**Returns:**
- KPI value for each program
- Status (ahead, on_track, behind)
- Aggregate stats (avg, min, max, median)

---

### 7. KPI Definitions
```bash
GET /api/kpis?category=WASH
```
**Returns:**
- All available KPIs
- Labels, descriptions, baselines, targets
- Computation logic

---

## Architecture Summary

```
┌─ API Routes (main.py)
│   └─ Get filter params, call ReportService
│
├─ ReportService (report_service.py)
│   └─ get_survey_summary() → question summaries
│   └─ get_indicator_report() → KPI values
│   └─ get_demographics() → age/gender/hh_size distributions
│   └─ get_geospatial() → GPS points + coverage
│   └─ get_trends() → KPI over time
│   └─ get_program_comparison() → KPI across programs
│
├─ KPIEngine (kpi_engine.py)
│   └─ compute(kpi_code, submissions) → single KPI value
│   └─ compute_all(submissions) → all KPIs
│   └─ compute_time_series(kpi_code, submissions, granularity) → trend data
│   └─ compute_by_dimension(kpi_code, submissions, field) → breakdowns
│
├─ FilterContext (report_filters.py)
│   └─ Applies date, location, form, field filters uniformly
│   └─ Handles field discovery for demographics
│
└─ Database Models (models.py)
    └─ KPIDefinition - KPI metadata
    └─ KPIValue - Computed values (time-series)
    └─ ReportCache - Cached report results
    └─ FormFieldMapping - Field mappings per form
```

---

## Troubleshooting

### Tables not created
**Error:** `sqlite3.OperationalError: no such table: kpi_definitions`

**Solution:**
```bash
python -c "from database import init_db; init_db()"
```

---

### Report returns empty demographics
**Cause:** Age/gender fields not found in form

**Solution:** Run field mapping setup
```bash
python scripts/setup_form_field_mappings.py
```

Or provide explicit field names in API:
```bash
GET /api/reports/demographics?form_id=16&age_field=child/age&gender_field=child/sex
```

---

### KPI values all zero
**Cause:** KPI field names don't match form fields

**Solution:** Check KPI `computation_logic` in database:
```bash
python -c "
from database import SessionLocal
from models import KPIDefinition

db = SessionLocal()
kpi = db.query(KPIDefinition).filter(KPIDefinition.kpi_code == 'water_access_rate').first()
print('Computation Logic:')
print(kpi.computation_logic)
"
```

Update KPI computation logic or add custom KPI with correct field names.

---

### 404 on report endpoints
**Cause:** Report services not initialized

**Verify startup logs:**
```
Initializing report services...
✓ Report services initialized
```

If missing, restart server and check for errors in logs.

---

## Performance Optimization

### Caching
Reports are cached by default (24-hour TTL). To invalidate cache:
```bash
# Clear all cached reports
python -c "
from database import SessionLocal
from models import ReportCache

db = SessionLocal()
db.query(ReportCache).delete()
db.commit()
"
```

### Indexing
Key fields are indexed:
- `kpi_definitions.kpi_code` - Fast KPI lookup
- `kpi_values.period_start` - Fast time-series queries
- `submissions.created_at` - Fast date filtering
- `submissions.form_id` - Fast form filtering

---

## Next Steps

1. ✅ Initialize database
2. ✅ Seed KPIs
3. ✅ Configure form field mappings
4. ✅ Test report endpoints
5. **Frontend Integration** - Build dashboards using report endpoints
6. **Export Functionality** - Add PDF/Excel/CSV export (Phase 3)
7. **Advanced Filtering** - Add multi-field filters (Phase 3)
8. **Caching Strategy** - Optimize for large datasets (Phase 3)

---

## Support

For issues or questions:
1. Check troubleshooting section above
2. Review endpoint documentation in API_SUMMARY.md
3. Check logs for error messages
4. Verify database has tables and data

