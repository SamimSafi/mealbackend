# NGO-Friendly Reports & Dashboards - Standardization Plan

## Executive Summary
The backend has existing endpoints for basic dashboards and aggregates, but lacks:
- Standardized KPI definitions (mathematically precise)
- Structured report endpoints (survey summary, indicators, geo, trends)
- Consistent filtering architecture
- Response schema formalization
- Modular, reusable aggregation logic

This plan standardizes the reporting system following M&E best practices.

---

## Part 1: Current State Analysis

### Existing Infrastructure
✅ **Working Endpoints:**
- `POST /form/{form_id}/aggregate` - Generic grouping/metrics
- `GET /api/dashboard/summary` - Basic overview
- `GET /api/dashboard/indicators` - Indicator list
- `GET /api/dashboard/accountability` - Complaints dashboard
- `POST /api/forms/{form_id}/chart-data` - Chart data with code→label conversion
- `POST /api/charts/box_plot` - Box plot statistics
- `POST /api/charts/bar_chart` - Categorical bar charts

### Existing Data Models
- `Form` - Kobo form metadata + schema
- `Submission` - Raw + cleaned submission data
- `Indicator` - Computed indicators (limited usage)
- `RawSubmission` - Raw data before processing

### Issues to Fix
1. **Inconsistent KPI Logic** - No formal definitions; computed ad-hoc
2. **Scattered Aggregation** - Logic duplicated across endpoints
3. **No Standard Filters** - Filtering varies by endpoint
4. **Missing Schemas** - No strict response definitions for reports
5. **No Time-Series KPIs** - Trends only count, not actual indicator values
6. **Geo Data Underutilized** - Location fields not aggregated properly

---

## Part 2: Proposed Architecture

### 2.1 Standardized Filters (Applied Universally)
All report endpoints will accept:
```python
{
    "date_from": "2024-01-01",           # Optional: start date
    "date_to": "2024-12-31",             # Optional: end date
    "location": ["province1", "prov2"],  # Optional: filter by location/admin area
    "form_id": [1, 2],                   # Optional: filter by forms
    "field_filters": {                   # Optional: equality filters on any field
        "info/gender": ["male", "female"],
        "info/province": ["Kabul"]
    },
    "exclude_incomplete": true            # Optional: exclude invalid submissions
}
```

### 2.2 Modular KPI Engine
Create a `KPIEngine` class to:
- Register KPIs with mathematical definitions
- Compute KPIs with consistent filtering
- Support time-series aggregation
- Return standardized KPI responses

**Example KPI Definition:**
```python
KPI(
    id="water_access_rate",
    label="% Households with Access to Safe Water",
    description="Count of households with safe water / Total households",
    formula="count(clean_water=='yes') / count(*) * 100",
    unit="%",
    baseline=None,
    target=None,
    report_category="WASH"
)
```

### 2.3 Report Types & Endpoints

#### **Report 1: Survey Summary** 
`GET /api/reports/survey-summary/{form_id}`
- Total submissions
- Submission rate by location/time
- Data quality metrics (% complete fields, validation rate)
- Question-wise response summaries (counts + percentages for each option)

**Response Format:**
```python
{
    "form_id": 1,
    "form_title": "...",
    "filters_applied": {...},
    "timestamp": "2024-01-10T12:00:00Z",
    "summary": {
        "total_submissions": 150,
        "date_range": {"from": "...", "to": "..."},
        "completion_rate": 87.5,  # % of fields filled
        "validation_rate": 92.0   # % of submissions with no errors
    },
    "question_summaries": [
        {
            "field": "info/province",
            "field_label": "Province",
            "field_type": "select_one",
            "response_type": "categorical",
            "valid_responses": 150,
            "null_responses": 0,
            "options": [
                {"label": "Kabul", "code": "p1", "count": 50, "percentage": 33.3},
                {"label": "Balkh", "code": "p2", "count": 45, "percentage": 30.0},
                {"label": "Jalalabad", "code": "p3", "count": 55, "percentage": 36.7}
            ]
        },
        {
            "field": "beneficiary/hh_size",
            "field_label": "Household Size",
            "field_type": "integer",
            "response_type": "numeric",
            "valid_responses": 148,
            "null_responses": 2,
            "statistics": {
                "min": 1,
                "max": 12,
                "mean": 5.2,
                "median": 5,
                "std_dev": 1.8
            }
        }
    ]
}
```

