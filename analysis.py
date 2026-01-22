from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from auth import get_current_active_user
from models import User
from typing import Optional, List
from datetime import date, datetime as dt
from analysis_service import AnalysisService
from schemas import (
    CrossTabResponse, StackedBarResponse, AnalysisFiltersResponse, 
    AnalysisReportResponse, NumericSummaryResponse, NumericDistributionResponse,
    OrdinalScaleAnalysisResponse, OrdinalFieldsResponse, OrdinalBatchAnalysisRequest, 
    OrdinalBatchAnalysisResponse, OrdinalTrendsResponse,
    MultiSelectAnalysisResponse, MultiSelectBatchRequest, MultiSelectBatchResponse,
    DetailedCrossTabResponse, TimeSeriesResponse
)

router = APIRouter(prefix="/api/analysis", tags=["Analysis"])

def parse_date_param(date_str: Optional[str]) -> Optional[date]:
    """Convert date string to date object, handling empty strings."""
    if not date_str or date_str.strip() == "":
        return None
    try:
        return dt.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {date_str}. Use YYYY-MM-DD")

@router.get("/report", response_model=AnalysisReportResponse)
def get_analysis_report(
    form_id: str = Query(..., description="Internal Form ID (int) or Kobo Form ID (string)"),
    row: Optional[str] = Query(None, description="Categorical variable for rows (optional)"),
    column: Optional[str] = Query(None, description="Categorical variable for columns (optional)"),
    date_from: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    location: Optional[str] = None,
    enumerator: Optional[str] = None,
    filter_field: Optional[str] = Query(None, description="Optional field to filter by"),
    filter_value: Optional[str] = Query(None, description="Value for the optional filter field"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Unified endpoint for analysis.
    Returns both cross-tabulation and stacked bar chart data.
    Row and Column variables are optional.
    """
    service = AnalysisService(db)
    try:
        return service.get_analysis_report(
            form_id=form_id,
            row_field=row,
            col_field=column,
            date_from=parse_date_param(date_from),
            date_to=parse_date_param(date_to),
            location=location if location else None,
            enumerator=enumerator if enumerator else None,
            filter_field=filter_field,
            filter_value=filter_value
        )
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/filters", response_model=AnalysisFiltersResponse)
def get_analysis_filters(
    form_id: str = Query(..., description="Internal Form ID (int) or Kobo Form ID (string)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get available categorical fields, locations, and enumerators for a form.
    """
    service = AnalysisService(db)
    try:
        return service.get_analysis_filters(form_id=form_id)
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/crosstab", response_model=CrossTabResponse)
def get_crosstab(
    form_id: str = Query(..., description="Internal Form ID (int) or Kobo Form ID (string)"),
    row: Optional[str] = Query(None, description="Categorical variable for rows"),
    column: Optional[str] = Query(None, description="Categorical variable for columns"),
    date_from: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    location: Optional[str] = None,
    enumerator: Optional[str] = None,
    filter_field: Optional[str] = Query(None, description="Optional field to filter by"),
    filter_value: Optional[str] = Query(None, description="Value for the optional filter field"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Accept two categorical variables (e.g., Gender vs Education).
    Ignore null or empty values.
    Return a pivot table with rows, columns, counts and totals.
    """
    service = AnalysisService(db)
    try:
        return service.get_crosstab(
            form_id=form_id,
            row_field=row,
            col_field=column,
            date_from=parse_date_param(date_from),
            date_to=parse_date_param(date_to),
            location=location if location else None,
            enumerator=enumerator if enumerator else None,
            filter_field=filter_field,
            filter_value=filter_value
        )
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/cross-tabulation", response_model=DetailedCrossTabResponse)
def get_cross_tabulation(
    form_id: int = Query(..., description="KoBo Form ID"),
    row_field: str = Query(..., description="Variable for rows (e.g., 'gender')"),
    column_field: str = Query(..., description="Variable for columns (e.g., 'education_level')"),
    date_from: Optional[date] = Query(None, description="Filter responses from date (ISO 8601)"),
    date_to: Optional[date] = Query(None, description="Filter responses to date (ISO 8601)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Cross-tabulation analysis for two categorical variables.
    
    Returns relationship analysis between two variables with:
    - Cross-tabulation table with counts and percentages
    - Row and column totals
    - Automatic insights
    - Metadata
    """
    service = AnalysisService(db)
    try:
        if not row_field or not column_field:
            raise HTTPException(
                status_code=400,
                detail="form_id, row_field, and column_field are required"
            )
        
        return service.get_detailed_crosstab(
            form_id=str(form_id),
            row_field=row_field,
            column_field=column_field,
            date_from=date_from,
            date_to=date_to
        )
    except HTTPException:
        raise
    except ValueError as e:
        if "invalid literal" in str(e).lower():
            raise HTTPException(
                status_code=422,
                detail="date_from and date_to must be in YYYY-MM-DD format"
            )
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stacked-bar", response_model=StackedBarResponse)
def get_stacked_bar(
    form_id: str = Query(..., description="Internal Form ID (int) or Kobo Form ID (string)"),
    x: Optional[str] = Query(None, description="Variable for X-axis"),
    stack: Optional[str] = Query(None, description="Variable for stacking"),
    date_from: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    location: Optional[str] = None,
    enumerator: Optional[str] = None,
    filter_field: Optional[str] = Query(None, description="Optional field to filter by"),
    filter_value: Optional[str] = Query(None, description="Value for the optional filter field"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Based on cross-tabulation output.
    Return percentage and count versions.
    Group data suitable for stacked bar visualization.
    """
    service = AnalysisService(db)
    try:
        return service.get_stacked_bar(
            form_id=form_id,
            x_field=x,
            stack_field=stack,
            date_from=parse_date_param(date_from),
            date_to=parse_date_param(date_to),
            location=location if location else None,
            enumerator=enumerator if enumerator else None,
            filter_field=filter_field,
            filter_value=filter_value
        )
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/numeric-summary", response_model=NumericSummaryResponse)
def get_numeric_summary(
    form_id: str = Query(..., description="Internal Form ID (int) or Kobo Form ID (string)"),
    field: str = Query(..., description="Numeric field to summarize"),
    date_from: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    location: Optional[str] = None,
    enumerator: Optional[str] = None,
    filter_field: Optional[str] = Query(None, description="Optional field to filter by"),
    filter_value: Optional[str] = Query(None, description="Value for the optional filter field"),
    allow_negative: bool = Query(False, description="Whether to include negative values"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get summary statistics for a numeric field.
    """
    service = AnalysisService(db)
    try:
        return service.get_numeric_summary(
            form_id=form_id,
            field=field,
            date_from=parse_date_param(date_from),
            date_to=parse_date_param(date_to),
            location=location if location else None,
            enumerator=enumerator if enumerator else None,
            filter_field=filter_field,
            filter_value=filter_value,
            allow_negative=allow_negative
        )
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/numeric-distribution", response_model=NumericDistributionResponse)
def get_numeric_distribution(
    form_id: int = Query(..., description="Kobo Form ID"),
    field: str = Query(..., description="Numeric field name"),
    allow_negative: bool = Query(False, description="Remove negative values (default false)"),
    remove_outliers: bool = Query(False, description="Remove outliers from calculation (default false)"),
    date_from: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    location: Optional[str] = None,
    enumerator: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get numeric distribution analysis for a field.
    
    Returns quartiles, IQR, mean, std dev, and outliers.
    
    Parameters:
    - form_id: Kobo Form ID (required)
    - field: Numeric field name (required)
    - allow_negative: Whether to include negative values (default false)
    - remove_outliers: Whether to exclude outliers from calculation (default false)
    - date_from: Optional ISO date filter
    - date_to: Optional ISO date filter
    - location: Optional location filter
    - enumerator: Optional enumerator filter
    """
    service = AnalysisService(db)
    try:
        return service.get_numeric_distribution(
            form_id=str(form_id),
            field=field,
            date_from=parse_date_param(date_from),
            date_to=parse_date_param(date_to),
            location=location if location else None,
            enumerator=enumerator if enumerator else None,
            allow_negative=allow_negative,
            remove_outliers=remove_outliers
        )
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ordinal-scale", response_model=OrdinalScaleAnalysisResponse)
def get_ordinal_scale_analysis(
    form_id: str = Query(..., description="Kobo Form ID"),
    field: str = Query(..., description="Ordinal field name"),
    date_from: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    location: Optional[str] = None,
    enumerator: Optional[str] = None,
    include_null: bool = Query(False, description="Include null responses"),
    decimal_places: int = Query(1, ge=0, le=5),
    response_type: Optional[str] = Query(None, description="all/positive/neutral/negative"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Analyze ordinal/Likert scale responses with order preservation.
    """
    service = AnalysisService(db)
    try:
        return service.get_ordinal_scale_analysis(
            form_id=form_id,
            field=field,
            date_from=parse_date_param(date_from),
            date_to=parse_date_param(date_to),
            location=location if location else None,
            enumerator=enumerator if enumerator else None,
            include_null=include_null,
            decimal_places=decimal_places,
            response_type=response_type
        )
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/forms/{form_id}/ordinal-fields", response_model=OrdinalFieldsResponse)
def get_ordinal_fields(
    form_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    List ordinal fields with options from form schema.
    """
    service = AnalysisService(db)
    try:
        return service.get_ordinal_fields(form_id=form_id)
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ordinal-batch", response_model=OrdinalBatchAnalysisResponse)
def get_ordinal_batch_analysis(
    request: OrdinalBatchAnalysisRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Analyze multiple ordinal fields simultaneously.
    """
    service = AnalysisService(db)
    try:
        return service.get_ordinal_batch_analysis(request)
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ordinal-trends", response_model=OrdinalTrendsResponse)
def get_ordinal_trends(
    form_id: str = Query(..., description="Kobo Form ID"),
    field: str = Query(..., description="Ordinal field name"),
    granularity: str = Query("month", description="day/week/month/year"),
    date_from: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    location: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Analyze trends of ordinal scores over time.
    """
    service = AnalysisService(db)
    try:
        return service.get_ordinal_trends(
            form_id=form_id,
            field=field,
            granularity=granularity,
            date_from=parse_date_param(date_from),
            date_to=parse_date_param(date_to),
            location=location if location else None
        )
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/time-series", response_model=TimeSeriesResponse)
def get_time_series(
    form_id: str = Query(..., description="Internal Form ID (int) or Kobo Form ID (string)"),
    date_from: str = Query(..., description="Start date (YYYY-MM-DD)"),
    date_to: str = Query(..., description="End date (YYYY-MM-DD)"),
    group_by: str = Query("day", description="day, week, month, quarter"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get time-series analysis of submissions.
    """
    service = AnalysisService(db)
    try:
        # Validate group_by
        if group_by not in ["day", "week", "month", "quarter"]:
            raise HTTPException(status_code=422, detail="Invalid group_by value. Use day, week, month, or quarter.")
        
        return service.get_time_series(
            form_id=form_id,
            date_from=parse_date_param(date_from),
            date_to=parse_date_param(date_to),
            group_by=group_by
        )
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/multiselect")
def get_multiselect_analysis(
    form_id: str = Query(..., description="Kobo Form ID"),
    field: str = Query(..., description="Field name (any type: ordinal, multi-select, etc.)"),
    date_from: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    location: Optional[str] = Query(None, description="Filter by location"),
    enumerator: Optional[str] = Query(None, description="Filter by enumerator"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Analyze any field type with auto-detection (ordinal, multi-select, etc.).
    Returns appropriate response format based on field type:
    - For select_multiple: MultiSelectAnalysisResponse with selection percentages
    - For ordinal/select_one: OrdinalScaleAnalysisResponse with sentiment analysis
    """
    service = AnalysisService(db)
    try:
        return service.get_multiselect_analysis(
            form_id=form_id,
            field=field,
            date_from=parse_date_param(date_from),
            date_to=parse_date_param(date_to),
            location=location if location else None,
            enumerator=enumerator if enumerator else None
        )
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/multiselect-batch")
def get_multiselect_batch_analysis(
    request: MultiSelectBatchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Analyze multiple fields of any type simultaneously with auto-detection.
    Each field's response format depends on its type:
    - select_multiple: MultiSelectAnalysisResponse
    - ordinal/select_one: OrdinalScaleAnalysisResponse
    """
    service = AnalysisService(db)
    try:
        return service.get_multiselect_batch_analysis(request)
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))
