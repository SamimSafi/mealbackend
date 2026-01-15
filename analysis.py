from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from auth import get_current_active_user
from models import User
from typing import Optional, List
from datetime import date
from analysis_service import AnalysisService
from schemas import CrossTabResponse, StackedBarResponse, AnalysisFiltersResponse, AnalysisReportResponse

router = APIRouter(prefix="/api/analysis", tags=["Analysis"])

@router.get("/report", response_model=AnalysisReportResponse)
def get_analysis_report(
    form_id: str = Query(..., description="Internal Form ID (int) or Kobo Form ID (string)"),
    row: Optional[str] = Query(None, description="Categorical variable for rows (optional)"),
    column: Optional[str] = Query(None, description="Categorical variable for columns (optional)"),
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
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
            date_from=date_from,
            date_to=date_to,
            location=location,
            enumerator=enumerator,
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
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
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
            date_from=date_from,
            date_to=date_to,
            location=location,
            enumerator=enumerator,
            filter_field=filter_field,
            filter_value=filter_value
        )
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stacked-bar", response_model=StackedBarResponse)
def get_stacked_bar(
    form_id: str = Query(..., description="Internal Form ID (int) or Kobo Form ID (string)"),
    x: Optional[str] = Query(None, description="Variable for X-axis"),
    stack: Optional[str] = Query(None, description="Variable for stacking"),
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
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
            date_from=date_from,
            date_to=date_to,
            location=location,
            enumerator=enumerator,
            filter_field=filter_field,
            filter_value=filter_value
        )
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))