#### **Report 2: Indicator Report (KPIs)**
`GET /api/reports/indicators`
- Pre-defined KPIs computed from submissions
- Current value + target + baseline
- Breakdown by location/time

**Response Format:**
```python
{
    "timestamp": "2024-01-10T12:00:00Z",
    "filters_applied": {...},
    "period": "2024",
    "kpis": [
        {
            "id": "water_access_rate",
            "label": "% Households with Access to Safe Water",
            "category": "WASH",
            "unit": "%",
            "baseline": 45.0,
            "target": 70.0,
            "current_value": 58.3,
            "trend": "up",
            "progress_to_target": 24.7,  # (58.3-45)/(70-45)*100
            "breakdown": [
                {"dimension": "province", "value": "Kabul", "kpi_value": 62.5, "sample_size": 50},
                {"dimension": "province", "value": "Balkh", "kpi_value": 55.0, "sample_size": 45}
            ]
        },
        {
            "id": "malnutrition_rate",
            "label": "% Children Malnourished (MUAC < 115mm)",
            "category": "Nutrition",
            "unit": "%",
            "baseline": 28.0,
            "target": 15.0,
            "current_value": 22.5,
            "trend": "down",
            "progress_to_target": 18.5
        }
    ]
}
```

#### **Report 3: Program Comparison**
`GET /api/reports/program-comparison`
- Compare KPIs across forms/projects/locations
- Side-by-side tables

**Response Format:**
```python
{
    "timestamp": "2024-01-10T12:00:00Z",
    "filters_applied": {...},
    "comparison_dimension": "form_id",  # or "province", "region", etc.
    "kpi_id": "water_access_rate",
    "items": [
        {
            "item_id": 1,
            "item_label": "WASH Program - 2024",
            "kpi_value": 58.3,
            "target": 70.0,
            "baseline": 45.0,
            "sample_size": 150,
            "status": "on_track"  # on_track, behind, ahead
        },
        {
            "item_id": 2,
            "item_label": "WASH Program - 2025",
            "kpi_value": 65.2,
            "target": 75.0,
            "baseline": 45.0,
            "sample_size": 120,
            "status": "ahead"
        }
    ],
    "aggregate": {
        "avg": 61.75,
        "min": 58.3,
        "max": 65.2
    }
}
```

#### **Report 4: Demographics**
`GET /api/reports/demographics`
- Age, gender, household size distributions
- Cross-tabulations (e.g., gender × education)

**Response Format:**
```python
{
    "timestamp": "2024-01-10T12:00:00Z",
    "filters_applied": {...},
    "demographics": {
        "by_age": [
            {"age_group": "0-5", "count": 25, "percentage": 16.7},
            {"age_group": "6-17", "count": 45, "percentage": 30.0},
            {"age_group": "18-60", "count": 65, "percentage": 43.3},
            {"age_group": "60+", "count": 15, "percentage": 10.0}
        ],
        "by_gender": [
            {"gender": "Male", "count": 75, "percentage": 50.0},
            {"gender": "Female", "count": 75, "percentage": 50.0}
        ],
        "by_hh_size": {
            "min": 1,
            "max": 12,
            "mean": 5.2,
            "median": 5,
            "std_dev": 1.8
        },
        "cross_tabulation": [  # gender × education
            {"dimension1": "Male", "dimension2": "Primary", "count": 30},
            {"dimension1": "Male", "dimension2": "Secondary", "count": 40},
            {"dimension1": "Female", "dimension2": "Primary", "count": 25},
            {"dimension1": "Female", "dimension2": "Secondary", "count": 50}
        ]
    }
}
```

#### **Report 5: Geospatial**
`GET /api/reports/geo`
- GPS points with submission counts
- Heatmap data (hotspots)
- Coverage by admin area

