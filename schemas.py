"""Pydantic schemas for request/response validation."""
from datetime import datetime, date
from typing import Any, Optional, Literal, List, Dict

from pydantic import BaseModel, EmailStr, Field


# User Schemas
class UserBase(BaseModel):
    """Base user schema."""

    username: str
    email: EmailStr
    full_name: Optional[str] = None
    role: str = "viewer"


class UserCreate(UserBase):
    """User creation schema."""

    password: str = Field(..., min_length=6)


class UserUpdate(BaseModel):
    """User update schema."""

    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None


class UserResponse(UserBase):
    """User response schema."""

    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Auth Schemas
class Token(BaseModel):
    """Token schema."""

    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """Token data schema."""

    username: Optional[str] = None


class LoginRequest(BaseModel):
    """Login request schema."""

    username: str
    password: str


# Form Schemas
class FormBase(BaseModel):
    """Base form schema."""

    title: str
    description: Optional[str] = None
    category: Optional[str] = None


class FormCreate(FormBase):
    """Form creation schema."""

    kobo_form_id: str
    form_schema: Optional[dict[str, Any]] = None


class FormUpdate(BaseModel):
    """Form update schema."""

    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    is_active: Optional[bool] = None


class FormResponse(FormBase):
    """Form response schema."""

    id: int
    kobo_form_id: str
    is_active: bool
    last_synced_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    submission_count: Optional[int] = None

    class Config:
        from_attributes = True


# Submission Schemas
class SubmissionBase(BaseModel):
    """Base submission schema."""

    submission_data: dict[str, Any]


class SubmissionResponse(SubmissionBase):
    """Submission response schema."""

    id: int
    form_id: int
    kobo_submission_id: str
    submitted_at: Optional[datetime] = None
    location_lat: Optional[float] = None
    location_lng: Optional[float] = None
    location_name: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# Indicator Schemas
class IndicatorBase(BaseModel):
    """Base indicator schema."""

    name: str
    description: Optional[str] = None
    indicator_type: str
    computation_rule: Optional[dict[str, Any]] = None


class IndicatorCreate(IndicatorBase):
    """Indicator creation schema."""

    form_id: int
    value: Optional[float] = None
    indicator_metadata: Optional[dict[str, Any]] = None


class IndicatorResponse(IndicatorBase):
    """Indicator response schema."""

    id: int
    form_id: int
    value: Optional[float] = None
    indicator_metadata: Optional[dict[str, Any]] = None
    computed_at: datetime
    created_at: datetime

    class Config:
        from_attributes = True


# Dashboard Schemas
class DashboardSummary(BaseModel):
    """Dashboard summary schema."""

    total_forms: int
    total_submissions: int
    total_indicators: int
    recent_submissions: int
    forms_by_category: dict[str, int]
    submissions_by_date: list[dict[str, Any]]


class IndicatorDashboardData(BaseModel):
    """Indicator dashboard data schema."""

    indicators: list[IndicatorResponse]
    trends: list[dict[str, Any]]
    by_category: dict[str, list[IndicatorResponse]]


class AccountabilityDashboardData(BaseModel):
    """Accountability dashboard data schema."""

    complaints: list[SubmissionResponse]
    complaints_by_status: dict[str, int]
    complaints_by_location: list[dict[str, Any]]
    trends: list[dict[str, Any]]


# Permission Schemas
class PermissionCreate(BaseModel):
    """Permission creation schema."""

    resource: str
    action: str


class PermissionResponse(BaseModel):
    """Permission response schema."""

    id: int
    user_id: int
    resource: str
    action: str
    created_at: datetime

    class Config:
        from_attributes = True


# Sync Schemas
class SyncRequest(BaseModel):
    """Sync request schema."""

    form_id: Optional[int] = None
    sync_type: str = "incremental"  # "full" or "incremental"


class SyncLogResponse(BaseModel):
    """Sync log response schema."""

    id: int
    form_id: Optional[int] = None
    sync_type: str
    status: str
    records_processed: int
    records_added: int
    records_updated: int
    error_message: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# Webhook Schemas
