"""Pydantic schemas for request/response validation."""
from datetime import datetime
from typing import Any, Optional, Literal

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
    - metrics: list of metrics to compute per group
    """

    filters: Optional[dict[str, Any]] = None
    group_by: Optional[list[AggregateGroupBy]] = None
    metrics: list[AggregateMetric]


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