**Response Format:**
```python
{
    "timestamp": "2024-01-10T12:00:00Z",
    "filters_applied": {...},
    "geo_data": {
        "points": [
            {"lat": 34.52, "lng": 69.18, "count": 15, "location_name": "Kabul City"},
            {"lat": 36.74, "lng": 68.11, "count": 12, "location_name": "Balkh City"}
        ],
        "coverage": {
            "by_province": [
                {"province": "Kabul", "submissions": 50, "coverage_pct": 45.5},
                {"province": "Balkh", "submissions": 45, "coverage_pct": 40.9},
                {"province": "Jalalabad", "submissions": 55, "coverage_pct": 50.0}
            ]
        },
        "bounds": {
            "north": 36.9,
            "south": 33.8,
            "east": 71.6,
            "west": 60.5
        }
    }
}
```

#### **Report 6: Trend Report**
`GET /api/reports/trends`
- Line chart data for KPIs over time
- Monthly/weekly aggregations

**Response Format:**
```python
{
    "timestamp": "2024-01-10T12:00:00Z",
    "filters_applied": {...},
    "kpi_id": "water_access_rate",
    "kpi_label": "% Households with Access to Safe Water",
    "time_granularity": "monthly",
    "trend_data": [
        {
            "period": "2024-01",
            "period_label": "January 2024",
            "value": 50.0,
            "sample_size": 30,
            "baseline": 45.0,
            "target": 70.0
        },
        {
            "period": "2024-02",
            "period_label": "February 2024",
            "value": 54.2,
            "sample_size": 35,
            "baseline": 45.0,
            "target": 70.0
        },
        {
            "period": "2024-03",
            "period_label": "March 2024",
            "value": 58.3,
            "sample_size": 40,
            "baseline": 45.0,
            "target": 70.0
        }
    ],
    "summary": {
        "overall_trend": "up",
        "trend_pct_change": 16.7,  # (58.3-50)/50 * 100
        "avg_monthly_improvement": 2.78
    }
}
```

---

## Part 3: KPI Definitions (Formal & Mathematical)

### WASH KPIs
1. **water_access_rate**
   - Formula: `count(water_source IN ['piped', 'borehole', 'well']) / count(*) * 100`
   - Unit: `%`
   - Interpretation: Proportion of households with access to safe water source

2. **sanitation_facility_rate**
   - Formula: `count(toilet_type IN ['flush', 'pit_latrine_ventilated']) / count(*) * 100`
   - Unit: `%`

### Nutrition KPIs
1. **child_malnutrition_rate**
   - Formula: `count(muac < 115) / count(age_group IN ['6-59months']) * 100`
   - Unit: `%`
   - Notes: MUAC < 115mm indicates acute malnutrition

2. **stunting_rate**
   - Formula: `count(height_for_age < -2SD) / count(age_group IN ['0-59months']) * 100`
   - Unit: `%`

### Protection KPIs
1. **child_labor_prevalence**
   - Formula: `count(engaging_in_labor == 'yes') / count(age_group IN ['5-17']) * 100`
   - Unit: `%`

---

## Part 4: Data Models

### New Models to Create

#### **1. KPIDefinition Model**
Stores formal KPI metadata:
```python
class KPIDefinition(Base):
    __tablename__ = "kpi_definitions"
    
    id = Column(Integer, primary_key=True)
    kpi_code = Column(String(50), unique=True, index=True)  # e.g., "water_access_rate"
    label = Column(String(255))
    description = Column(Text)
    unit = Column(String(20))  # %, count, days, etc.
    formula = Column(Text)  # Human-readable formula
    computation_rules = Column(JSON)  # {'field': '...', 'condition': '...'}
    baseline = Column(Float, nullable=True)
    target = Column(Float, nullable=True)
    report_category = Column(String(50))  # WASH, Nutrition, Protection
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)
```