class WebhookPayload(BaseModel):
    """Webhook payload schema."""

    form_id: Optional[str] = None
    submission_id: Optional[str] = None
    event_type: str  # e.g., "submission.created", "submission.updated"
    data: Optional[dict[str, Any]] = None


# Chart Data Request Schema
class ChartDataRequest(BaseModel):
    """Chart data request schema."""

    chart_type: str = "bar"  # bar, line, pie, donut, stacked_bar, diverging_stacked_bar, histogram, scatter
    dimension: str  # Primary dimension to group by
    secondary_dimension: Optional[str] = None  # For stacked charts, scatter plots
    filters: Optional[dict[str, Any]] = None
    time_dimension: Optional[str] = None  # For line charts (date field)
    bin_count: Optional[int] = 10  # For histograms


# Aggregate / Pivot Request Schema
class AggregateGroupBy(BaseModel):
    """Grouping definition for aggregate endpoint."""

    field: str


class AggregateMetric(BaseModel):
    """Metric definition for aggregate endpoint."""

    type: Literal["count", "sum", "avg", "percentage"]
    field: str  # e.g. "gender", "age_group", or "*" for count all
    value: Optional[str] = None  # for percentage metrics
    alias: str  # name used in response rows


class AggregateRequest(BaseModel):
    """
    Generic aggregate request used by /form/{id}/aggregate.

    - filters: equality filters on cleaned/submission data
    - group_by: list of fields to group by
    - metrics: list of metrics to compute per group (optional; if empty returns general aggregate)
    """

    filters: Optional[dict[str, Any]] = None
    group_by: Optional[list[AggregateGroupBy]] = None
    metrics: Optional[list[AggregateMetric]] = None


# Generic chart request/response for raw statistical analysis
class BoxPlotRequest(BaseModel):
    """Request body for /api/charts/box_plot."""

    form_id: int
    column: str
    filters: Optional[dict[str, Any]] = None


class BoxPlotResponse(BaseModel):
    """Five-number summary + outliers for a numeric column."""

    form_id: int
    column: str
    q1: float
    median: float
    q3: float
    whisker_min: float
    whisker_max: float
    outliers: list[float]
    iqr: Optional[float] = 0
    lower_bound: Optional[float] = 0
    upper_bound: Optional[float] = 0
    count: Optional[int] = 0
    stats: Optional[dict[str, Any]] = None


class BarChartRequest(BaseModel):
    """Request body for /api/charts/bar_chart."""

    form_id: int
    group_by: Optional[str] = None  # Optional: auto-detected from filters if not provided
    filters: Optional[dict[str, Any]] = None


class BarChartItem(BaseModel):
    """Single bar/category in bar chart response."""

    category: str
    count: int


class BarChartResponse(BaseModel):
    """Response body for /api/charts/bar_chart."""

    form_id: int
    group_by: str
    items: list[BarChartItem]
    total_submissions: int  # Total submissions included in the chart
    unique_values: int  # Number of distinct categories
    field_label: Optional[str] = None  # Human-readable label for the field


# Daily data load schema
class DailyDataResponse(BaseModel):
    """Response body for /api/data/load (records for a specific date)."""

    date: str
    total: int
    submissions: list[SubmissionResponse]


# Organization Schemas
class OrganizationBase(BaseModel):
    """Base organization schema."""

    name: str
    description: Optional[str] = None


class OrganizationCreate(OrganizationBase):
    """Organization creation schema."""

    pass


class OrganizationResponse(OrganizationBase):
    """Organization response schema."""

    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Branding Schemas
class BrandingBase(BaseModel):
    """Base branding schema."""

    company_name: str
    primary_color: Optional[str] = None
    secondary_color: Optional[str] = None
    description: Optional[str] = None


class BrandingCreate(BrandingBase):
    """Branding creation schema."""

    organization_id: int


# JSON variant for branding that may include a base64-encoded file
class BrandingJSON(BrandingBase):
    file_base64: Optional[str] = None
    file_name: Optional[str] = None