#### **2. KPIValue Model**
Stores computed KPI values with time-series support:
```python
class KPIValue(Base):
    __tablename__ = "kpi_values"
    
    id = Column(Integer, primary_key=True)
    kpi_definition_id = Column(Integer, ForeignKey("kpi_definitions.id"))
    form_id = Column(Integer, ForeignKey("forms.id"), nullable=True)
    location = Column(String(100), nullable=True)  # Province, district, etc.
    period_start = Column(DateTime, index=True)  # For time-series
    period_end = Column(DateTime)
    value = Column(Float)
    sample_size = Column(Integer)  # N of submissions used
    computed_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    kpi_definition = relationship("KPIDefinition")
    form = relationship("Form")
```

#### **3. ReportCache Model** (Optional, for performance)
```python
class ReportCache(Base):
    __tablename__ = "report_cache"
    
    id = Column(Integer, primary_key=True)
    report_type = Column(String(50))  # survey_summary, indicators, geo, etc.
    filters_hash = Column(String(64), unique=True, index=True)  # Hash of filter params
    result_json = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)  # Cache TTL
```

---

## Part 5: Standardized Request/Response Schemas

### Common Request Schema
```python
class ReportRequest(BaseModel):
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    location: Optional[list[str]] = []  # Province codes/names
    form_id: Optional[list[int]] = []
    field_filters: Optional[dict[str, Any]] = {}
    exclude_incomplete: bool = False
    
    # Pagination/Limits
    limit: Optional[int] = None
    offset: Optional[int] = 0
```

### Common Response Metadata
```python
class ReportMetadata(BaseModel):
    timestamp: datetime
    report_type: str
    filters_applied: dict
    total_records_analyzed: int
    data_quality_pct: float  # % of records with no validation errors
    generated_by: Optional[str] = None  # User who requested
```

---

## Part 6: Implementation Roadmap

### Phase 1: Foundation (Core Services)
- [ ] Create `KPIEngine` class (kpi_engine.py)
- [ ] Create `ReportService` class (report_service.py)
- [ ] Add `KPIDefinition` and `KPIValue` models
- [ ] Add standard filter parsing utilities
- [ ] Add response schema validation

### Phase 2: Basic Reports
- [ ] Implement `/api/reports/survey-summary/{form_id}`
- [ ] Implement `/api/reports/demographics`
- [ ] Implement `/api/reports/geo`

### Phase 3: KPI Reports
- [ ] Define all NGO-relevant KPIs in database
- [ ] Implement `/api/reports/indicators` (KPI dashboard)
- [ ] Implement `/api/reports/trends`
- [ ] Implement `/api/reports/program-comparison`

### Phase 4: Export & Performance
- [ ] Add export to PDF/Excel/CSV
- [ ] Implement report caching
- [ ] Add pagination support

### Phase 5: Documentation & Testing
- [ ] Document all endpoints
- [ ] Write integration tests
- [ ] Create sample report outputs

---

## Part 7: Guiding Principles

1. **Separation of Concerns**
   - `KPIEngine`: Computes KPIs
   - `ReportService`: Orchestrates reports
   - `FilterParser`: Handles filter logic
   - API routes: Only route + auth

2. **Reusability**
   - All KPIs use `KPIEngine` (no duplicate logic)
   - All reports use `ReportService` (consistent filtering)
   - All responses follow schemas

3. **Extensibility**
   - Easy to add new KPIs (register in database)
   - Easy to add new report types (inherit `BaseReport`)
   - Easy to add new visualizations (return different response formats)

4. **Standards Compliance**
   - Follow UN/SPHERE/IASC standards for humanitarian indicators
   - Use ISO 8601 for dates
   - Use standard statistical measures (mean, median, percentiles)

5. **Performance**
   - Cache KPI computations (daily, weekly, monthly)
   - Index frequently-filtered fields
   - Support pagination for large result sets
   - Lazy-load nested data

---

## Next Steps
1. **Review & Approve** this plan
2. **Define NGO-specific KPIs** (what KPIs matter for your NGO?)
3. **Implement Phase 1** (core services)
4. **Iterate through phases** with testing/validation at each step

---

**Document Status**: Ready for Review & Approval