class BrandingUpdate(BaseModel):
    """Branding update schema."""

    company_name: Optional[str] = None
    primary_color: Optional[str] = None
    secondary_color: Optional[str] = None
    description: Optional[str] = None


class BrandingResponse(BrandingBase):
    """Branding response schema."""

    id: int
    organization_id: int
    logo_path: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class BrandingDetailResponse(BrandingResponse):
    """Detailed branding response with organization info."""

    organization: OrganizationResponse


# Report Schemas (Filters, Requests, Responses)
class LocationFilterRequest(BaseModel):
    """Geographic dimension filter."""
    
    dimension_1: Optional[str] = None
    dimension_2: Optional[str] = None
    dimension_3: Optional[str] = None


class ReportFiltersRequest(BaseModel):
    """Standard filters for all reports."""
    
    date_from: Optional[str] = None  # ISO date format
    date_to: Optional[str] = None
    locations: Optional[list[LocationFilterRequest]] = []
    form_ids: Optional[list[int]] = []
    field_filters: Optional[dict[str, Any]] = {}
    exclude_incomplete: bool = False


class ReportMetadataResponse(BaseModel):
    """Metadata included in all report responses."""
    
    timestamp: datetime
    report_type: str
    filters_applied: dict[str, Any]
    total_submissions_analyzed: int
    total_submissions_in_filter: int
    data_quality_pct: float
    generated_in_ms: Optional[int] = None


# KPI Definition & Value Schemas
class KPIDefinitionResponse(BaseModel):
    """KPI definition response."""
    
    id: int
    kpi_code: str
    label: str
    description: Optional[str]
    unit: str
    baseline_value: Optional[float]
    target_value: Optional[float]
    report_category: str
    sub_category: Optional[str]
    is_custom: bool
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class KPIComputationResponse(BaseModel):
    """Single KPI computation result."""
    
    kpi_code: str
    kpi_label: str
    value: float
    unit: str
    baseline: Optional[float]
    target: Optional[float]
    progress_to_target_pct: Optional[float]  # (value - baseline) / (target - baseline) * 100
    sample_size: int
    valid_sample_size: int
    trend: Optional[str]  # up, down, stable, no_data
    category: str
    sub_category: Optional[str]


class QuestionSummaryResponse(BaseModel):
    """Summary for a single question in survey."""
    
    field: str
    field_label: str
    field_type: str
    response_type: str  # categorical, numeric, text, date
    valid_responses: int
    null_responses: int
    
    # For categorical
    options: Optional[list[dict[str, Any]]] = None
    
    # For numeric
    statistics: Optional[dict[str, float]] = None


class SurveySummaryResponse(BaseModel):
    """Survey summary report."""
    
    metadata: ReportMetadataResponse
    form_id: int
    form_title: str
    summary: dict[str, Any]
    question_summaries: list[QuestionSummaryResponse]


class IndicatorReportResponse(BaseModel):
    """Indicator/KPI report."""
    
    metadata: ReportMetadataResponse
    kpis: list[KPIComputationResponse]
    by_category: dict[str, list[KPIComputationResponse]]
    highlights: Optional[list[dict[str, Any]]] = None


class DemographicsReportResponse(BaseModel):
    """Demographics report."""
    
    metadata: ReportMetadataResponse
    demographics: dict[str, Any]


class GeoPointResponse(BaseModel):
    """Single geographic point with submission count."""
    
    lat: float
    lng: float
    count: int
    location_name: Optional[str] = None


class GeospatialReportResponse(BaseModel):
    """Geospatial report with maps and coverage."""
    
    metadata: ReportMetadataResponse
    points: list[GeoPointResponse]
    coverage: dict[str, Any]
    bounds: dict[str, float]


class TrendDataPointResponse(BaseModel):
    """Single point in trend data."""
    
    period: str
    period_label: str
    value: float
    sample_size: int
    baseline: Optional[float]
    target: Optional[float]


class TrendReportResponse(BaseModel):
    """Trend report for KPI over time."""
    
    metadata: ReportMetadataResponse
    kpi_code: str
    kpi_label: str
    time_granularity: str  # daily, weekly, monthly
    trend_data: list[TrendDataPointResponse]
    summary: dict[str, Any]


class ProgramComparisonItemResponse(BaseModel):
    """Single item in program comparison."""
    
    item_id: int
    item_label: str
    kpi_value: float
    target: Optional[float]
    baseline: Optional[float]
    sample_size: int
    status: str  # on_track, behind, ahead, no_data


class ProgramComparisonResponse(BaseModel):
    """Program comparison report."""
    
    metadata: ReportMetadataResponse
    comparison_dimension: str
    kpi_code: str
    items: list[ProgramComparisonItemResponse]
    aggregate: dict[str, float]


class TableColumnDefinition(BaseModel):
    """Definition of a table column."""
    
    name: str
    label: str
    type: str


class TableViewResponse(BaseModel):
    """Table view response for form data."""
    
    form_id: int
    form_title: str
    total_count: int
    columns: list[TableColumnDefinition]
    rows: list[dict[str, Any]]
    skip: int
    limit: int
    has_more: bool


class PolarAreaItem(BaseModel):
    """Single item in polar area chart."""
    
    label: str
    value: int
    percentage: float


class PolarAreaChartRequest(BaseModel):
    """Request body for polar area chart."""
    
    form_id: int
    field: str
    filters: Optional[dict[str, Any]] = None


class PolarAreaChartResponse(BaseModel):
    """Response body for polar area chart."""
    
    form_id: int
    field_name: str
    field_label: str
    items: list[PolarAreaItem]
    total_submissions: int
    total_with_data: int
    without_data: int
    unique_values: int


class GenderRatioItem(BaseModel):
    """Single gender item in ratio."""
    
    gender: str
    count: int
    percentage: float


class AggregateReportResponse(BaseModel):
    """Response for form aggregate report."""
    
    form_id: int
    total_survey: int
    todays_submissions: int
    total_provinces: int
    gender_ratio: list[GenderRatioItem]
    generated_at: datetime


class CrossTabResponse(BaseModel):
    """Cross-tabulation response."""
    rows: list[str]
    columns: list[str]
    data: list[list[int]]
    row_totals: list[int]
    column_totals: list[int]
    grand_total: int
    total_responses: int
    missing_count: int
    missing_percentage: float


class StackedBarItem(BaseModel):
    """Item for stacked bar chart."""
    category: str
    values: dict[str, int]
    percentages: dict[str, float]
    total: int


class StackedBarResponse(BaseModel):
    """Stacked bar chart response."""
    x_axis: list[str]
    stacks: list[str]
    items: list[StackedBarItem]
    total_responses: int
    missing_count: int
    missing_percentage: float


class AnalysisReportResponse(BaseModel):
    """Unified analysis report response."""
    crosstab: CrossTabResponse
    stacked_bar: StackedBarResponse


class AnalysisFiltersResponse(BaseModel):
    """Available filters for analysis."""
    categorical_fields: list[dict[str, Any]]  # list of {"name": "field_name", "label": "Label", "type": "type"}
    numeric_fields: list[dict[str, Any]]      # For Histogram, Scatter, Box Plot
    date_fields: list[dict[str, Any]]         # For Line Chart
    locations: list[str]
    enumerators: list[str]
    date_range: dict[str, Optional[str]]


class NumericStatistics(BaseModel):
    """Calculated statistics for numeric fields."""
    mean: float
    median: float
    min: float
    max: float
    std_dev: Optional[float] = None
    q1: Optional[float] = None
    q3: Optional[float] = None
    iqr: Optional[float] = None


class NumericSummaryResponse(BaseModel):
    """Response for numeric summary statistics."""
    field: str
    valid_count: int
    excluded_count: int
    statistics: NumericStatistics


class Distribution(BaseModel):
    """Distribution metrics for numeric fields."""
    min: float
    q1: float
    median: float
    q3: float
    max: float
    iqr: float


class NumericDistributionResponse(BaseModel):
    """Response for numeric distribution analysis."""
    field: str
    valid_count: int
    excluded_count: int
    distribution: Optional[Distribution] = None
    statistics: Optional[dict[str, float]] = None
    outliers: Optional[list[float]] = None
    message: Optional[str] = None


# Ordinal/Likert Scale Schemas

class OrdinalFieldOption(BaseModel):
    label: str
    value: str

class OrdinalFieldInfo(BaseModel):
    name: str
    label: str
    options: List[OrdinalFieldOption]

class OrdinalFieldsResponse(BaseModel):
    form_id: str
    fields: List[OrdinalFieldInfo]

class OrdinalResponseItem(BaseModel):
    option: str
    count: int
    percentage: float
    order: int
    category: str

class OrdinalAnalysisSummary(BaseModel):
    positive_percentage: float
    negative_percentage: float
    neutral_percentage: float
    net_score: float
    mean_score: Optional[float] = None
    mode: Optional[str] = None
    consistency_index: Optional[float] = None

class OrdinalAnalysisMetadata(BaseModel):
    form_name: str
    question_text: str
    options_order: List[str]
    generated_at: datetime
    filters_applied: Dict[str, Any]

class OrdinalScaleAnalysisResponse(BaseModel):
    field: str
    total_responses: int
    excluded_count: int
    valid_responses: int
    responses: List[OrdinalResponseItem]
    analysis: OrdinalAnalysisSummary
    metadata: OrdinalAnalysisMetadata
    message: Optional[str] = None

class OrdinalBatchAnalysisRequest(BaseModel):
    form_id: str
    fields: List[str]
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    location: Optional[str] = None
    enumerator: Optional[str] = None
    include_null: bool = False
    decimal_places: int = 1

class OrdinalBatchAnalysisResponse(BaseModel):
    form_id: str
    results: Dict[str, OrdinalScaleAnalysisResponse]


class OrdinalTrendItem(BaseModel):
    period: str
    positive_percentage: float
    negative_percentage: float
    neutral_percentage: float
    net_score: float
    count: int

class OrdinalTrendsResponse(BaseModel):
    field: str
    granularity: str
    trends: List[OrdinalTrendItem]


# Multi-Select Analysis Schemas

class MultiSelectOption(BaseModel):
    option: str
    count: int
    percentage: float
    respondent_percentage: float

class MultiSelectAnalysisResponse(BaseModel):
    field: str
    total_respondents: int
    respondents_with_data: int
    excluded_count: int
    total_selections: int
    options: List[MultiSelectOption]
    metadata: Dict[str, Any]
    message: Optional[str] = None

class MultiSelectBatchRequest(BaseModel):
    form_id: str
    fields: List[str]
    date_from: Optional[date] = None
    date_to: Optional[date] = None

class MultiSelectBatchResponse(BaseModel):
    form_id: str
    results: Dict[str, MultiSelectAnalysisResponse]


class CrossTabColumnItem(BaseModel):
    label: str
    count: int
    percentage: float


class CrossTabRowItem(BaseModel):
    label: str
    count: int
    columns: List[CrossTabColumnItem]


class CrossTabTable(BaseModel):
    rows: List[CrossTabRowItem]
    column_totals: Dict[str, int]
    grand_total: int


class CrossTabMetadata(BaseModel):
    generated_at: datetime
    date_filter_applied: bool
    form_name: str


class DetailedCrossTabResponse(BaseModel):
    success: bool
    form_id: int
    row_field: str
    column_field: str
    total_responses: int
    excluded_count: int
    table: CrossTabTable
    insights: List[str]
    metadata: CrossTabMetadata


class TimeSeriesDataPoint(BaseModel):
    period: str
    label: str
    count: int
    cumulative: int


class TimeSeriesResponse(BaseModel):
    success: bool
    form_id: int
    form_name: str
    date_from: str
    date_to: str
    group_by: str
    total_submissions: int
    average_per_period: float
    trend: str
    data: List[TimeSeriesDataPoint]
    insights: List[str]


class CrossTabErrorResponse(BaseModel):
    success: bool = False
    error: str
    message: str
    details: Optional[Dict[str, Any]] = None
    available_fields: Optional[List[str]] = None
    suggestion: Optional[str] = None
