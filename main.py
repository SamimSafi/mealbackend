"""FastAPI main application."""
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import logging
import json
import shutil
from contextlib import asynccontextmanager
from typing import Dict, Set
from sqlalchemy import text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Avoid running initialization at import time. Initialization is handled
# in the FastAPI `lifespan` context manager or when running as a script.
    
from fastapi import FastAPI, HTTPException, Depends, status, WebSocket, WebSocketDisconnect, Request, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from jose import jwt

from config import settings
from database import get_db, init_db, migrate_db, SessionLocal
from models import (
    User, Form as FormModel, Submission, Indicator, SyncLog, UserPermission, UserFormAccess,
    RawSubmission, Organization, Branding, KPIDefinition, KPIValue, ReportCache, FormFieldMapping, Document
)
from typing import Optional
from schemas import (
    UserCreate,
    UserResponse,
    UserUpdate,
    ChangePasswordRequest,
    ResetPasswordRequest,
    Token,
    LoginRequest,
    FormResponse,
    FormFieldMappingResponse,
    FormFieldMappingUpdate,
    SubmissionResponse,
    IndicatorResponse,
    DashboardSummary,
    IndicatorDashboardData,
    AccountabilityDashboardData,
    SyncRequest,
    SyncLogResponse,
    SyncProgressResponse,
    WebhookPayload,
    PermissionCreate,
    PermissionResponse,
    UserFormAccessCreate,
    BulkFormAccessRequest,
    UserFormAccessResponse,
    ChartDataRequest,
    AggregateRequest,
    BoxPlotRequest,
    BoxPlotResponse,
    BarChartRequest,
    BarChartResponse,
    BarChartItem,
    DailyDataResponse,
    OrganizationCreate,
    OrganizationResponse,
    BrandingCreate,
    BrandingUpdate,
    BrandingResponse,
    BrandingDetailResponse,
    BrandingJSON,
    ReportFiltersRequest,
    SurveySummaryResponse,
    IndicatorReportResponse,
    DemographicsReportResponse,
    GeospatialReportResponse,
    TrendReportResponse,
    ProgramComparisonResponse,
    KPIDefinitionResponse,
    TableViewResponse,
    TableColumnDefinition,
    PolarAreaItem,
    PolarAreaChartRequest,
    PolarAreaChartResponse,
    AggregateReportResponse,
    GenderRatioItem,
    GroupBy,
    TimeSeriesMode,
    TimeSeriesResponse,
)
from dynamic_field_detector import (
    detect_province_field,
    detect_gender_field,
    get_field_data,
)
from auth import (
    get_current_active_user,
    get_current_user_for_sse,
    get_password_hash,
    create_access_token,
    verify_password,
    require_role,
    get_current_user,
    check_form_access,
)
from kobo_client import KoboClient
from etl import ETLPipeline
from datetime import datetime, timedelta, date as date_type
from typing import Optional, Any
import asyncio
import threading
from fastapi.responses import StreamingResponse, JSONResponse

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

import sync_progress_store
from discover import discover_router
from analysis import router as analysis_router
from report_service import ReportService
from report_filters import FilterContext, LocationFilter
from kpi_engine import KPIEngine



@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown."""
    try:
        logger.info("Application starting...")
        logger.info("Running database migrations and initialization...")
        migrate_db()
        logger.info("Database ready")
            
    except Exception as e:
        logger.error(f"Database initialization error: {e}", exc_info=True)
    
    yield
    
    logger.info("Shutting down...")

# Create FastAPI app
app = FastAPI(
    title="Kobo Dashboard API",
    description="API for Kobo Toolbox data dashboard",
    version="1.0.0",
    lifespan=lifespan,
)

# Force migration on import for environments where lifespan isn't triggered
migrate_db()


# CORS middleware
app.add_middleware(
    CORSMiddleware,
   allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://samimsafi12-001-site1.site4future.com",
        "https://samimsafi12-001-site1.site4future.com",
        "https://samimsafi.pythonanywhere.com",
        "https://samimsafi.pythonanywhere.com/",  # Add with trailing slash
        "http://samimsafi.pythonanywhere.com",    # HTTP version
        "http://samimsafi.pythonanywhere.com/",   # HTTP with trailing slash
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],  # Allows Authorization header
    expose_headers=["*"],  # Expose headers to browser
)


uploads_dir = Path("uploads")
uploads_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")


# Discovery endpoints (auto-detect Back4App URL)
app.include_router(discover_router)
app.include_router(analysis_router)



# ============================================================================
# Auth Endpoints
# ============================================================================
@app.get("/api/auth/test-me-fixed")
def test_me_fixed(
    request: Request,
    db: Session = Depends(get_db)
):
    """Test endpoint with PythonAnywhere header fix."""
    
    headers = dict(request.headers)
    
    # Debug: Show all headers
    all_headers = {}
    for key, value in headers.items():
        all_headers[key] = value
    
    # Check for authorization in all possible formats
    auth_header = None
    for key in headers.keys():
        if 'authorization' in key.lower():
            auth_header = headers[key]
            auth_key_found = key
            break
    
    auth_info = {
        "all_headers": all_headers,
        "auth_header_found": auth_header is not None,
        "auth_key": auth_key_found if auth_header else None,
        "auth_header_value": f"{auth_header[:50]}..." if auth_header and len(auth_header) > 50 else auth_header
    }
    
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:]
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            username = payload.get("sub")
            user = db.query(User).filter(User.username == username).first() if username else None
            
            return {
                **auth_info,
                "authenticated": True,
                "username": username,
                "user_found": user is not None
            }
        except Exception as e:
            return {
                **auth_info,
                "authenticated": False,
                "error": str(e)
            }
    
    return {
        **auth_info,
        "authenticated": False,
        "error": "No valid Authorization header found"
    }
@app.get("/api/debug/raw-headers")
async def debug_raw_headers(request: Request):
    """Debug endpoint to see all raw headers."""
    headers = dict(request.headers)
    
    return {
        "all_headers": headers,
        "has_authorization": "authorization" in headers or "Authorization" in headers,
        "authorization_value": headers.get("authorization") or headers.get("Authorization"),
        "header_keys": list(headers.keys())
    }
    
@app.get("/api/debug/test-token")
async def test_token_decoding(token: str):
    """Test if token can be decoded with current SECRET_KEY."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return {
            "valid": True,
            "username": payload.get("sub"),
            "expires": payload.get("exp"),
            "expires_human": datetime.fromtimestamp(payload.get("exp")).isoformat() if payload.get("exp") else None,
            "current_time": datetime.now().isoformat()
        }
    except jwt.ExpiredSignatureError:
        return {
            "valid": False,
            "error": "Token has expired"
        }
    except Exception as e:
        return {
            "valid": False,
            "error": str(e),
            "error_type": type(e).__name__
        }
        
@app.get("/api/debug/db-check")
async def debug_db_check(db: Session = Depends(get_db)):
    """Check database connection and admin user."""
    try:
        # Test database connection - SQLAlchemy 2.x requires text() wrapper
        db.execute(text("SELECT 1"))
        
        # Count users
        user_count = db.query(User).count()
        
        # Get admin user
        admin = db.query(User).filter(User.username == "admin").first()
        
        # Check if tables exist
        from sqlalchemy import inspect
        inspector = inspect(db.get_bind())
        tables = inspector.get_table_names()
        
        return {
            "database_status": "connected",
            "database_path": settings.DATABASE_URL,
            "tables": tables,
            "user_count": user_count,
            "admin_user_exists": admin is not None,
            "admin_user_active": admin.is_active if admin else False,
            "admin_user_role": admin.role if admin else None
        }
    except Exception as e:
        import traceback
        return {
            "database_status": "error",
            "error": str(e),
            "error_details": traceback.format_exc(),
            "database_url": settings.DATABASE_URL
        }
        
@app.get("/api/debug/user-check")
async def debug_user_check(username: str = "admin", db: Session = Depends(get_db)):
    """Check if a user exists in database."""
    user = db.query(User).filter(User.username == username).first()
    
    if not user:
        return {
            "exists": False,
            "message": f"User '{username}' not found in database"
        }
    
    return {
        "exists": True,
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat() if user.created_at else None
    }
    
@app.post("/api/debug/token")
def debug_token(token: str):
    """Debug endpoint to test token decoding."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return {
            "valid": True,
            "username": payload.get("sub"),
            "expires": payload.get("exp"),
            "full_payload": payload
        }
    except Exception as e:
        return {
            "valid": False,
            "error": str(e)
        }

@app.post("/api/auth/login", response_model=Token)
def login(login_data: LoginRequest, db: Session = Depends(get_db)):
    """Login endpoint that accepts a JSON body with username/password."""
    try:
        logger.info(f"[LOGIN] Attempting login for user: {login_data.username}")
        
        user = db.query(User).filter(User.username == login_data.username).first()
        if not user:
            logger.warning(f"[LOGIN] User not found: {login_data.username}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
            )
        
        logger.info(f"[LOGIN] User found: {user.username}, checking password...")
        logger.info(f"[LOGIN] Hash length: {len(user.hashed_password) if user.hashed_password else 0}")
        
        if not verify_password(login_data.password, user.hashed_password):
            logger.warning(f"[LOGIN] Password verification failed for: {login_data.username}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
            )
        
        logger.info(f"[LOGIN] Password verified for: {login_data.username}")
        
        if not user.is_active:
            logger.warning(f"[LOGIN] User is inactive: {login_data.username}")
            raise HTTPException(status_code=400, detail="Inactive user")
        
        logger.info(f"[LOGIN] Creating access token for: {login_data.username}")
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.username}, expires_delta=access_token_expires
        )
        logger.info(f"[LOGIN] Login successful for: {login_data.username}")
        return {"access_token": access_token, "token_type": "bearer"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[LOGIN] Unexpected error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Login error: {str(e)}"
        )


@app.post("/api/auth/register", response_model=UserResponse)
def register(user_data: UserCreate, db: Session = Depends(get_db)):
    """Register a new user."""
    # Check if username exists
    if db.query(User).filter(User.username == user_data.username).first():
        raise HTTPException(status_code=400, detail="Username already registered")
    
    # Check if email exists
    if db.query(User).filter(User.email == user_data.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create user
    user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=get_password_hash(user_data.password),
        full_name=user_data.full_name,
        role=user_data.role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@app.get("/api/auth/me", response_model=UserResponse)
def get_current_user_info(
    request: Request,
    db: Session = Depends(get_db)
):
    """Get current user information - PythonAnywhere compatible."""
    
    # PythonAnywhere sends headers with 'http_' prefix
    # Look for authorization header in any format
    headers = dict(request.headers)
    
    # Check for 'http_authorization' (PythonAnywhere format)
    auth_header = headers.get("http_authorization") or headers.get("authorization") or headers.get("Authorization")
    
    if not auth_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication scheme",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = auth_header[7:]  # Remove "Bearer "
    
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username = payload.get("sub")
        
        if not username:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        user = db.query(User).filter(User.username == username).first()
        
        if not user:
            # Fallback to admin
            user = db.query(User).filter(User.username == "admin").first()
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
        
        return user
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


@app.post("/api/auth/change-password")
def change_password(
    password_data: ChangePasswordRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Change current user's password."""
    if not verify_password(password_data.old_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect old password",
        )
    
    current_user.hashed_password = get_password_hash(password_data.new_password)
    current_user.updated_at = datetime.utcnow()
    db.commit()
    return {"detail": "Password changed successfully"}


# ============================================================================
# Base Data Endpoint (per-day survey records)
# ============================================================================


@app.get("/api/data/load", response_model=DailyDataResponse)
def load_daily_data(
    date: str,
    form_id: Optional[int] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Return all survey submissions for a specific date.

    - `date`: YYYY-MM-DD (UTC) string
    - Optional `form_id` to restrict to a single form
    
    - Admins see all submissions for the date
    - Non-admin users see only submissions for their assigned forms
    """
    try:
        target_date: date_type = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format, expected YYYY-MM-DD")

    query = db.query(Submission)
    
    if form_id:
        if not check_form_access(current_user, form_id, db):
            raise HTTPException(status_code=403, detail="Access denied to this form")
        query = query.filter(Submission.form_id == form_id)
    elif current_user.role != "admin":
        accessible_form_ids = (
            db.query(UserFormAccess.form_id)
            .filter(UserFormAccess.user_id == current_user.id)
            .all()
        )
        form_ids = [f[0] for f in accessible_form_ids]
        if not form_ids:
            return DailyDataResponse(date=target_date.isoformat(), total=0, submissions=[])
        query = query.filter(Submission.form_id.in_(form_ids))

    # Prefer submitted_at if available, otherwise fall back to created_at
    day_start = datetime.combine(target_date, datetime.min.time())
    day_end = datetime.combine(target_date, datetime.max.time())

    submissions = (
        query.filter(
            (
                (Submission.submitted_at >= day_start)
                & (Submission.submitted_at <= day_end)
            )
            | (
                Submission.submitted_at.is_(None)
                & (Submission.created_at >= day_start)
                & (Submission.created_at <= day_end)
            )
        )
        .order_by(desc(Submission.submitted_at.nullslast()), desc(Submission.created_at))
        .all()
    )

    return DailyDataResponse(
        date=target_date.isoformat(),
        total=len(submissions),
        submissions=[SubmissionResponse.model_validate(s) for s in submissions],
    )


# ============================================================================
# User Management Endpoints
# ============================================================================

@app.get("/api/users", response_model=list[UserResponse])
def list_users(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """List all users (admin only).
    
    Returns users with helper flags:
    - can_delete: False for admin users (protected)
    - can_assign_forms: False for admin users (they have access to all forms)
    """
    users = db.query(User).offset(skip).limit(limit).all()
    
    # Add helper flags for frontend
    result = []
    for user in users:
        user_dict = {
            **{c.name: getattr(user, c.name) for c in user.__table__.columns if c.name != "hashed_password"},
            "can_delete": user.role != "admin",
            "can_assign_forms": user.role != "admin",
        }
        result.append(UserResponse(**user_dict))
    
    return result


@app.get("/api/users/{user_id}", response_model=UserResponse)
def get_user(
    user_id: int,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """Get a specific user (admin only).
    
    Returns user with helper flags:
    - can_delete: False for admin users (protected)
    - can_assign_forms: False for admin users (they have access to all forms)
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Add helper flags for frontend
    user_dict = {
        **{c.name: getattr(user, c.name) for c in user.__table__.columns if c.name != "hashed_password"},
        "can_delete": user.role != "admin",
        "can_assign_forms": user.role != "admin",
    }
    return UserResponse(**user_dict)


@app.put("/api/users/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    user_update: UserUpdate,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """Update a user (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    for field, value in user_update.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    
    user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(user)
    return user


@app.delete("/api/users/{user_id}")
def delete_user(
    user_id: int,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """Delete a user (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Prevent self-deletion
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    
    # Prevent deleting admin users - they are protected
    if user.role == "admin":
        raise HTTPException(status_code=400, detail="Cannot delete admin users. Admin accounts are protected.")
    
    db.delete(user)
    db.commit()
    return {"detail": f"User {user.username} deleted successfully"}


@app.post("/api/users/{user_id}/reset-password")
def reset_password(
    user_id: int,
    password_data: ResetPasswordRequest,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """Reset a user's password (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.hashed_password = get_password_hash(password_data.new_password)
    user.updated_at = datetime.utcnow()
    db.commit()
    return {"detail": f"Password reset successfully for user {user.username}"}


@app.post("/api/users/{user_id}/permissions", response_model=PermissionResponse)
def add_user_permission(
    user_id: int,
    permission: PermissionCreate,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """Add a permission to a user (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if permission already exists
    existing = (
        db.query(UserPermission)
        .filter(
            UserPermission.user_id == user_id,
            UserPermission.resource == permission.resource,
            UserPermission.action == permission.action,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Permission already exists")
    
    user_permission = UserPermission(
        user_id=user_id,
        resource=permission.resource,
        action=permission.action,
    )
    db.add(user_permission)
    db.commit()
    db.refresh(user_permission)
    return user_permission


# ============================================================================
# User Form Access Endpoints
# ============================================================================

@app.post("/api/users/{user_id}/forms/{form_id}", response_model=UserFormAccessResponse)
def assign_form_to_user(
    user_id: int,
    form_id: int,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """Assign a form to a user (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Admin users have access to all forms by default - no need to assign
    if user.role == "admin":
        raise HTTPException(status_code=400, detail="Admin users have access to all forms by default. Form assignment is not needed.")
    
    form = db.query(FormModel).filter(FormModel.id == form_id).first()
    if not form:
        raise HTTPException(status_code=404, detail="Form not found")
    
    # Check access for non-admin users
    if not check_form_access(current_user, form_id, db):
        raise HTTPException(status_code=403, detail="Access denied to this form")
    
    # Check if access already exists
    existing = (
        db.query(UserFormAccess)
        .filter(
            UserFormAccess.user_id == user_id,
            UserFormAccess.form_id == form_id,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="User already has access to this form")
    
    form_access = UserFormAccess(user_id=user_id, form_id=form_id)
    db.add(form_access)
    db.commit()
    db.refresh(form_access)
    return form_access


@app.post("/api/users/{user_id}/forms/bulk")
def bulk_assign_forms(
    user_id: int,
    access_data: BulkFormAccessRequest,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """Assign multiple forms to a user (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Admin users have access to all forms by default - no need to assign
    if user.role == "admin":
        raise HTTPException(status_code=400, detail="Admin users have access to all forms by default. Form assignment is not needed.")
    
    assigned_count = 0
    skipped_count = 0
    
    for form_id in access_data.form_ids:
        # Verify form exists
        form = db.query(FormModel).filter(FormModel.id == form_id).first()
        if not form:
            skipped_count += 1
            continue
            
        # Check if access already exists
        existing = (
            db.query(UserFormAccess)
            .filter(
                UserFormAccess.user_id == user_id,
                UserFormAccess.form_id == form_id,
            )
            .first()
        )
        if existing:
            skipped_count += 1
            continue
        
        form_access = UserFormAccess(user_id=user_id, form_id=form_id)
        db.add(form_access)
        assigned_count += 1
    
    db.commit()
    return {
        "detail": f"Successfully assigned {assigned_count} forms. {skipped_count} skipped (already assigned or invalid)."
    }


@app.delete("/api/users/{user_id}/forms/{form_id}")
def revoke_form_access(
    user_id: int,
    form_id: int,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """Revoke form access from a user (admin only)."""
    form_access = (
        db.query(UserFormAccess)
        .filter(
            UserFormAccess.user_id == user_id,
            UserFormAccess.form_id == form_id,
        )
        .first()
    )
    if not form_access:
        raise HTTPException(status_code=404, detail="Form access not found")
    
    db.delete(form_access)
    db.commit()
    return {"detail": "Form access revoked successfully"}


@app.delete("/api/users/{user_id}/forms/bulk")
def bulk_revoke_forms(
    user_id: int,
    access_data: BulkFormAccessRequest,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """Revoke multiple forms from a user (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    revoked_count = 0
    skipped_count = 0
    
    for form_id in access_data.form_ids:
        form_access = (
            db.query(UserFormAccess)
            .filter(
                UserFormAccess.user_id == user_id,
                UserFormAccess.form_id == form_id,
            )
            .first()
        )
        if not form_access:
            skipped_count += 1
            continue
        
        db.delete(form_access)
        revoked_count += 1
    
    db.commit()
    return {
        "detail": f"Successfully revoked access to {revoked_count} forms. {skipped_count} skipped (not assigned)."
    }


@app.get("/api/users/{user_id}/forms", response_model=list[FormResponse])
def get_user_forms(
    user_id: int,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """Get all forms assigned to a user (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get all forms the user has access to
    form_access_records = (
        db.query(UserFormAccess)
        .filter(UserFormAccess.user_id == user_id)
        .offset(skip)
        .limit(limit)
        .all()
    )
    
    forms = [record.form for record in form_access_records]
    
    # Add submission count to each form
    result = []
    for form in forms:
        form_dict = {
            **{c.name: getattr(form, c.name) for c in form.__table__.columns},
            "submission_count": db.query(func.count(Submission.id))
            .filter(Submission.form_id == form.id)
            .scalar(),
        }
        result.append(FormResponse(**form_dict))
    
    return result


# ============================================================================
# Form Endpoints
# ============================================================================

@app.get("/api/forms", response_model=list[FormResponse])
def list_forms(
    skip: int = 0,
    limit: int = 100,
    category: str = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """List all forms from the local cache/database.
    
    - Admins see all forms
    - Non-admin users see only forms assigned to them
    """
    query = db.query(FormModel)
    
    # Non-admin users only see forms assigned to them
    if current_user.role != "admin":
        form_ids = (
            db.query(UserFormAccess.form_id)
            .filter(UserFormAccess.user_id == current_user.id)
            .all()
        )
        form_ids = [f[0] for f in form_ids]
        if not form_ids:
            return []
        query = query.filter(FormModel.id.in_(form_ids))
    
    if category:
        query = query.filter(FormModel.category == category)
    
    forms = query.offset(skip).limit(limit).all()
    
    # Add submission count
    result = []
    for form in forms:
        form_dict = {
            **{c.name: getattr(form, c.name) for c in form.__table__.columns},
            "submission_count": db.query(func.count(Submission.id))
            .filter(Submission.form_id == form.id)
            .scalar(),
        }
        result.append(FormResponse(**form_dict))
    
    return result


# Public alias without /api prefix (for cleaner URLs / compatibility)
@app.get("/forms", response_model=list[FormResponse])
def list_forms_public(
    skip: int = 0,
    limit: int = 100,
    category: str = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Public-facing alias for listing forms.

    Keeps compatibility with existing `/api/forms` while exposing
    the shorter `/forms` path expected by some clients.
    """
    return list_forms(skip=skip, limit=limit, category=category, current_user=current_user, db=db)


@app.get("/api/forms/{form_id}", response_model=FormResponse)
def get_form(
    form_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Get a specific form.
    
    - Admins can access any form
    - Non-admin users can only access forms assigned to them
    """
    form = db.query(FormModel).filter(FormModel.id == form_id).first()
    if not form:
        raise HTTPException(status_code=404, detail="Form not found")
    
    # Check access for non-admin users
    if not check_form_access(current_user, form_id, db):
        raise HTTPException(status_code=403, detail="Access denied to this form")
    
    form_dict = {
        **{c.name: getattr(form, c.name) for c in form.__table__.columns},
        "submission_count": db.query(func.count(Submission.id))
        .filter(Submission.form_id == form.id)
        .scalar(),
    }
    mapping = db.query(FormFieldMapping).filter(FormFieldMapping.form_id == form.id).first()
    form_dict["province_field"] = (mapping.province_field or None) if mapping else None
    form_dict["district_field"] = (mapping.district_field or None) if mapping else None
    return FormResponse(**form_dict)


@app.get("/api/forms/{form_id}/field-mapping", response_model=FormFieldMappingResponse)
def get_form_field_mapping(
    form_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Get field mapping for a form (which form fields → province, district, age, gender, etc.)."""
    form = db.query(FormModel).filter(FormModel.id == form_id).first()
    if not form:
        raise HTTPException(status_code=404, detail="Form not found")
    if not check_form_access(current_user, form_id, db):
        raise HTTPException(status_code=403, detail="Access denied to this form")
    mapping = db.query(FormFieldMapping).filter(FormFieldMapping.form_id == form_id).first()
    if not mapping:
        raise HTTPException(status_code=404, detail="No field mapping for this form. Use PATCH to create one.")
    return FormFieldMappingResponse.model_validate(mapping)


@app.patch("/api/forms/{form_id}/field-mapping", response_model=FormFieldMappingResponse)
def update_form_field_mapping(
    form_id: int,
    body: FormFieldMappingUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Set which form fields map to province and district (and optionally age, gender, etc.).
    Used by ETL sync and backfill to fill Submission.province and Submission.district from
    the correct columns in submission_data/cleaned_data for each form."""
    form = db.query(FormModel).filter(FormModel.id == form_id).first()
    if not form:
        raise HTTPException(status_code=404, detail="Form not found")
    if not check_form_access(current_user, form_id, db):
        raise HTTPException(status_code=403, detail="Access denied to this form")
    mapping = db.query(FormFieldMapping).filter(FormFieldMapping.form_id == form_id).first()
    if not mapping:
        mapping = FormFieldMapping(form_id=form_id)
        db.add(mapping)
        db.flush()
    u = body.model_dump(exclude_unset=True)
    for k in ("province_field", "district_field", "age_field", "gender_field", "household_size_field", "location_field"):
        if k in u:
            setattr(mapping, k, u[k])
    db.commit()
    db.refresh(mapping)
    return FormFieldMappingResponse.model_validate(mapping)


# ============================================================================
# Submission Endpoints
# ============================================================================

def _get_enumerator_from_data(data: Optional[dict]) -> Optional[str]:
    """Resolve enumerator from submission cleaned_data/submission_data.
    Tries: _submitted_by (Kobo), info/enumerator_name, info/enumerator_id, then nested info.enumerator_*.
    """
    if not data:
        return None
    for key in ("_submitted_by", "info/enumerator_name", "info/enumerator_id"):
        v = data.get(key)
        if v is not None and str(v).strip():
            return str(v).strip()
    info = data.get("info")
    if isinstance(info, dict):
        for k in ("enumerator_name", "enumerator_id"):
            v = info.get(k)
            if v is not None and str(v).strip():
                return str(v).strip()
    return None


@app.get("/api/submissions", response_model=list[SubmissionResponse])
def list_submissions(
    form_id: int = None,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """List submissions.
    
    - Admins see all submissions (optionally filtered by form_id)
    - Non-admin users see only submissions for forms assigned to them
    """
    query = db.query(Submission)
    
    # Check access and filter by form_id if provided
    if form_id:
        if not check_form_access(current_user, form_id, db):
            raise HTTPException(status_code=403, detail="Access denied to this form")
        query = query.filter(Submission.form_id == form_id)
    elif current_user.role != "admin":
        # If no form_id, only show submissions for assigned forms
        form_ids = (
            db.query(UserFormAccess.form_id)
            .filter(UserFormAccess.user_id == current_user.id)
            .all()
        )
        form_ids = [f[0] for f in form_ids]
        if not form_ids:
            return []
        query = query.filter(Submission.form_id.in_(form_ids))
    
    submissions = query.order_by(desc(Submission.created_at)).offset(skip).limit(limit).all()
    
    result = []
    for s in submissions:
        response = SubmissionResponse.model_validate(s)
        data = s.cleaned_data or s.submission_data or {}
        response.submission_data = data
        response.enumerator = _get_enumerator_from_data(data)
        result.append(response)
    
    return result


@app.get("/form/{form_id}/submissions", response_model=list[SubmissionResponse])
def list_form_submissions_public(
    form_id: int,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Public alias for getting submissions by form, matching the desired
    `/form/{id}/submissions` shape while reusing existing logic.
    """
    return get_form_submissions(form_id=form_id, filters=None, skip=skip, limit=limit, current_user=current_user, db=db)


@app.get("/api/submissions/{submission_id}", response_model=SubmissionResponse)
def get_submission(
    submission_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Get a specific submission.
    
    Checks if the user has access to the form associated with this submission.
    """
    submission = db.query(Submission).filter(Submission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    
    # Check access to the parent form
    if not check_form_access(current_user, submission.form_id, db):
        raise HTTPException(status_code=403, detail="Access denied to this submission's form")
    
    response = SubmissionResponse.model_validate(submission)
    data = submission.cleaned_data or submission.submission_data or {}
    response.submission_data = data
    response.enumerator = _get_enumerator_from_data(data)
    return response


# ============================================================================
# Indicator Endpoints
# ============================================================================

@app.get("/api/indicators", response_model=list[IndicatorResponse])
def list_indicators(
    form_id: int = None,
    category: str = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """List indicators.
    
    - Admins see all indicators
    - Non-admin users see only indicators for forms assigned to them
    """
    query = db.query(Indicator)
    
    # Check access and filter by form_id if provided
    if form_id:
        if not check_form_access(current_user, form_id, db):
            raise HTTPException(status_code=403, detail="Access denied to this form")
        query = query.filter(Indicator.form_id == form_id)
    elif current_user.role != "admin":
        # If no form_id, only show indicators for assigned forms
        form_ids = (
            db.query(UserFormAccess.form_id)
            .filter(UserFormAccess.user_id == current_user.id)
            .all()
        )
        form_ids = [f[0] for f in form_ids]
        if not form_ids:
            return []
        query = query.filter(Indicator.form_id.in_(form_ids))
        
    if category:
        query = query.join(FormModel).filter(FormModel.category == category)
    
    indicators = query.all()
    return indicators


@app.get("/form/{form_id}/indicators", response_model=list[IndicatorResponse])
def list_form_indicators_public(
    form_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Public alias for listing indicators for a given form:
    `/form/{id}/indicators`.

    This returns the row-level Indicator records (not the aggregated summary
    used by the dashboard panel).
    """
    return list_indicators(form_id=form_id, category=None, current_user=current_user, db=db)


@app.get("/api/forms/{form_id}/indicators")
def get_form_indicators_summary(
    form_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Aggregated indicator summary used by the Monitoring dashboard's
    `IndicatorsPanel`.

    Returns a JSON object (not a list of Indicator rows) with keys like:
    - total_submissions
    - valid_submissions
    - invalid_submissions
    - male_count / female_count / other_gender_count
    - province_counts
    - time_trend_summary
    """
    form = db.query(FormModel).filter(FormModel.id == form_id).first()
    if not form:
        raise HTTPException(status_code=404, detail="Form not found")
    
    # Check access for non-admin users
    if not check_form_access(current_user, form_id, db):
        raise HTTPException(status_code=403, detail="Access denied to this form")

    # Base query for this form's submissions
    submissions_query = db.query(Submission).filter(Submission.form_id == form_id)

    total_submissions = submissions_query.count()

    # Sample up to N submissions for derived stats to avoid huge in-memory loads
    SAMPLE_LIMIT = 5000
    submissions = submissions_query.order_by(desc(Submission.submitted_at)).limit(SAMPLE_LIMIT).all()

    valid_submissions = 0
    invalid_submissions = 0

    male_count = 0
    female_count = 0
    other_gender_count = 0

    province_counts: dict[str, int] = {}

    min_submitted_at: Optional[datetime] = None
    max_submitted_at: Optional[datetime] = None

    for sub in submissions:
        payload = sub.cleaned_data or sub.submission_data or {}
        if not isinstance(payload, dict):
            continue

        # Validity flag from ETL cleaning
        is_valid = payload.get("is_valid")
        if is_valid is False:
            invalid_submissions += 1
        else:
            # Treat missing flag as valid to avoid under-counting historical data
            valid_submissions += 1

        # Gender counts
        gender_raw = (
            payload.get("gender")
            or payload.get("sex")
            or payload.get("respondent_gender")
            or ""
        )
        gender = str(gender_raw).strip().lower()
        if gender in {"male", "m"}:
            male_count += 1
        elif gender in {"female", "f"}:
            female_count += 1
        elif gender:
            other_gender_count += 1

        # Province-level breakdown
        province_raw = (
            payload.get("province")
            or payload.get("state")
            or payload.get("region")
        )
        if province_raw:
            province = str(province_raw).strip()
            if province:
                province_counts[province] = province_counts.get(province, 0) + 1

        # Time trend summary based on submitted_at
        if sub.submitted_at:
            if not min_submitted_at or sub.submitted_at < min_submitted_at:
                min_submitted_at = sub.submitted_at
            if not max_submitted_at or sub.submitted_at > max_submitted_at:
                max_submitted_at = sub.submitted_at

    time_trend_summary = None
    if min_submitted_at and max_submitted_at:
        time_trend_summary = {
            "from": min_submitted_at.isoformat(),
            "to": max_submitted_at.isoformat(),
            "total": total_submissions,
        }

    return {
        "form_id": form_id,
        "total_submissions": total_submissions,
        "valid_submissions": valid_submissions,
        "invalid_submissions": invalid_submissions,
        "male_count": male_count,
        "female_count": female_count,
        "other_gender_count": other_gender_count,
        "province_counts": province_counts,
        "time_trend_summary": time_trend_summary,
    }


@app.get("/form/{form_id}/aggregate", response_model=AggregateReportResponse)
def get_form_aggregate_report(
    form_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Get aggregate report for a form with:
    - Total Survey (total submissions)
    - Today's submissions
    - Total Provinces (auto-detected)
    - Gender Ratio (auto-detected and accurate)
    """
    form = db.query(FormModel).filter(FormModel.id == form_id).first()
    if not form:
        raise HTTPException(status_code=404, detail="Form not found")
    
    # Check access for non-admin users
    if not check_form_access(current_user, form_id, db):
        raise HTTPException(status_code=403, detail="Access denied to this form")

    submissions = db.query(Submission).filter(Submission.form_id == form_id).all()
    
    total_survey = len(submissions)
    
    today = date_type.today()
    todays_submissions = 0
    for sub in submissions:
        if sub.submitted_at:
            submitted_date = sub.submitted_at.date() if hasattr(sub.submitted_at, 'date') else sub.submitted_at
            if submitted_date == today:
                todays_submissions += 1
        elif sub.created_at:
            created_date = sub.created_at.date() if hasattr(sub.created_at, 'date') else sub.created_at
            if created_date == today:
                todays_submissions += 1
    
    province_field = detect_province_field(form, submissions)
    gender_field = detect_gender_field(form, submissions)
    
    province_counts = get_field_data(submissions, province_field) if province_field else {}
    gender_counts = get_field_data(submissions, gender_field) if gender_field else {}
    
    total_provinces = len(province_counts)
    
    gender_ratio = []
    total_with_gender = sum(gender_counts.values()) if gender_counts else 0
    for gender, count in sorted(gender_counts.items()):
        percentage = (count / total_with_gender * 100) if total_with_gender > 0 else 0
        gender_ratio.append(GenderRatioItem(
            gender=gender.title() if gender else "Unknown",
            count=count,
            percentage=round(percentage, 2)
        ))
    
    return AggregateReportResponse(
        form_id=form_id,
        total_survey=total_survey,
        todays_submissions=todays_submissions,
        total_provinces=total_provinces,
        gender_ratio=gender_ratio,
        generated_at=datetime.now()
    )


@app.post("/form/{form_id}/aggregate")
def aggregate_form_data(
    form_id: int,
    request: AggregateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Generic aggregate endpoint for a form.

    If metrics is empty or not provided, returns general aggregate report:
    - Total Survey
    - Today's submissions
    - Total Provinces
    - Gender Ratio

    Otherwise, computes custom metrics:
    - filters: equality filters on cleaned/submission data
    - group_by: list of fields to group by
    - metrics: list of metrics to compute per group
    """
    form = db.query(FormModel).filter(FormModel.id == form_id).first()
    if not form:
        raise HTTPException(status_code=404, detail="Form not found")
    
    # Check access for non-admin users
    if not check_form_access(current_user, form_id, db):
        raise HTTPException(status_code=403, detail="Access denied to this form")

    submissions = db.query(Submission).filter(Submission.form_id == form_id).all()
    
    if not request.metrics:
        total_survey = len(submissions)
        
        today = date_type.today()
        todays_submissions = 0
        for sub in submissions:
            if sub.submitted_at:
                submitted_date = sub.submitted_at.date() if hasattr(sub.submitted_at, 'date') else sub.submitted_at
                if submitted_date == today:
                    todays_submissions += 1
            elif sub.created_at:
                created_date = sub.created_at.date() if hasattr(sub.created_at, 'date') else sub.created_at
                if created_date == today:
                    todays_submissions += 1
        
        province_field = detect_province_field(form, submissions)
        gender_field = detect_gender_field(form, submissions)
        
        province_counts = get_field_data(submissions, province_field) if province_field else {}
        gender_counts = get_field_data(submissions, gender_field) if gender_field else {}
        
        total_provinces = len(province_counts)
        
        gender_ratio = []
        total_with_gender = sum(gender_counts.values()) if gender_counts else 0
        for gender, count in sorted(gender_counts.items()):
            percentage = (count / total_with_gender * 100) if total_with_gender > 0 else 0
            gender_ratio.append(GenderRatioItem(
                gender=gender.title() if gender else "Unknown",
                count=count,
                percentage=round(percentage, 2)
            ))
        
        return AggregateReportResponse(
            form_id=form_id,
            total_survey=total_survey,
            todays_submissions=todays_submissions,
            total_provinces=total_provinces,
            gender_ratio=gender_ratio,
            generated_at=datetime.now()
        )

    # Custom metrics logic (when metrics is provided)
    # Apply filters (simple equality / IN logic, similar to chart endpoints)
    filters = request.filters or {}
    if filters:
        filtered: list[Submission] = []
        for sub in submissions:
            payload = sub.cleaned_data or sub.submission_data
            if not payload or not isinstance(payload, dict):
                continue

            matches = True
            for fname, fval in filters.items():
                if fval is None or fval == "" or fval == []:
                    continue
                value = payload.get(fname)
                if isinstance(fval, list):
                    if value not in fval:
                        matches = False
                        break
                else:
                    if str(value) != str(fval):
                        matches = False
                        break
            if matches:
                filtered.append(sub)
        submissions = filtered

    # Helper: fetch payload dict for a submission
    def get_payload(sub: Submission) -> dict[str, Any]:
        data = sub.cleaned_data or sub.submission_data or {}
        return data if isinstance(data, dict) else {}

    group_by = request.group_by or []

    # No grouping: compute metrics on the whole filtered set
    if not group_by:
        row = _compute_metrics_for_group(submissions, request.metrics, get_payload)
        return {"rows": [row], "meta": {"total": len(submissions)}}

    # Group submissions by the requested fields
    grouped: dict[tuple, list[Submission]] = {}
    for sub in submissions:
        payload = get_payload(sub)
        key_vals = []
        for g in group_by:
            key_vals.append(payload.get(g.field))
        key = tuple(key_vals)
        grouped.setdefault(key, []).append(sub)

    rows = []
    for key, subs in grouped.items():
        base_row: dict[str, Any] = {}
        for idx, g in enumerate(group_by):
            base_row[g.field] = key[idx]
        metrics_row = _compute_metrics_for_group(subs, request.metrics, get_payload)
        base_row.update(metrics_row)
        rows.append(base_row)

    return {"rows": rows, "meta": {"total": len(submissions)}}


def _compute_metrics_for_group(
    submissions: list[Submission],
    metrics: list,
    get_payload,
) -> dict[str, Any]:
    """Compute metric values for a single group of submissions."""
    row: dict[str, Any] = {}

    # Pre-compute payloads for efficiency
    payloads = [get_payload(sub) for sub in submissions]

    for metric in metrics:
        m_type = metric.type
        field = metric.field
        alias = metric.alias

        if m_type == "count":
            if field == "*" or field == "_all":
                row[alias] = len(submissions)
            else:
                count = sum(1 for p in payloads if p.get(field) not in (None, ""))
                row[alias] = count

        elif m_type == "sum":
            total = 0.0
            for p in payloads:
                try:
                    val = p.get(field)
                    if val not in (None, ""):
                        total += float(val)
                except (ValueError, TypeError):
                    continue
            row[alias] = total

        elif m_type == "avg":
            values = []
            for p in payloads:
                try:
                    val = p.get(field)
                    if val not in (None, ""):
                        values.append(float(val))
                except (ValueError, TypeError):
                    continue
            row[alias] = float(sum(values) / len(values)) if values else 0.0

        elif m_type == "percentage":
            # Percentage of submissions where field == value
            target = metric.value
            if target is None:
                row[alias] = 0.0
            else:
                total = len(submissions)
                if total == 0:
                    row[alias] = 0.0
                else:
                    match_count = 0
                    for p in payloads:
                        val = p.get(field)
                        if str(val) == str(target):
                            match_count += 1
                    row[alias] = (match_count / total) * 100.0

        else:
            # Unknown metric type -> default to None
            row[alias] = None

    return row


# ============================================================================
# Generic Statistical Chart Endpoints (Box Plot, Bar Chart)
# These operate on Kobo raw/cleaned data per form
# ============================================================================

def build_schema_maps(form_schema: dict) -> tuple[dict, dict]:
    """
    Build schema maps following Kobo best practices:
    - question_map: field_name → {label, type, list_name}
    - choice_map: list_name → {code: label}
    
    This is more efficient than on-the-fly lookups.
    """
    question_map = {}
    choice_map = {}
    
    if not form_schema or not isinstance(form_schema, dict):
        return question_map, choice_map
    
    try:
        content = form_schema.get("content", {})
        if not content:
            content = form_schema
        
        questions = content.get("survey", [])
        choices = content.get("choices", [])
        
        # Build question map: field_name → {label, type, list_name}
        for q in questions:
            if "name" in q:
                field_name = q["name"]
                question_map[field_name] = {
                    "label": q.get("label", [""])[0] if isinstance(q.get("label"), list) and len(q.get("label", [])) > 0 else q.get("label", ""),
                    "type": q.get("type", ""),
                    "list_name": q.get("select_from_list_name") or q.get("choice")  # Kobo uses both
                }
        
        # Build choice map: list_name → {code: label}
        for c in choices:
            list_name = c.get("list_name") or c.get("name")  # Kobo can use either
            if list_name:
                if list_name not in choice_map:
                    choice_map[list_name] = {}
                
                code = c.get("name")
                label = c.get("label", [])
                # Handle label format (can be list, string, or object)
                if isinstance(label, list) and len(label) > 0:
                    label_value = label[0] if isinstance(label[0], str) else (label[0].get("label", "") if isinstance(label[0], dict) else str(label[0]))
                elif isinstance(label, str):
                    label_value = label
                else:
                    label_value = str(code) if code else ""
                
                if code:
                    choice_map[list_name][code] = label_value
        
        return question_map, choice_map
    except Exception as e:
        logger.warning(f"Error building schema maps: {e}")
        return question_map, choice_map


def get_choice_label_dynamic(form_schema: dict, field_name: str, code: str) -> str:
    """
    Dynamic label lookup that tries to find the field and choice list by searching
    through all fields in the schema. This is a fallback when exact field name matching fails.
    """
    if not form_schema or not isinstance(form_schema, dict):
        return code
    
    try:
        content = form_schema.get("content", {})
        if not content:
            content = form_schema
        
        survey = content.get("survey", [])
        choices_lists = content.get("choices", [])
        
        if not survey or not choices_lists:
            return code
        
        # Try to find field by partial name match (e.g., "province" in "info/province")
        field_name_parts = field_name.lower().split('/')
        last_part = field_name_parts[-1] if field_name_parts else field_name.lower()
        
        for field in survey:
            field_name_in_schema = field.get("name", "").lower()
            # Check if the last part of the field name matches
            if last_part in field_name_in_schema or field_name_in_schema.endswith(last_part):
                choice_list_name = field.get("choice") or field.get("select_from_list_name")
                if choice_list_name:
                    # Find the choice list and look for the code
                    for cl in choices_lists:
                        if cl.get("name") == choice_list_name:
                            choices = cl.get("choices", [])
                            for choice in choices:
                                choice_name = choice.get("name")
                                if choice_name and str(choice_name).lower() == str(code).lower():
                                    label = choice.get("label", [])
                                    if isinstance(label, list) and len(label) > 0:
                                        first_item = label[0]
                                        if isinstance(first_item, str):
                                            return first_item
                                        elif isinstance(first_item, dict):
                                            return first_item.get("label", code)
                                    elif isinstance(label, str):
                                        return label
        return code
    except Exception as e:
        logger.warning(f"Error in dynamic label lookup for {field_name}/{code}: {e}")
        return code


def _resolve_code_to_label(code: str, form, actual_path: str, request_field: str) -> str:
    """Resolve a choice code to its label using form schema. Returns code if not found."""
    if not code:
        return code
    question_map, choice_map = build_schema_maps(form.form_schema) if form.form_schema else ({}, {})
    for var in [actual_path, actual_path.lower(), actual_path.split("/")[-1], request_field, request_field.lower()]:
        if var in question_map:
            meta = question_map[var]
            if meta.get("list_name") and meta["list_name"] in choice_map:
                c = str(code).lower()
                for k, lbl in choice_map[meta["list_name"]].items():
                    if str(k).lower() == c:
                        return lbl
            break
    out = get_choice_label(form.form_schema, actual_path, code)
    return out if out != code else get_choice_label_dynamic(form.form_schema, actual_path, code)


def get_choice_label(form_schema: dict, field_name: str, code: str) -> str:
    """
    Look up the label for a choice code in the form schema.
    Returns the code if label not found.
    
    Kobo schema structure (can vary):
    - content.survey: list of field definitions
    - content.choices: list of choice lists
    - OR directly: survey and choices at root level
    - Each field with type 'select_one' or 'select_multiple' has a 'choice' key
    - The choice list name matches the choice list in content.choices
    """
    if not form_schema or not isinstance(form_schema, dict):
        return code
    
    try:
        # Try different schema structures
        content = form_schema.get("content", {})
        if not content:
            # Try root level
            content = form_schema
        
        survey = content.get("survey", [])
        choices_lists = content.get("choices", [])
        
        if not survey:
            logger.warning(f"No survey fields found in form schema for field '{field_name}'. Schema keys: {list(form_schema.keys())[:10]}")
            return code
        
        # Find the field definition - try multiple dynamic matching strategies
        field_def = None
        field_name_lower = field_name.lower()
        field_name_last_part = field_name.split("/")[-1].lower() if "/" in field_name else field_name_lower
        field_name_flat = field_name.replace("/", "_").lower()
        
        for field in survey:
            field_name_in_schema = field.get("name", "")
            field_name_in_schema_lower = field_name_in_schema.lower()
            field_name_in_schema_last_part = field_name_in_schema.split("/")[-1].lower() if "/" in field_name_in_schema else field_name_in_schema_lower
            field_name_in_schema_flat = field_name_in_schema.replace("/", "_").lower()
            
            # Try multiple matching strategies for dynamic field matching
            if (field_name_in_schema == field_name or  # Exact match
                field_name_in_schema_lower == field_name_lower or  # Case-insensitive exact
                field_name_in_schema_flat == field_name_flat or  # Flattened match
                field_name_in_schema_last_part == field_name_last_part or  # Last part match (province)
                field_name_last_part in field_name_in_schema_lower or  # Contains match
                field_name_in_schema_last_part in field_name_lower):  # Reverse contains match
                field_def = field
                break
        
        if not field_def:
            available_fields = [f.get('name') for f in survey[:10]]
            logger.warning(f"Field '{field_name}' not found in form schema. Available fields: {available_fields}")
            return code
        
        # Get the choice list name from the field
        # Kobo can store this as "choice" or "select_from_list_name"
        choice_list_name = field_def.get("choice") or field_def.get("select_from_list_name")
        if not choice_list_name:
            field_type = field_def.get("type", "unknown")
            logger.warning(f"Field '{field_name}' (type: {field_type}) has no choice list (not a select_one/select_multiple field). Field keys: {list(field_def.keys())}")
            return code
        
        # Find the choice list
        # Find the choice list - try exact match first, then partial match for dynamic lookup
        choice_list = None
        for cl in choices_lists:
            cl_name = cl.get("name")
            if cl_name == choice_list_name:
                choice_list = cl
                break
        
        # If not found, try partial match (for dynamic lookup)
        if not choice_list:
            choice_list_name_lower = choice_list_name.lower()
            for cl in choices_lists:
                cl_name = cl.get("name", "")
                if cl_name.lower() == choice_list_name_lower or choice_list_name_lower in cl_name.lower():
                    choice_list = cl
                    logger.info(f"Found choice list '{cl_name}' using partial match for '{choice_list_name}'")
                    break
        
        if not choice_list:
            available_lists = [cl.get('name') for cl in choices_lists[:10]]
            logger.warning(f"Choice list '{choice_list_name}' not found in form schema. Available choice lists: {available_lists}")
            return code
        
        # Find the label for the code
        choices = choice_list.get("choices", [])
        if not choices:
            logger.warning(f"Choice list '{choice_list_name}' has no choices. Choice list keys: {list(choice_list.keys())}")
            return code
        
        for choice in choices:
            choice_name = choice.get("name")
            # Match code (case-insensitive for robustness)
            if choice_name and str(choice_name).lower() == str(code).lower():
                label = choice.get("label", [])
                # Label can be a list of translations, a string, or a list of objects
                if isinstance(label, list) and len(label) > 0:
                    # Get the first translation
                    first_item = label[0]
                    if isinstance(first_item, str):
                        logger.info(f"Found label '{first_item}' for code '{code}' in field '{field_name}'")
                        return first_item
                    elif isinstance(first_item, dict):
                        # Handle object format: {"language": "English", "label": "Kabul"}
                        found_label = first_item.get("label", code)
                        logger.info(f"Found label '{found_label}' for code '{code}' in field '{field_name}'")
                        return found_label
                    else:
                        return str(first_item)
                elif isinstance(label, str):
                    logger.info(f"Found label '{label}' for code '{code}' in field '{field_name}'")
                    return label
                else:
                    logger.warning(f"Choice '{code}' has invalid label format: {label}")
                    return code
        
        available_codes = [c.get('name') for c in choices[:10]]
        logger.warning(f"Code '{code}' not found in choice list '{choice_list_name}'. Available codes: {available_codes}")
        return code
    except Exception as e:
        logger.warning(f"Error looking up choice label for {field_name}/{code}: {e}")
        return code


def _apply_filters_dict(query, service, form, filters: dict):
    """
    Apply a filters dict (key=field path, value=scalar or list) to the query using
    JSON extract. Uses service._resolve_field and _get_json_field. Returns the modified query.
    """
    if not filters:
        return query
    path_mapping = service._get_full_path_mapping(form)
    for k, v in filters.items():
        if v is None or v == "" or (isinstance(v, list) and len(v) == 0):
            continue
        resolved = service._resolve_field(k, path_mapping)
        jexpr = service._get_json_field(resolved)
        if jexpr is None:
            continue
        if isinstance(v, list):
            query = query.filter(jexpr.in_([str(x) for x in v]))
        else:
            query = query.filter(jexpr == str(v))
    return query


def get_nested_field_value(payload: dict, field_name: str) -> Any:
    """
    Extract field value from payload, handling both nested (info/Province) and flattened (info_Province) formats.
    
    Tries multiple variations:
    1. Direct access: payload[field_name]
    2. Case-insensitive direct access
    3. Slash notation: payload['info']['Province'] for "info/Province"
    4. Flattened notation: payload['info_Province'] for "info/Province"
    5. Case-insensitive variations of the above
    """
    if not payload or not isinstance(payload, dict):
        return None
    
    # Normalize field name (remove leading/trailing slashes, handle variations)
    normalized = field_name.strip().strip('/')
    original = normalized
    
    # Try direct access (exact match)
    if normalized in payload:
        return payload[normalized]
    
    # Try case-insensitive direct access
    for key in payload.keys():
        if isinstance(key, str) and key.lower() == normalized.lower():
            return payload[key]
    
    # Try slash notation (nested structure): info/Province -> payload['info']['Province']
    if '/' in normalized:
        parts = normalized.split('/')
        # Try exact nested path
        value = payload
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                value = None
                break
            if value is None:
                break
        if value is not None:
            return value
        
        # Try case-insensitive nested path
        value = payload
        for part in parts:
            if isinstance(value, dict):
                # Find key case-insensitively
                found_key = None
                for key in value.keys():
                    if isinstance(key, str) and key.lower() == part.lower():
                        found_key = key
                        break
                if found_key is not None:
                    value = value[found_key]
                else:
                    value = None
                    break
            else:
                value = None
                break
        if value is not None:
            return value
    
    # Try flattened notation: info/Province -> info_Province
    flattened_name = normalized.replace('/', '_')
    if flattened_name in payload:
        return payload[flattened_name]
    
    # Try case-insensitive flattened
    for key in payload.keys():
        if isinstance(key, str) and key.lower() == flattened_name.lower():
            return payload[key]
    
    # Try just the last part after slash: info/Province -> Province
    if '/' in normalized:
        last_part = normalized.split('/')[-1]
        if last_part in payload:
            return payload[last_part]
        # Case-insensitive last part
        for key in payload.keys():
            if isinstance(key, str) and key.lower() == last_part.lower():
                return payload[key]
    
    # Try without prefix (common Kobo patterns): info/Province -> Province, info_province -> province
    # Remove common prefixes like "info", "group", etc.
    for prefix in ['info_', 'group_', 'data_', 'info/', 'group/', 'data/']:
        if normalized.lower().startswith(prefix.lower()):
            remaining = normalized[len(prefix):]
            if remaining in payload:
                return payload[remaining]
            # Case-insensitive
            for key in payload.keys():
                if isinstance(key, str) and key.lower() == remaining.lower():
                    return payload[key]
    
    return None


@app.post("/api/charts/box_plot", response_model=BoxPlotResponse)
def generate_box_plot(
    request: BoxPlotRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Compute five-number summary + outliers for a numeric column on a form.
    Uses DB-side filtering and fetches only the target column (no full submission blobs).
    """
    from analysis_service import AnalysisService

    form = db.query(FormModel).filter(FormModel.id == request.form_id).first()
    if not form:
        raise HTTPException(status_code=404, detail="Form not found")
    if not check_form_access(current_user, request.form_id, db):
        raise HTTPException(status_code=403, detail="Access denied to this form")
    if db.query(Submission).filter(Submission.form_id == form.id).limit(1).first() is None:
        raise HTTPException(status_code=400, detail=f"No submissions found for form_id {request.form_id}. Please sync data first.")

    service = AnalysisService(db)
    path_mapping = service._get_full_path_mapping(form)
    request_column = service._resolve_field(request.column, path_mapping)
    filters = request.filters or {}
    cache_key = {"form_id": form.id, "column": request.column, "filters": filters}
    cached = service._get_cache("box_plot", cache_key)
    if cached:
        return BoxPlotResponse(**cached)

    query = db.query(Submission).filter(Submission.form_id == form.id)
    query = _apply_filters_dict(query, service, form, filters)
    col_expr = service._get_json_field(request_column)
    if col_expr is None:
        return BoxPlotResponse(form_id=form.id, column=request.column, q1=0.0, median=0.0, q3=0.0, whisker_min=0.0, whisker_max=0.0, outliers=[], iqr=0.0, lower_bound=0.0, upper_bound=0.0, count=0, stats={"error": f"Invalid column path: {request.column}"})

    rows = query.with_entities(col_expr).all()
    total_checked = len(rows)
    empty_count = sum(1 for (v,) in rows if v is None or (isinstance(v, str) and v.strip() == ""))
    values = []
    for (v,) in rows:
        if v is None or (isinstance(v, str) and v.strip() == ""):
            continue
        s = str(v).strip().strip('"')
        if not s:
            continue
        try:
            values.append(float(s))
        except (ValueError, TypeError):
            pass
    non_numeric_count = total_checked - empty_count - len(values)

    if not values:
        out = BoxPlotResponse(
            form_id=form.id, column=request.column, q1=0.0, median=0.0, q3=0.0, whisker_min=0.0, whisker_max=0.0,
            outliers=[], iqr=0.0, lower_bound=0.0, upper_bound=0.0, count=0,
            stats={"total_submissions": total_checked, "checked_after_filters": total_checked, "empty_values": empty_count, "non_numeric_values": non_numeric_count, "error": f"Field '{request.column}' contains no numeric data. Ensure you select a numeric field (integer/decimal)."}
        )
        service._set_cache("box_plot", cache_key, out.model_dump(), form.id)
        return out

    values.sort()
    series = values

    def _pct(p: float) -> float:
        if not series:
            return 0.0
        k = (len(series) - 1) * p
        f = int(k)
        c = min(f + 1, len(series) - 1)
        return float(series[f] * (c - k) + series[c] * (k - f)) if f != c else float(series[int(k)])

    q1, med, q3 = _pct(0.25), _pct(0.5), _pct(0.75)
    iqr = q3 - q1
    lower_bound = q1 - 1.5 * iqr
    upper_bound = q3 + 1.5 * iqr
    whisker_min_vals = [v for v in series if v >= lower_bound]
    whisker_max_vals = [v for v in series if v <= upper_bound]
    whisker_min = float(min(whisker_min_vals)) if whisker_min_vals else float(min(series))
    whisker_max = float(max(whisker_max_vals)) if whisker_max_vals else float(max(series))
    outliers = [float(v) for v in series if v < lower_bound or v > upper_bound]

    out = BoxPlotResponse(
        form_id=form.id, column=request.column, q1=float(q1), median=float(med), q3=float(q3),
        whisker_min=whisker_min, whisker_max=whisker_max, outliers=outliers, iqr=float(iqr),
        lower_bound=float(lower_bound), upper_bound=float(upper_bound), count=len(series),
        stats={"total_submissions": total_checked, "checked_after_filters": total_checked, "empty_values": empty_count, "non_numeric_values": non_numeric_count},
    )
    service._set_cache("box_plot", cache_key, out.model_dump(), form.id)
    return out


@app.post("/api/charts/bar_chart", response_model=BarChartResponse)
def generate_bar_chart(
    request: BarChartRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Categorical bar chart. Uses DB-side filtering and GROUP BY; only label resolution in Python.
    """
    from analysis_service import AnalysisService

    form = db.query(FormModel).filter(FormModel.id == request.form_id).first()
    if not form:
        raise HTTPException(status_code=404, detail="Form not found")
    if not check_form_access(current_user, request.form_id, db):
        raise HTTPException(status_code=403, detail="Access denied to this form")

    service = AnalysisService(db)
    path_mapping = service._get_full_path_mapping(form)
    filters = request.filters or {}
    group_by_field = request.group_by
    if not group_by_field or (isinstance(group_by_field, str) and group_by_field.strip() == ""):
        if filters:
            group_by_field = list(filters.keys())[0]
        else:
            raise HTTPException(status_code=400, detail="group_by field is required. Either provide group_by or send a field in filters (e.g., {\"info/Province\": []}).")
    actual_group_by = service._resolve_field(group_by_field, path_mapping)
    filters_to_apply = {k: v for k, v in filters.items() if service._resolve_field(k, path_mapping) != actual_group_by}
    cache_key = {"form_id": form.id, "group_by": group_by_field, "filters": request.filters or {}}
    cached = service._get_cache("bar_chart", cache_key)
    if cached:
        return BarChartResponse(**cached)

    query = db.query(Submission).filter(Submission.form_id == form.id)
    query = _apply_filters_dict(query, service, form, filters_to_apply)
    col_expr = service._get_json_field(actual_group_by)
    if col_expr is None:
        fl = group_by_field.split("/")[-1].replace("_", " ").title()
        return BarChartResponse(form_id=form.id, group_by=group_by_field, items=[], total_submissions=0, unique_values=0, field_label=fl)

    rows = query.filter(col_expr.isnot(None), col_expr != "").with_entities(col_expr, func.count(Submission.id)).group_by(col_expr).all()
    counts = {}
    for (code, cnt) in rows:
        s = (str(code).strip().strip('"') if code else "") or ""
        if not s:
            continue
        label = _resolve_code_to_label(s, form, actual_group_by, group_by_field)
        counts[label] = counts.get(label, 0) + int(cnt)

    total_submissions_included = sum(counts.values())
    field_label = None
    if form.form_schema:
        try:
            schema = form.form_schema if isinstance(form.form_schema, dict) else json.loads(form.form_schema) if isinstance(form.form_schema, str) else {}
            for f in (schema.get("content") or schema).get("survey") or []:
                n = f.get("name", "")
                if n == group_by_field or (n or "").replace("/", "_") == (group_by_field or "").replace("/", "_"):
                    L = f.get("label", "")
                    field_label = (L[0] if isinstance(L, list) and L else L) if L else None
                    break
        except Exception:
            pass
    if not field_label:
        field_label = group_by_field.split("/")[-1].replace("_", " ").title()
    items = [BarChartItem(category=c, count=k) for c, k in sorted(counts.items(), key=lambda x: -x[1])]
    out = BarChartResponse(form_id=form.id, group_by=group_by_field, items=items, total_submissions=total_submissions_included, unique_values=len(counts), field_label=field_label)
    service._set_cache("bar_chart", cache_key, out.model_dump(), form.id)
    return out


@app.post("/api/charts/polar_area", response_model=PolarAreaChartResponse)
def generate_polar_area_chart(
    request: PolarAreaChartRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Polar area chart. Uses DB-side filtering and GROUP BY; label resolution in Python.
    """
    from analysis_service import AnalysisService

    form = db.query(FormModel).filter(FormModel.id == request.form_id).first()
    if not form:
        raise HTTPException(status_code=404, detail="Form not found")
    if not check_form_access(current_user, request.form_id, db):
        raise HTTPException(status_code=403, detail="Access denied to this form")

    service = AnalysisService(db)
    path_mapping = service._get_full_path_mapping(form)
    actual_field = service._resolve_field(request.field, path_mapping)
    filters = request.filters or {}
    cache_key = {"form_id": form.id, "field": request.field, "filters": filters}
    cached = service._get_cache("polar_area", cache_key)
    if cached:
        return PolarAreaChartResponse(**cached)

    query = db.query(Submission).filter(Submission.form_id == form.id)
    query = _apply_filters_dict(query, service, form, filters)
    total_submissions = query.count()
    col_expr = service._get_json_field(actual_field)
    if col_expr is None:
        fl = request.field.split("/")[-1].replace("_", " ").title()
        return PolarAreaChartResponse(form_id=request.form_id, field_name=request.field, field_label=fl, items=[], total_submissions=total_submissions, total_with_data=0, without_data=total_submissions, unique_values=0)

    rows = query.filter(col_expr.isnot(None), col_expr != "").with_entities(col_expr, func.count(Submission.id)).group_by(col_expr).all()
    counts = {}
    for (code, cnt) in rows:
        s = (str(code).strip().strip('"') if code else "") or ""
        if not s:
            continue
        label = _resolve_code_to_label(s, form, actual_field, request.field)
        counts[label] = counts.get(label, 0) + int(cnt)
    total_with_data = sum(counts.values())
    total = total_with_data or 1
    field_label = None
    if form.form_schema:
        try:
            schema = form.form_schema if isinstance(form.form_schema, dict) else json.loads(form.form_schema) if isinstance(form.form_schema, str) else {}
            for f in (schema.get("content") or schema).get("survey") or []:
                n = f.get("name", "")
                if (n or "").replace("/", "_") == (request.field or "").replace("/", "_"):
                    L = f.get("label", "")
                    field_label = (L[0] if isinstance(L, list) and L else L) if L else None
                    break
        except Exception:
            pass
    if not field_label:
        field_label = request.field.split("/")[-1].replace("_", " ").title()
    items = [PolarAreaItem(label=c, value=k, percentage=round((k / total * 100), 2)) for c, k in sorted(counts.items(), key=lambda x: -x[1])]
    out = PolarAreaChartResponse(form_id=request.form_id, field_name=request.field, field_label=field_label, items=items, total_submissions=total_submissions, total_with_data=total_with_data, without_data=total_submissions - total_with_data, unique_values=len(counts))
    service._set_cache("polar_area", cache_key, out.model_dump(), form.id)
    return out


@app.get("/api/indicators/{indicator_id}", response_model=IndicatorResponse)
def get_indicator(
    indicator_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Get a specific indicator.
    
    Checks if the user has access to the form associated with this indicator.
    """
    indicator = db.query(Indicator).filter(Indicator.id == indicator_id).first()
    if not indicator:
        raise HTTPException(status_code=404, detail="Indicator not found")
    
    # Check access to the parent form
    if not check_form_access(current_user, indicator.form_id, db):
        raise HTTPException(status_code=403, detail="Access denied to this indicator's form")
        
    return indicator


# ============================================================================
# Dashboard Endpoints
# ============================================================================

@app.get("/api/dashboard/summary", response_model=DashboardSummary)
def get_dashboard_summary(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Get dashboard summary.
    
    - Admins see global stats
    - Non-admin users see stats for their assigned forms only
    """
    form_ids_query = db.query(FormModel.id)
    submissions_query = db.query(Submission)
    indicators_query = db.query(Indicator)
    
    if current_user.role != "admin":
        accessible_form_ids = (
            db.query(UserFormAccess.form_id)
            .filter(UserFormAccess.user_id == current_user.id)
            .all()
        )
        form_ids = [f[0] for f in accessible_form_ids]
        if not form_ids:
            return DashboardSummary(
                total_forms=0,
                total_submissions=0,
                total_indicators=0,
                recent_submissions=0,
                forms_by_category={},
                submissions_by_date=[]
            )
        form_ids_query = form_ids_query.filter(FormModel.id.in_(form_ids))
        submissions_query = submissions_query.filter(Submission.form_id.in_(form_ids))
        indicators_query = indicators_query.filter(Indicator.form_id.in_(form_ids))

    total_forms = form_ids_query.count()
    total_submissions = submissions_query.count()
    total_indicators = indicators_query.count()
    
    # Recent submissions: count of the last 30 records (by created_at), not a time window
    recent_submissions = len(
        submissions_query
        .order_by(Submission.created_at.desc())
        .limit(30)
        .all()
    )
    
    # Forms by category
    forms_by_category = {}
    categories = form_ids_query.with_entities(FormModel.category).distinct().all()
    for (category,) in categories:
        if category:
            count = form_ids_query.filter(FormModel.category == category).count()
            forms_by_category[category] = count
    
    # Submissions by date (last 30 days)
    submissions_by_date = []
    for i in range(30):
        date = datetime.utcnow() - timedelta(days=29 - i)
        date_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        date_end = date.replace(hour=23, minute=59, second=59, microsecond=999999)
        count = (
            submissions_query
            .filter(Submission.created_at >= date_start, Submission.created_at <= date_end)
            .count()
        )
        submissions_by_date.append({"date": date_start.isoformat(), "count": count})
    
    return DashboardSummary(
        total_forms=total_forms,
        total_submissions=total_submissions,
        total_indicators=total_indicators,
        recent_submissions=recent_submissions,
        forms_by_category=forms_by_category,
        submissions_by_date=submissions_by_date,
    )


@app.get("/api/dashboard/indicators", response_model=IndicatorDashboardData)
def get_indicator_dashboard(
    category: str = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Get indicator dashboard data.
    
    - Admins see all indicators
    - Non-admin users see only indicators for their assigned forms
    """
    query = db.query(Indicator)
    
    form_ids = []
    if current_user.role != "admin":
        accessible_form_ids = (
            db.query(UserFormAccess.form_id)
            .filter(UserFormAccess.user_id == current_user.id)
            .all()
        )
        form_ids = [f[0] for f in accessible_form_ids]
        if not form_ids:
            return IndicatorDashboardData(indicators=[], trends=[], by_category={})
        query = query.filter(Indicator.form_id.in_(form_ids))

    if category:
        query = query.join(FormModel).filter(FormModel.category == category)
    
    indicators = query.all()
    
    # Group by category
    by_category = {}
    for indicator in indicators:
        form = db.query(FormModel).filter(FormModel.id == indicator.form_id).first()
        cat = form.category or "uncategorized"
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(indicator)
    
    # Trends (last 30 days of indicator computations)
    trends = []
    for i in range(30):
        date = datetime.utcnow() - timedelta(days=29 - i)
        date_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        date_end = date.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        trends_query = db.query(func.count(Indicator.id)).filter(
            Indicator.computed_at >= date_start, 
            Indicator.computed_at <= date_end
        )
        
        if current_user.role != "admin":
            trends_query = trends_query.filter(Indicator.form_id.in_(form_ids))
            
        count = trends_query.scalar()
        trends.append({"date": date_start.isoformat(), "count": count})
    
    return IndicatorDashboardData(
        indicators=[IndicatorResponse.model_validate(ind) for ind in indicators],
        trends=trends,
        by_category={k: [IndicatorResponse.model_validate(i) for i in v] for k, v in by_category.items()},
    )


@app.get("/api/dashboard/accountability", response_model=AccountabilityDashboardData)
def get_accountability_dashboard(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Get accountability and complaints dashboard data.
    
    - Admins see all accountability data
    - Non-admin users see data for their assigned forms only
    """
    # Get complaints (assuming forms with category "complaints" or "accountability")
    query = db.query(FormModel).filter(
        (FormModel.category == "complaints") | (FormModel.category == "accountability")
    )
    
    if current_user.role != "admin":
        accessible_form_ids = (
            db.query(UserFormAccess.form_id)
            .filter(UserFormAccess.user_id == current_user.id)
            .all()
        )
        form_ids = [f[0] for f in accessible_form_ids]
        if not form_ids:
            return AccountabilityDashboardData(
                complaints=[],
                complaints_by_status={},
                complaints_by_location=[],
                trends=[]
            )
        query = query.filter(FormModel.id.in_(form_ids))
        
    complaint_forms = query.all()
    
    form_ids = [f.id for f in complaint_forms]
    complaints = db.query(Submission).filter(Submission.form_id.in_(form_ids)).all() if form_ids else []
    
    # Complaints by status (extract from submission data)
    complaints_by_status = {}
    for complaint in complaints:
        status_val = complaint.submission_data.get("status") or complaint.submission_data.get("complaint_status") or "unknown"
        complaints_by_status[status_val] = complaints_by_status.get(status_val, 0) + 1
    
    # Complaints by location
    complaints_by_location = []
    for complaint in complaints:
        if complaint.location_lat and complaint.location_lng:
            complaints_by_location.append({
                "lat": complaint.location_lat,
                "lng": complaint.location_lng,
                "name": complaint.location_name or "Unknown",
                "count": 1,
            })
    
    # Trends
    trends = []
    for i in range(30):
        date = datetime.utcnow() - timedelta(days=29 - i)
        date_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        date_end = date.replace(hour=23, minute=59, second=59, microsecond=999999)
        count = (
            db.query(func.count(Submission.id))
            .filter(
                Submission.form_id.in_(form_ids),
                Submission.created_at >= date_start,
                Submission.created_at <= date_end,
            )
            .scalar() if form_ids else 0
        )
        trends.append({"date": date_start.isoformat(), "count": count})
    
    return AccountabilityDashboardData(
        complaints=[SubmissionResponse.model_validate(c) for c in complaints],
        complaints_by_status=complaints_by_status,
        complaints_by_location=complaints_by_location,
        trends=trends,
    )


# ============================================================================
# NGO Reports & Dashboards - NEW
# ============================================================================

@app.get("/api/reports/submissions/time-series", response_model=TimeSeriesResponse)
def get_time_series_report(
    request: Request,
    form_id: Optional[int] = None,
    asset_uid: Optional[str] = None,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    year: Optional[int] = None,
    month: Optional[int] = None,
    tz: str = "Asia/Kabul",
    group_by: GroupBy = GroupBy.day,
    mode: TimeSeriesMode = TimeSeriesMode.range,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Get time series report for form submissions.
    
    Supports filtering by form_id/asset_uid, date range, year/month, and any other field filters.
    """
    if asset_uid:
        form = db.query(FormModel).filter(FormModel.kobo_form_id == asset_uid).first()
        if not form:
            raise HTTPException(status_code=404, detail="Form not found")
        form_id = form.id
    else:
        form = db.query(FormModel).filter(FormModel.id == form_id).first()
        
    if not form:
        raise HTTPException(status_code=400, detail="Valid form_id or asset_uid is required")
        
    if not check_form_access(current_user, form.id, db):
        raise HTTPException(status_code=403, detail="Access denied to this form")
        
    try:
        # Resolve Year/Month Convenience
        if year:
            mode = TimeSeriesMode.range
            if month:
                start = datetime(year, month, 1)
                if month == 12:
                    end = datetime(year + 1, 1, 1)
                else:
                    end = datetime(year, month + 1, 1)
                if group_by in [GroupBy.year, GroupBy.month]:
                    group_by = GroupBy.day
            else:
                start = datetime(year, 1, 1)
                end = datetime(year + 1, 1, 1)
                if group_by == GroupBy.year:
                    group_by = GroupBy.month
        elif group_by == GroupBy.year and not start and not end:
            mode = TimeSeriesMode.all_time

        # Build dynamic field filters from query parameters
        field_filters = {}
        field_labels = {}
        
        # Reserved parameters to exclude from field filters
        reserved = [
            'form_id', 'asset_uid', 'start', 'end', 'year', 'month', 
            'tz', 'group_by', 'mode', 'token'
        ]
        
        # Helper to get label from schema
        def get_label(field_name):
            if not form.form_schema: return field_name.split("/")[-1].title()
            survey = form.form_schema.get("content", {}).get("survey", [])
            for q in survey:
                if q.get("name") == field_name or q.get("name") == field_name.split("/")[-1]:
                    label = q.get("label", field_name)
                    if isinstance(label, list) and len(label) > 0:
                        label = label[0]
                    elif isinstance(label, dict):
                        # Try to get English or the first available language
                        label = label.get("English", label.get("en", next(iter(label.values()), field_name)))
                    return str(label)
            return field_name.split("/")[-1].title()

        # Capture all other query params as filters
        for key, value in request.query_params.items():
            if key in reserved or not value or value.lower() == "all":
                continue
            
            # Map common shortcuts to full paths
            target_key = key
            if key == "province": target_key = "info/province"
            elif key == "region": target_key = "info/region"
            elif key == "district": target_key = "info/district"
            
            field_filters[target_key] = value
            field_labels[key] = get_label(target_key)
        
        report_service = ReportService(db)
        result = report_service.get_time_series_report(
            form_id=form.id,
            start=start,
            end=end,
            tz=tz,
            group_by=group_by,
            mode=mode,
            filters={"field_filters": field_filters}
        )
        
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
            
        result["field_labels"] = field_labels
        return result
    except Exception as e:
        logger.error(f"Error generating time series report: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/reports/survey-summary/{form_id}")
def get_survey_summary(
    form_id: int,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Get survey summary report for a form.
    
    Includes: total submissions, completion rate, question-wise summaries.
    """
    if not check_form_access(current_user, form_id, db):
        raise HTTPException(status_code=403, detail="Access denied to this form")
    
    try:
        filters_request = {
            "date_from": date_from,
            "date_to": date_to,
            "locations": [],
            "form_ids": [form_id],
            "field_filters": {},
            "exclude_incomplete": False,
        }
        
        report_service = ReportService(db)
        result = report_service.get_survey_summary(form_id, filters_request)
        
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        
        return result
    except Exception as e:
        logger.error(f"Error generating survey summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/reports/indicators")
def get_indicator_report(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    category: Optional[str] = None,
    form_ids: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Get KPI indicator report with all key metrics.
    
    Supports filtering by date range, category (WASH, Nutrition, Protection, etc.), and form IDs.
    """
    try:
        form_id_list = []
        if form_ids:
            form_id_list = [int(x) for x in form_ids.split(",")]
            # Check access for all provided forms
            for fid in form_id_list:
                if not check_form_access(current_user, fid, db):
                    raise HTTPException(status_code=403, detail=f"Access denied to form {fid}")
        elif current_user.role != "admin":
            # If no forms provided, only show accessible forms
            accessible_form_ids = (
                db.query(UserFormAccess.form_id)
                .filter(UserFormAccess.user_id == current_user.id)
                .all()
            )
            form_id_list = [f[0] for f in accessible_form_ids]
            if not form_id_list:
                return {"indicators": [], "trends": [], "by_category": {}, "total_submissions": 0}
        
        filters_request = {
            "date_from": date_from,
            "date_to": date_to,
            "locations": [],
            "form_ids": form_id_list,
            "field_filters": {},
            "exclude_incomplete": False,
        }
        
        report_service = ReportService(db)
        result = report_service.get_indicator_report(
            filters_request,
            category=category
        )
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return result
    except Exception as e:
        logger.error(f"Error generating indicator report: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/reports/demographics")
def get_demographics_report(
    form_id: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Get demographics report with age, gender, household size distributions.
    
    Automatically detects demographic fields from form schema.
    Works with Child Protection & Education forms.
    """
    if form_id and not check_form_access(current_user, form_id, db):
        raise HTTPException(status_code=403, detail="Access denied to this form")
        
    try:
        form_ids = [form_id] if form_id else []
        if not form_id and current_user.role != "admin":
            # Filter by accessible forms
            accessible_form_ids = (
                db.query(UserFormAccess.form_id)
                .filter(UserFormAccess.user_id == current_user.id)
                .all()
            )
            form_ids = [f[0] for f in accessible_form_ids]
            if not form_ids:
                return {"age_distribution": [], "gender_distribution": [], "household_size_distribution": [], "total_submissions": 0}

        filters_request = {
            "date_from": date_from,
            "date_to": date_to,
            "locations": [],
            "form_ids": form_ids,
            "field_filters": {},
            "exclude_incomplete": False,
        }
        
        report_service = ReportService(db)
        result = report_service.get_demographics(
            filters_request,
            form_id=form_id
        )
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return result
    except Exception as e:
        logger.error(f"Error generating demographics report: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/reports/geo")
def get_geospatial_report(
    form_id: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Get geospatial report with GPS points, coverage, and bounds.
    
    Shows where surveys were conducted and coverage by location.
    """
    if form_id and not check_form_access(current_user, form_id, db):
        raise HTTPException(status_code=403, detail="Access denied to this form")

    try:
        form_ids = [form_id] if form_id else []
        if not form_id and current_user.role != "admin":
            # Filter by accessible forms
            accessible_form_ids = (
                db.query(UserFormAccess.form_id)
                .filter(UserFormAccess.user_id == current_user.id)
                .all()
            )
            form_ids = [f[0] for f in accessible_form_ids]
            if not form_ids:
                return {"points": [], "bounds": None, "total_submissions": 0}

        filters_request = {
            "date_from": date_from,
            "date_to": date_to,
            "locations": [],
            "form_ids": form_ids,
            "field_filters": {},
            "exclude_incomplete": False,
        }
        
        report_service = ReportService(db)
        result = report_service.get_geospatial(
            filters_request,
            form_id=form_id
        )
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return result
    except Exception as e:
        logger.error(f"Error generating geospatial report: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/reports/trends/{kpi_code}")
def get_trend_report(
    kpi_code: str,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    granularity: Optional[str] = "monthly",
    form_ids: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Get trend report for a KPI over time.
    
    Shows KPI values with specified granularity (daily, weekly, monthly, quarterly, annual).
    """
    try:
        form_id_list = []
        if form_ids:
            form_id_list = [int(x) for x in form_ids.split(",")]
            # Check access for all provided forms
            for fid in form_id_list:
                if not check_form_access(current_user, fid, db):
                    raise HTTPException(status_code=403, detail=f"Access denied to form {fid}")
        elif current_user.role != "admin":
            # If no forms provided, only show accessible forms
            accessible_form_ids = (
                db.query(UserFormAccess.form_id)
                .filter(UserFormAccess.user_id == current_user.id)
                .all()
            )
            form_id_list = [f[0] for f in accessible_form_ids]
            if not form_id_list:
                return {"kpi_code": kpi_code, "granularity": granularity, "data": [], "total_submissions": 0}
        
        filters_request = {
            "date_from": date_from,
            "date_to": date_to,
            "locations": [],
            "form_ids": form_id_list,
            "field_filters": {},
            "exclude_incomplete": False,
        }
        
        report_service = ReportService(db)
        result = report_service.get_trends(
            kpi_code,
            filters_request,
            granularity=granularity
        )
        
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        
        return result
    except Exception as e:
        logger.error(f"Error generating trend report: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/reports/program-comparison")
def get_program_comparison_report(
    dimension: str = "form_id",
    kpi_code: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Get program comparison report comparing KPIs across forms/locations/programs.
    
    dimension: 'form_id', 'location', 'district', or any custom field
    kpi_code: KPI to compare (required)
    
    - Admins see comparison across all forms
    - Non-admin users see comparison across their assigned forms only
    """
    try:
        if not kpi_code:
            raise HTTPException(status_code=400, detail="kpi_code is required")
        
        form_ids = []
        if current_user.role != "admin":
            accessible_form_ids = (
                db.query(UserFormAccess.form_id)
                .filter(UserFormAccess.user_id == current_user.id)
                .all()
            )
            form_ids = [f[0] for f in accessible_form_ids]
            if not form_ids:
                return {"dimension": dimension, "kpi_code": kpi_code, "data": [], "total_submissions": 0}

        filters_request = {
            "date_from": date_from,
            "date_to": date_to,
            "locations": [],
            "form_ids": form_ids,
            "field_filters": {},
            "exclude_incomplete": False,
        }
        
        report_service = ReportService(db)
        result = report_service.get_program_comparison(
            dimension,
            [kpi_code],
            filters_request
        )
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating program comparison report: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/kpis", response_model=list[KPIDefinitionResponse])
def list_kpis(
    category: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    List all available KPI definitions.
    
    Optionally filter by category (WASH, Nutrition, Protection, Education, Food Security, Livelihoods).
    """
    try:
        kpi_engine = KPIEngine(db)
        kpis = kpi_engine.list_kpis(category=category, include_custom=True)
        
        return [
            KPIDefinitionResponse.model_validate(kpi)
            for kpi in kpis
        ]
    except Exception as e:
        logger.error(f"Error listing KPIs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Sync Endpoints
# ============================================================================

def run_sync_in_background(sync_log_id: int, form_id: Optional[int], sync_type: str):
    """Background task to run sync operation. After sync, runs reverse geocoding on DB lat/lng (no extra sync time)."""
    from database import SessionLocal
    db = SessionLocal()
    try:
        # Mark stale "running" syncs as timed out (e.g. worker killed when other forms take too long on PythonAnywhere)
        threshold = datetime.utcnow() - timedelta(minutes=15)
        for s in db.query(SyncLog).filter(SyncLog.status == "running", SyncLog.started_at < threshold):
            s.status = "error"
            s.error_message = "Sync timed out or was interrupted"
            s.completed_at = datetime.utcnow()
        db.commit()

        etl = ETLPipeline(db)
        sync_log = db.query(SyncLog).filter(SyncLog.id == sync_log_id).first()
        
        if not sync_log:
            logger.error(f"Sync log {sync_log_id} not found")
            return

        sync_progress_store.set(sync_log.id, sync_progress_store.from_sync_log(sync_log))
        
        try:
            if form_id:
                # Sync specific form
                form = db.query(FormModel).filter(FormModel.id == form_id).first()
                if not form:
                    sync_log.status = "error"
                    sync_log.error_message = "Form not found"
                    sync_log.completed_at = datetime.utcnow()
                    db.commit()
                    sync_progress_store.set(sync_log.id, sync_progress_store.from_sync_log(sync_log))
                    return
                etl.sync_form(form.kobo_form_id, sync_type=sync_type, sync_log=sync_log)
            else:
                # Sync all forms
                etl.sync_all_forms(sync_type=sync_type, parent_sync_log=sync_log)
            # After sync: reverse geocode from DB (location_lat/lng). Runs in same background task; sync already "complete" to user.
            # Process up to 500 per run; for large syncs run 2 passes. Nominatim allows ~1 req/s; limit keeps sync responsive.
            try:
                total_updated, total_processed = 0, 0
                for _ in range(2):
                    u, p = etl.geocode_pending_submissions(form_id=form_id, limit=500)
                    total_updated += u
                    total_processed += p
                    if p == 0:
                        break
                if total_processed > 0:
                    logger.info(f"Geocode-pending after sync: updated={total_updated}, processed={total_processed}")
            except Exception as ge:
                logger.warning(f"Geocode-pending after sync failed (non-fatal): {ge}")
        except Exception as e:
            logger.error(f"Sync error in background task: {e}", exc_info=True)
            sync_log.status = "error"
            sync_log.error_message = str(e)
            sync_log.completed_at = datetime.utcnow()
            db.commit()
            sync_progress_store.set(sync_log.id, sync_progress_store.from_sync_log(sync_log))
    finally:
        db.close()

@app.post("/api/sync", response_model=SyncLogResponse)
def sync_forms(
    sync_request: SyncRequest,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """Sync forms from Kobo (admin only). Returns immediately and runs sync in a daemon thread.
    Using a thread (not BackgroundTasks) avoids blocking the single worker on PythonAnywhere:
    when form 1's sync runs, the worker stays free so form 2's POST /api/sync can be handled."""
    try:
        # Create sync log entry
        sync_log = SyncLog(
            sync_type=sync_request.sync_type,
            status="running",
            started_at=datetime.utcnow(),
            total_forms=1 if sync_request.form_id else 0,  # Will be updated when we know total
            current_form_index=0,
        )
        db.add(sync_log)
        db.flush()
        
        form_id = None
        if sync_request.form_id:
            form = db.query(FormModel).filter(FormModel.id == sync_request.form_id).first()
            if not form:
                raise HTTPException(status_code=404, detail="Form not found")
            form_id = form.id
        
        db.commit()

        # In-memory progress: allow SSE/polling/WS to read before first ETL update
        sync_progress_store.set(sync_log.id, sync_progress_store.from_sync_log(sync_log))
        
        # Run sync in a daemon thread so the worker is not blocked (fixes form 2+ POST timing out when form 1 sync is still running)
        threading.Thread(
            target=run_sync_in_background,
            args=(sync_log.id, form_id, sync_request.sync_type),
            daemon=True,
        ).start()
        
        return SyncLogResponse.model_validate(sync_log)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Sync error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")


@app.delete("/api/forms/{form_id}/data")
def clear_form_data(
    form_id: int,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """Clear all submissions and related data for a form (admin only)."""
    form = db.query(FormModel).filter(FormModel.id == form_id).first()
    if not form:
        raise HTTPException(status_code=404, detail="Form not found")
    
    # Check access for non-admin users
    if not check_form_access(current_user, form_id, db):
        raise HTTPException(status_code=403, detail="Access denied to this form")
    
    try:
        # Delete indicators
        indicators_count = db.query(Indicator).filter(Indicator.form_id == form_id).count()
        db.query(Indicator).filter(Indicator.form_id == form_id).delete()
        
        # Delete submissions
        submissions_count = db.query(Submission).filter(Submission.form_id == form_id).count()
        db.query(Submission).filter(Submission.form_id == form_id).delete()
        
        # Delete raw submissions
        raw_submissions_count = db.query(RawSubmission).filter(RawSubmission.form_id == form_id).count()
        db.query(RawSubmission).filter(RawSubmission.form_id == form_id).delete()
        
        # Delete sync logs for this form
        sync_logs_count = db.query(SyncLog).filter(SyncLog.form_id == form_id).count()
        db.query(SyncLog).filter(SyncLog.form_id == form_id).delete()
        
        # Reset last_synced_at
        form.last_synced_at = None
        
        db.commit()
        
        return {
            "form_id": form_id,
            "form_title": form.title,
            "deleted": {
                "indicators": indicators_count,
                "submissions": submissions_count,
                "raw_submissions": raw_submissions_count,
                "sync_logs": sync_logs_count,
            },
            "message": "Form data cleared successfully. You can now re-sync from Kobo.",
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Error clearing form data for form {form_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error clearing form data: {str(e)}")


@app.get("/api/sync/logs", response_model=list[SyncLogResponse])
def get_sync_logs(
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """Get sync logs (admin only)."""
    logs = (
        db.query(SyncLog)
        .order_by(desc(SyncLog.started_at))
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [SyncLogResponse.model_validate(log) for log in logs]


@app.post("/api/submissions/geocode-pending")
def geocode_pending_submissions(
    form_id: Optional[int] = None,
    limit: int = 50,
    validate_only: bool = False,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """
    Reverse geocode from location_lat/lng (start-geopoint or manual gps_location). Run after sync.
    - validate_only=false: fill location_name for those missing it; set gps_consistent.
    - validate_only=true: run on ALL with GPS, set gps_resolved_* and gps_consistent only (for survey accuracy: form vs GPS).
    Inaccurate survey: form "Sholgara, Balkh" but GPS "Kabul" -> cleaned_data.gps_consistent=false, survey_location_warning set.
    """
    etl = ETLPipeline(db)
    updated, processed = etl.geocode_pending_submissions(form_id=form_id, limit=limit, validate_only=validate_only)
    return {"updated": updated, "processed": processed, "message": f"Geocoded {updated} of {processed} pending."}


# ============================================================================
# Webhook Endpoint (Kobo REST Services)
# ============================================================================

@app.post("/api/webhooks/kobo")
def kobo_webhook(
    payload: dict,  # Kobo REST Services send raw submission JSON
    db: Session = Depends(get_db),
):
    """
    Webhook endpoint for Kobo form submissions (REST Services).

    Kobo's REST Services feature sends the **raw submission JSON** without any
    wrapper like `event_type` or `data`. Previously we expected a structured
    `WebhookPayload`, which caused 422 errors. This handler now:

    - Accepts arbitrary JSON (`dict`)
    - Extracts the Kobo form ID from `_xform_id_string` (or fallbacks)
    - Triggers an incremental sync for that form via the ETL pipeline
    """
    try:
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="Invalid payload format, expected JSON object")

        # Try to detect the Kobo form identifier from the submission
        kobo_form_id = (
            payload.get("_xform_id_string")
            or payload.get("formhub/uuid")
            or payload.get("form_id")
        )

        if not kobo_form_id:
            logger.warning(f"Webhook received without form identifier. Payload keys: {list(payload.keys())}")
            return {
                "status": "ignored",
                "message": "No form identifier (_xform_id_string/formhub/uuid/form_id) provided",
            }

        logger.info(f"Received Kobo REST webhook for form {kobo_form_id} with submission id {payload.get('_id')}")

        # Run incremental sync for this Kobo form id
        etl = ETLPipeline(db)
        sync_log = etl.sync_form(str(kobo_form_id), sync_type="incremental")
        form_id = sync_log.form_id

        # Reverse geocode from DB (lat/lng) in background so webhook returns fast; ~1s per unique location.
        def _geocode_after_webhook():
            from database import SessionLocal
            _db = SessionLocal()
            try:
                _etl = ETLPipeline(_db)
                _etl.geocode_pending_submissions(form_id=form_id, limit=50)
            except Exception as e:
                logger.warning(f"Geocode-pending after webhook failed: {e}")
            finally:
                _db.close()

        threading.Thread(target=_geocode_after_webhook, daemon=True).start()

        return {
            "status": "success",
            "kobo_form_id": str(kobo_form_id),
            "sync_log_id": sync_log.id,
            "records_added": sync_log.records_added,
        }
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Webhook processing error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Form Schema & Dynamic Fields Endpoints
# ============================================================================

@app.get("/api/forms/{form_id}/schema")
def get_form_schema(
    form_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Get form schema for dynamic filter generation."""
    form = db.query(FormModel).filter(FormModel.id == form_id).first()
    if not form:
        raise HTTPException(status_code=404, detail="Form not found")
    
    # Check access for non-admin users
    if not check_form_access(current_user, form_id, db):
        raise HTTPException(status_code=403, detail="Access denied to this form")
    
    return {
        "form_id": form.id,
        "form_name": form.title,
        "schema": form.form_schema or {},
    }


@app.get("/api/forms/{form_id}/debug-schema")
def debug_form_schema(
    form_id: int,
    field_name: str = "info/province",
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Debug endpoint to inspect form schema structure for label lookup."""
    form = db.query(FormModel).filter(FormModel.id == form_id).first()
    if not form:
        raise HTTPException(status_code=404, detail="Form not found")
    
    # Check access for non-admin users
    if not check_form_access(current_user, form_id, db):
        raise HTTPException(status_code=403, detail="Access denied to this form")
    
    schema = form.form_schema or {}
    if isinstance(schema, str):
        import json
        try:
            schema = json.loads(schema)
        except:
            schema = {}
    
    # Try to find the field and its choice list
    content = schema.get("content", schema)
    survey = content.get("survey", [])
    choices_lists = content.get("choices", [])
    
    field_info = None
    for field in survey:
        if field.get("name") == field_name or field.get("name", "").endswith(field_name.split("/")[-1]):
            field_info = {
                "name": field.get("name"),
                "type": field.get("type"),
                "choice": field.get("choice"),
                "select_from_list_name": field.get("select_from_list_name"),
            }
            break
    
    choice_list_info = None
    if field_info and (field_info.get("choice") or field_info.get("select_from_list_name")):
        choice_list_name = field_info.get("choice") or field_info.get("select_from_list_name")
        for cl in choices_lists:
            if cl.get("name") == choice_list_name:
                choice_list_info = {
                    "name": cl.get("name"),
                    "choices_count": len(cl.get("choices", [])),
                    "sample_choices": [
                        {
                            "name": c.get("name"),
                            "label": c.get("label"),
                        }
                        for c in cl.get("choices", [])[:5]
                    ],
                }
                break
    
    return {
        "form_id": form_id,
        "field_name": field_name,
        "schema_structure": {
            "has_content": "content" in schema,
            "has_survey": "survey" in (schema.get("content", {}) or schema),
            "has_choices": "choices" in (schema.get("content", {}) or schema),
            "survey_fields_count": len(survey),
            "choices_lists_count": len(choices_lists),
        },
        "field_info": field_info,
        "choice_list_info": choice_list_info,
    }


@app.get("/api/forms/{form_id}/filter-fields")
def get_form_filter_fields(
    form_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Get available filter fields for a form based on its schema."""
    form = db.query(FormModel).filter(FormModel.id == form_id).first()
    if not form:
        raise HTTPException(status_code=404, detail="Form not found")
    
    # Check access for non-admin users
    if not check_form_access(current_user, form_id, db):
        raise HTTPException(status_code=403, detail="Access denied to this form")
    
    # Handle form_schema - it might be a dict, JSON string, or None
    schema = form.form_schema or {}
    if isinstance(schema, str):
        try:
            schema = json.loads(schema)
        except (json.JSONDecodeError, TypeError):
            schema = {}
    if not isinstance(schema, dict):
        schema = {}
    
    filter_fields = []
    
    # Extract fields from Kobo form schema
    try:
        content = schema.get("content", {})
        if not isinstance(content, dict):
            content = {}
        survey = content.get("survey", [])
        if not isinstance(survey, list):
            survey = []
        
        for field in survey:
            if not isinstance(field, dict):
                continue
            field_type = field.get("type", "")
            field_name = field.get("name", "")
            if not field_name:
                continue
            
            # Handle label - can be a list or string
            label_value = field.get("label", field_name)
            if isinstance(label_value, list) and len(label_value) > 0:
                label = label_value[0]
            elif isinstance(label_value, str):
                label = label_value
            else:
                label = field_name
            
            # Include select_one, select_multiple, text, integer, decimal, date, geopoint
            if field_type in ["select_one", "select_multiple", "text", "integer", "decimal", "date", "geopoint"]:
                options = []
                if field_type in ["select_one", "select_multiple"]:
                    choices = field.get("select_from_list_name")
                    if not choices:
                        # Try alternative field name
                        choices = field.get("select_from_list")
                    
                    if choices:
                        # Get choices from choices list
                        choices_list = content.get("choices", [])
                        if not choices_list:
                            # Try alternative location in schema
                            choices_list = schema.get("choices", [])
                        
                        if isinstance(choices_list, list):
                            for choice_group in choices_list:
                                if not isinstance(choice_group, dict):
                                    continue
                                list_name = choice_group.get("list_name")
                                if list_name == choices:
                                    group_choices = choice_group.get("choices", [])
                                    if not group_choices:
                                        # Try alternative field name
                                        group_choices = choice_group.get("items", [])
                                    
                                    if isinstance(group_choices, list):
                                        for c in group_choices:
                                            if not isinstance(c, dict):
                                                continue
                                            choice_name = c.get("name", "")
                                            if not choice_name:
                                                choice_name = c.get("value", "")
                                            
                                            choice_label_value = c.get("label", choice_name)
                                            if isinstance(choice_label_value, list) and len(choice_label_value) > 0:
                                                choice_label = choice_label_value[0]
                                            elif isinstance(choice_label_value, str):
                                                choice_label = choice_label_value
                                            else:
                                                choice_label = choice_name
                                            
                                            options.append({
                                                "value": choice_name,
                                                "label": choice_label
                                            })
                                    break
                
                filter_fields.append({
                    "name": field_name,
                    "label": label,
                    "type": field_type,
                    "options": options,
                })
    except Exception as e:
        logger.error(f"Error parsing form schema for form {form_id}: {e}", exc_info=True)
    
    # Also check actual submission/cleaned data for additional fields and extract options
    try:
        submissions = db.query(Submission).filter(Submission.form_id == form_id).limit(1000).all()
        if submissions:
            # Get unique keys from submission data and extract unique values for options
            seen_fields = {f["name"] for f in filter_fields}
            field_value_counts = {}  # Track unique values per field
            
            for submission in submissions:
                # Prefer cleaned_data (normalized) over raw submission_data
                payload = submission.cleaned_data or submission.submission_data
                if not payload or not isinstance(payload, dict):
                    continue

                for key, value in payload.items():
                    if key.startswith("_"):
                        continue
                    
                    # Track unique values for options
                    if key not in field_value_counts:
                        field_value_counts[key] = set()
                    
                    if value is not None and value != "":
                        if isinstance(value, list):
                            field_value_counts[key].update(str(v) for v in value if v)
                        else:
                            field_value_counts[key].add(str(value))
                    
                    # Add field if not already in filter_fields
                    if key not in seen_fields:
                        # Try to find the field type from schema
                        field_type = "text"
                        for field in filter_fields:
                            if field["name"] == key:
                                field_type = field.get("type", "text")
                                break
                        
                        filter_fields.append({
                            "name": key,
                            "label": key.replace("_", " ").title(),
                            "type": field_type,
                            "options": [],
                        })
                        seen_fields.add(key)
            
            # Update options for all fields based on actual data
            # Only keep fields that have actual data
            fields_with_data = []
            for field in filter_fields:
                field_name = field["name"]
                if field_name in field_value_counts and field_value_counts[field_name]:
                    # Only include if field has at least one value
                    unique_values = sorted(field_value_counts[field_name])
                    # Populate options for select fields and text fields with data
                    if field["type"] in ["select_one", "select_multiple", "text"]:
                        # Only update if options are empty or for text fields
                        if not field["options"] or field["type"] == "text":
                            field["options"] = [
                                {"value": val, "label": val.replace("_", " ").title() if len(unique_values) <= 50 else val}
                                for val in unique_values[:100]  # Limit to 100 options
                            ]
                    fields_with_data.append(field)
                elif field["type"] in ["select_one", "select_multiple"] and field["options"]:
                    # Include select fields from schema even if no data yet (they have predefined options)
                    fields_with_data.append(field)
            
            filter_fields = fields_with_data
    except Exception as e:
        logger.error(f"Error extracting fields from submissions for form {form_id}: {e}", exc_info=True)
    
    # Ensure high-value analytical filters are present if underlying data exists
    high_value_fields = {
        "province": "Province",
        "district": "District",
        "gender": "Gender",
        "age_group": "Age Group",
    }
    existing_field_names = {f["name"] for f in filter_fields}

    try:
        submissions = db.query(Submission).filter(Submission.form_id == form_id).limit(2000).all()
        field_value_counts = {}
        for submission in submissions:
            payload = submission.cleaned_data or submission.submission_data
            if not payload or not isinstance(payload, dict):
                continue
            for field_name, label in high_value_fields.items():
                if field_name in payload and payload[field_name] not in (None, ""):
                    if field_name not in field_value_counts:
                        field_value_counts[field_name] = set()
                    value = payload[field_name]
                    if isinstance(value, list):
                        field_value_counts[field_name].update(str(v) for v in value if v)
                    else:
                        field_value_counts[field_name].add(str(value))

        for field_name, label in high_value_fields.items():
            if field_name in field_value_counts and field_name not in existing_field_names:
                options = sorted(field_value_counts[field_name])
                filter_fields.append(
                    {
                        "name": field_name,
                        "label": label,
                        "type": "select_one",
                        "options": [
                            {"value": val, "label": val.replace("_", " ").title()}
                            for val in options[:100]
                        ],
                    }
                )
    except Exception as e:
        logger.error(f"Error enriching high-value filters for form {form_id}: {e}", exc_info=True)

    return {"form_id": form_id, "filter_fields": filter_fields}


@app.get("/form/{form_id}/filters")
def get_form_filters_public(
    form_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Public alias for dynamic filter metadata:
    `/form/{id}/filters`.
    """
    return get_form_filter_fields(form_id=form_id, current_user=current_user, db=db)


@app.post("/api/forms/{form_id}/chart-data")
def get_form_chart_data(
    form_id: int,
    request_data: ChartDataRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Get chart data for a form with filters and dimension."""
    try:
        chart_type = request_data.chart_type
        dimension = request_data.dimension
        secondary_dimension = request_data.secondary_dimension
        filters = request_data.filters or {}
        time_dimension = request_data.time_dimension
        bin_count = request_data.bin_count or 10
        
        if not dimension:
            raise HTTPException(status_code=400, detail="dimension is required")
        
        form = db.query(FormModel).filter(FormModel.id == form_id).first()
        if not form:
            raise HTTPException(status_code=404, detail="Form not found")
            
        # Check access for non-admin users
        if not check_form_access(current_user, form_id, db):
            raise HTTPException(status_code=403, detail="Access denied to this form")
            
        # Smart Dimension Resolution (Mirror AnalysisService logic)
        from analysis_service import AnalysisService
        service = AnalysisService(db)
        path_mapping = service._get_full_path_mapping(form)
        
        actual_dimension = service._resolve_field(dimension, path_mapping)
        actual_secondary = service._resolve_field(secondary_dimension, path_mapping)
        actual_time = service._resolve_field(time_dimension, path_mapping)
        
        # Use resolved names for processing
        dimension = actual_dimension
        secondary_dimension = actual_secondary
        time_dimension = actual_time

        def _q():
            return _apply_filters_dict(db.query(Submission).filter(Submission.form_id == form_id), service, form, request_data.filters or {})

        cache_key = {"form_id": form_id, "chart_type": chart_type, "dimension": request_data.dimension, "secondary_dimension": request_data.secondary_dimension, "time_dimension": request_data.time_dimension, "bin_count": request_data.bin_count or 10, "filters": request_data.filters or {}}
        cached = service._get_cache("chart_data", cache_key)
        if cached:
            return cached

        total = _q().count()
        if total == 0:
            return {"form_id": form_id, "chart_type": chart_type, "dimension": dimension, "data": [], "total": 0}

        apply_age = (request_data.dimension or "").lower() in ["age", "age_of_respondent", "respondent_age"]
        chart_data = []
        try:
            if chart_type == "line" and time_dimension:
                te = service._get_json_field(time_dimension)
                if te is not None:
                    rows = _q().filter(te.isnot(None), te != "").with_entities(te, func.count(Submission.id)).group_by(te).all()
                    chart_data = [{"name": str(k).strip().strip('"') or k, "value": v, "date": str(k).strip().strip('"') or k} for k, v in sorted(rows, key=lambda x: (str(x[0]) or ""))]
            elif chart_type in ["stacked_bar", "diverging_stacked_bar"] and secondary_dimension:
                de, se = service._get_json_field(dimension), service._get_json_field(secondary_dimension)
                if de is not None and se is not None:
                    rows = _q().filter(de.isnot(None), de != "", se.isnot(None), se != "").with_entities(de, se, func.count(Submission.id)).group_by(de, se).all()
                    g, all_s = {}, set()
                    for (p, s, c) in rows:
                        pl = _resolve_code_to_label((str(p).strip().strip('"') if p else "") or "", form, dimension, request_data.dimension or dimension)
                        sl = _resolve_code_to_label((str(s).strip().strip('"') if s else "") or "", form, secondary_dimension, request_data.secondary_dimension or secondary_dimension)
                        g.setdefault(pl, {})[sl] = g.get(pl, {}).get(sl, 0) + int(c)
                        all_s.add(sl)
                    all_s = sorted(all_s)
                    chart_data = [{"name": p, **{s: g[p].get(s, 0) for s in all_s}} for p in sorted(g.keys())]
            elif chart_type == "histogram":
                de = service._get_json_field(dimension)
                if de is not None:
                    rows = _q().with_entities(de).filter(de.isnot(None), de != "").all()
                    vals = []
                    for (v,) in rows:
                        s = (str(v).strip().strip('"') if v else "") or ""
                        try:
                            vals.append(float(s))
                        except (ValueError, TypeError):
                            pass
                    chart_data = _histogram_from_values(vals, bin_count)
            elif chart_type == "scatter" and secondary_dimension:
                de, se = service._get_json_field(dimension), service._get_json_field(secondary_dimension)
                if de is not None and se is not None:
                    rows = _q().with_entities(de, se).filter(de.isnot(None), de != "", se.isnot(None), se != "").all()
                    for (x, y) in rows:
                        try:
                            xn = float((str(x).strip().strip('"') or "") or "0")
                            yn = float((str(y).strip().strip('"') or "") or "0")
                            chart_data.append({"x": xn, "y": yn, "name": f"({xn:.1f}, {yn:.1f})"})
                        except (ValueError, TypeError):
                            pass
            elif chart_type in ["pie", "donut"]:
                de = service._get_json_field(dimension)
                if de is not None:
                    rows = _q().filter(de.isnot(None), de != "").with_entities(de, func.count(Submission.id)).group_by(de).all()
                    cnt = {}
                    for (c, n) in rows:
                        s = (str(c).strip().strip('"') if c else "") or ""
                        if s:
                            lbl = _resolve_code_to_label(s, form, dimension, request_data.dimension or dimension)
                            cnt[lbl] = cnt.get(lbl, 0) + int(n)
                    chart_data = [{"name": k, "value": v} for k, v in sorted(cnt.items(), key=lambda x: -x[1])]
            else:
                de = service._get_json_field(dimension)
                if de is not None:
                    if apply_age:
                        rows = _q().with_entities(de).filter(de.isnot(None), de != "").all()
                        cnt = {}
                        for (v,) in rows:
                            s = (str(v).strip().strip('"') if v else "") or ""
                            try:
                                r = _group_by_age_range(s)
                                cnt[r] = cnt.get(r, 0) + 1
                            except Exception:
                                pass
                        chart_data = [{"name": k, "value": v} for k, v in sorted(cnt.items(), key=lambda x: -x[1])]
                    else:
                        rows = _q().filter(de.isnot(None), de != "").with_entities(de, func.count(Submission.id)).group_by(de).all()
                        cnt = {}
                        for (c, n) in rows:
                            s = (str(c).strip().strip('"') if c else "") or ""
                            if s:
                                lbl = _resolve_code_to_label(s, form, dimension, request_data.dimension or dimension)
                                cnt[lbl] = cnt.get(lbl, 0) + int(n)
                        chart_data = [{"name": k, "value": v} for k, v in sorted(cnt.items(), key=lambda x: -x[1])]

            if not chart_data:
                msg = f"No data found for dimension '{dimension}'"
                if chart_type in ["histogram", "scatter", "box_plot"]:
                    msg += ". This chart requires numeric fields (integer/decimal)."
                elif chart_type == "line":
                    msg += ". This chart requires a valid time dimension (date/datetime)."
                return {"form_id": form_id, "chart_type": chart_type, "dimension": dimension, "data": [], "total": total, "warning": msg}
        except Exception as e:
            logger.error(f"Error processing chart data for form {form_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Error processing chart data: {str(e)}")

        response = {"form_id": form_id, "chart_type": chart_type, "dimension": dimension, "data": chart_data, "total": total}
        if secondary_dimension and chart_type in ["stacked_bar", "diverging_stacked_bar", "scatter"]:
            response["secondary_dimension"] = secondary_dimension
        service._set_cache("chart_data", cache_key, response, form.id)
        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting chart data for form {form_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error retrieving chart data: {str(e)}")


def _process_bar_chart(submissions: list, dimension: str, form_schema: dict = None) -> list:
    """Process data for bar chart - simple count by dimension with label lookup."""
    dimension_data = {}
    question_map, choice_map = build_schema_maps(form_schema) if form_schema else ({}, {})
    
    for submission in submissions:
        try:
            # Use cleaned_data (normalized) or submission_data (raw)
            payload = submission.cleaned_data or submission.submission_data
            if not payload or not isinstance(payload, dict):
                continue
            
            # Use get_nested_field_value to handle nested paths like info/province
            dim_value = get_nested_field_value(payload, dimension)
            
            if dim_value is None or dim_value == "":
                continue
            
            # Convert to string
            if isinstance(dim_value, list):
                dim_value = ", ".join(str(v) for v in dim_value)
            dim_value = str(dim_value).strip()
            
            # Try to convert code to label using schema maps
            original_value = dim_value
            if choice_map:
                # Find field in question_map
                field_meta = None
                for var_name in [dimension, dimension.lower(), dimension.replace("/", "_"), dimension.split("/")[-1]]:
                    if var_name in question_map:
                        field_meta = question_map[var_name]
                        break
                
                if field_meta and field_meta.get("list_name"):
                    list_name = field_meta["list_name"]
                    if list_name in choice_map:
                        code_lower = dim_value.lower()
                        for code_key, label_value in choice_map[list_name].items():
                            if str(code_key).lower() == code_lower:
                                dim_value = label_value
                                break
            
            dimension_data[dim_value] = dimension_data.get(dim_value, 0) + 1
        except Exception as e:
            logger.warning(f"Error processing submission {submission.id} for bar chart: {e}")
            continue
    
    chart_data = [{"name": k, "value": v} for k, v in dimension_data.items()]
    chart_data.sort(key=lambda x: x["value"], reverse=True)
    return chart_data


def _group_by_age_range(value: str) -> str:
    """Convert age to age range groups."""
    try:
        age = float(value)
        if age < 5:
            return "0-4"
        elif age < 12:
            return "5-11"
        elif age < 18:
            return "12-17"
        elif age < 30:
            return "18-29"
        elif age < 45:
            return "30-44"
        elif age < 60:
            return "45-59"
        else:
            return "60+"
    except:
        return str(value)


def _process_bar_chart_with_grouping(submissions: list, dimension: str, grouping_func) -> list:
    """Process data for bar chart with custom grouping function."""
    dimension_data = {}
    for submission in submissions:
        try:
            if not submission.submission_data or not isinstance(submission.submission_data, dict):
                continue
            sub_data = submission.submission_data
            dim_value = sub_data.get(dimension, "Unknown")
            if isinstance(dim_value, list):
                dim_value = ", ".join(str(v) for v in dim_value)
            dim_value = str(dim_value) if dim_value else "Unknown"
            # Apply grouping function
            grouped_value = grouping_func(dim_value)
            dimension_data[grouped_value] = dimension_data.get(grouped_value, 0) + 1
        except Exception as e:
            logger.warning(f"Error processing submission {submission.id} for bar chart: {e}")
            continue
    
    chart_data = [{"name": k, "value": v} for k, v in dimension_data.items()]
    chart_data.sort(key=lambda x: x["value"], reverse=True)
    return chart_data


def _process_pie_chart(submissions: list, dimension: str, form_schema: dict = None) -> list:
    """Process data for pie chart - proportions."""
    return _process_bar_chart(submissions, dimension, form_schema)


def _process_line_chart(submissions: list, time_dimension: str, value_dimension: Optional[str] = None, form_schema: dict = None) -> list:
    """Process data for line chart - trends over time."""
    from datetime import datetime
    
    # Build schema maps for label lookup if provided
    question_map = {}
    choice_map = {}
    if form_schema:
        question_map, choice_map = build_schema_maps(form_schema)
    
    time_data = {}
    for submission in submissions:
        try:
            sub_data = submission.cleaned_data or submission.submission_data
            if not sub_data or not isinstance(sub_data, dict):
                continue
            time_value = get_nested_field_value(sub_data, time_dimension)
            
            if not time_value:
                continue
            
            # Parse date
            try:
                if isinstance(time_value, str):
                    # Try parsing various date formats
                    date_obj = None
                    
                    # 1. Try standard ISO format (most common in Kobo: 2023-10-27T10:00:00.000Z)
                    try:
                        # Remove 'Z' and truncate milliseconds if present for simpler parsing
                        clean_time = time_value.replace('Z', '').split('.')[0]
                        for fmt in ["%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"]:
                            try:
                                date_obj = datetime.strptime(clean_time, fmt)
                                break
                            except:
                                continue
                    except:
                        pass

                    # 2. Try other common formats if ISO failed
                    if not date_obj:
                        for fmt in ["%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d"]:
                            try:
                                date_obj = datetime.strptime(time_value.split("T")[0].split(" ")[0], fmt)
                                break
                            except:
                                continue
                                
                    if not date_obj:
                        continue
                else:
                    continue
                
                # Group by date (day level)
                date_key = date_obj.strftime("%Y-%m-%d")
                
                if value_dimension:
                    # Count by value_dimension within each time period
                    value = get_nested_field_value(sub_data, value_dimension) or "All"
                    value_str = str(value)
                    
                    # Convert code to label if possible
                    if form_schema and choice_map:
                        original_value = value_str
                        for var_name in [value_dimension, value_dimension.lower(), value_dimension.replace("/", "_"), value_dimension.split("/")[-1]]:
                            if var_name in question_map:
                                field_meta = question_map[var_name]
                                if field_meta.get("list_name") and field_meta["list_name"] in choice_map:
                                    list_name = field_meta["list_name"]
                                    code_lower = value_str.lower()
                                    for code_key, label_value in choice_map[list_name].items():
                                        if str(code_key).lower() == code_lower:
                                            value_str = label_value
                                            break
                                break
                        
                        # Fallback to get_choice_label
                        if value_str == original_value:
                            label = get_choice_label(form_schema, value_dimension, value_str)
                            if label != value_str:
                                value_str = label
                    
                    if date_key not in time_data:
                        time_data[date_key] = {}
                    time_data[date_key][value_str] = time_data[date_key].get(value_str, 0) + 1
                else:
                    # Simple count over time
                    time_data[date_key] = time_data.get(date_key, 0) + 1
            except Exception as e:
                logger.warning(f"Error parsing time value for submission {submission.id}: {e}")
                continue
        except Exception as e:
            logger.warning(f"Error processing submission {submission.id} for line chart: {e}")
            continue
    
    # Format for line chart
    if value_dimension:
        # Multiple series
        all_dates = sorted(time_data.keys())
        all_values = set()
        for date_data in time_data.values():
            if isinstance(date_data, dict):
                all_values.update(date_data.keys())
        
        chart_data = []
        for date in all_dates:
            point = {"name": date, "date": date}
            for value in sorted(all_values):
                point[value] = time_data.get(date, {}).get(value, 0)
            chart_data.append(point)
    else:
        chart_data = [{"name": k, "value": v, "date": k} for k, v in sorted(time_data.items())]
    
    return chart_data


def _process_stacked_bar_chart(submissions: list, dimension: str, secondary_dimension: str, form_schema: dict = None) -> list:
    """Process data for stacked bar chart - group by dimension, stack by secondary."""
    grouped_data = {}
    
    for submission in submissions:
        try:
            sub_data = submission.cleaned_data or submission.submission_data
            if not sub_data or not isinstance(sub_data, dict):
                continue
            
            primary_raw = get_nested_field_value(sub_data, dimension) or "Unknown"
            
            secondary_raw = get_nested_field_value(sub_data, secondary_dimension) or "Unknown"
            
            primary_value = str(primary_raw)
            secondary_value = str(secondary_raw)
            
            if form_schema:
                primary_label = get_choice_label(form_schema, dimension, primary_value)
                if primary_label != primary_value:
                    primary_value = primary_label
                
                secondary_label = get_choice_label(form_schema, secondary_dimension, secondary_value)
                if secondary_label != secondary_value:
                    secondary_value = secondary_label
            
            if primary_value not in grouped_data:
                grouped_data[primary_value] = {}
            
            grouped_data[primary_value][secondary_value] = grouped_data[primary_value].get(secondary_value, 0) + 1
        except Exception as e:
            logger.warning(f"Error processing submission {submission.id} for stacked bar chart: {e}")
            continue
    
    # Format for stacked bar chart
    all_secondary_values = set()
    for primary_data in grouped_data.values():
        if isinstance(primary_data, dict):
            all_secondary_values.update(primary_data.keys())
    
    chart_data = []
    for primary_value, secondary_data in sorted(grouped_data.items()):
        point = {"name": primary_value}
        for secondary_value in sorted(all_secondary_values):
            point[secondary_value] = secondary_data.get(secondary_value, 0) if isinstance(secondary_data, dict) else 0
        chart_data.append(point)
    
    return chart_data


def _histogram_from_values(values: list, bin_count: int) -> list:
    """Build histogram bins from a list of numeric values."""
    if not values:
        return []
    try:
        min_val, max_val = min(values), max(values)
        bin_width = (max_val - min_val) / bin_count if max_val > min_val else 1
        bins = {}
        for v in values:
            i = min(int((v - min_val) / bin_width) if bin_width > 0 else 0, bin_count - 1)
            start = min_val + i * bin_width
            end = min_val + (i + 1) * bin_width
            lbl = f"{start:.1f}-{end:.1f}"
            bins[lbl] = bins.get(lbl, 0) + 1
        return [{"name": k, "value": v} for k, v in sorted(bins.items(), key=lambda x: float(x[0].split("-")[0]))]
    except Exception as e:
        logger.error(f"Error building histogram: {e}", exc_info=True)
        return []


def _process_histogram(submissions: list, dimension: str, bin_count: int) -> list:
    """Process data for histogram - frequency distribution of numeric data."""
    values = []
    for submission in submissions:
        try:
            sub_data = submission.cleaned_data or submission.submission_data
            if not sub_data or not isinstance(sub_data, dict):
                continue
            value = get_nested_field_value(sub_data, dimension)
            try:
                if value is not None:
                    values.append(float(value))
            except (ValueError, TypeError):
                continue
        except Exception as e:
            logger.warning(f"Error processing submission {submission.id} for histogram: {e}")
            continue
    return _histogram_from_values(values, bin_count)


def _process_scatter_plot(submissions: list, x_dimension: str, y_dimension: str) -> list:
    """Process data for scatter plot - relationship between two numeric variables."""
    points = []
    for submission in submissions:
        try:
            sub_data = submission.cleaned_data or submission.submission_data
            if not sub_data or not isinstance(sub_data, dict):
                continue
            x_value = get_nested_field_value(sub_data, x_dimension)
            y_value = get_nested_field_value(sub_data, y_dimension)
            try:
                if x_value is not None and y_value is not None:
                    x_num = float(x_value)
                    y_num = float(y_value)
                    points.append({"x": x_num, "y": y_num, "name": f"({x_num:.1f}, {y_num:.1f})"})
            except (ValueError, TypeError):
                continue
        except Exception as e:
            logger.warning(f"Error processing submission {submission.id} for scatter plot: {e}")
            continue
    
    return points


@app.get("/api/forms/{form_id}/submissions")
def get_form_submissions(
    form_id: int,
    filters: Optional[dict] = None,
    skip: int = 0,
    limit: int = 30,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Get submissions for a specific form. Returns the last N records (default 30) by created_at, no date cutoff."""
    form = db.query(FormModel).filter(FormModel.id == form_id).first()
    if not form:
        raise HTTPException(status_code=404, detail="Form not found")
    
    # Check access for non-admin users
    if not check_form_access(current_user, form_id, db):
        raise HTTPException(status_code=403, detail="Access denied to this form")
    
    # No date cutoff: show the most recent records (last N by created_at). Use limit to control how many (default 30).
    query = db.query(Submission).filter(Submission.form_id == form_id)
    submissions = query.order_by(desc(Submission.created_at)).offset(skip).limit(limit).all()
    
    result = []
    for s in submissions:
        response = SubmissionResponse.model_validate(s)
        data = s.cleaned_data or s.submission_data or {}
        response.submission_data = data
        response.enumerator = _get_enumerator_from_data(data)
        result.append(response)
    
    return result


@app.get("/api/forms/{form_id}/submission-details")
def get_submission_details(
    form_id: int,
    submission_id: str = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Get detailed information for submission(s) in a form.
    
    Supports multiple submission IDs via:
    - Query params: ?submission_id=1&submission_id=2&submission_id=3
    - Comma-separated: ?submission_id=1,2,3
    """
    form = db.query(FormModel).filter(FormModel.id == form_id).first()
    if not form:
        raise HTTPException(status_code=404, detail="Form not found")
    
    # Check access for non-admin users
    if not check_form_access(current_user, form_id, db):
        raise HTTPException(status_code=403, detail="Access denied to this form")
    
    if not submission_id:
        raise HTTPException(status_code=400, detail="submission_id is required")
    
    submission_ids = []
    if ',' in submission_id:
        submission_ids = [int(id.strip()) for id in submission_id.split(',')]
    else:
        submission_ids = [int(submission_id)]
    
    submissions = db.query(Submission).filter(
        Submission.id.in_(submission_ids),
        Submission.form_id == form_id
    ).all()
    
    if not submissions:
        raise HTTPException(status_code=404, detail="No submissions found")
    
    result = []
    for submission in submissions:
        response = SubmissionResponse.model_validate(submission)
        data = submission.cleaned_data or submission.submission_data or {}
        response.submission_data = data
        response.enumerator = _get_enumerator_from_data(data)
        result.append(response)
    
    return result


@app.get("/api/forms/{form_id}/table", response_model=TableViewResponse)
def get_form_table(
    form_id: int,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Get form data in table view format (like Kobo table)."""
    form = db.query(FormModel).filter(FormModel.id == form_id).first()
    if not form:
        raise HTTPException(status_code=404, detail="Form not found")
    
    # Check access for non-admin users
    if not check_form_access(current_user, form_id, db):
        raise HTTPException(status_code=403, detail="Access denied to this form")
    
    total_count = db.query(Submission).filter(Submission.form_id == form_id).count()
    
    submissions = (
        db.query(Submission)
        .filter(Submission.form_id == form_id)
        .order_by(desc(Submission.created_at))
        .offset(skip)
        .limit(limit)
        .all()
    )
    
    columns = []
    rows = []
    
    if submissions:
        # Pre-define auto-detected columns to ensure they always appear
        seen_fields = {"province", "district"}
        field_types = {"province": "text", "district": "text"}
        
        for submission in submissions:
            payload = submission.cleaned_data or submission.submission_data
            if not payload or not isinstance(payload, dict):
                continue
            
            for key in payload.keys():
                if key.startswith("_"):
                    continue
                if key not in seen_fields:
                    seen_fields.add(key)
                    
                    value = payload[key]
                    if isinstance(value, bool):
                        field_type = "boolean"
                    elif isinstance(value, (int, float)):
                        field_type = "numeric"
                    elif isinstance(value, list):
                        field_type = "list"
                    else:
                        field_type = "text"
                    
                    field_types[key] = field_type
        
        # Sort fields but keep province and district at a consistent place if desired
        # For now, just sorting all including auto-detected ones
        for field_name in sorted(seen_fields):
            field_type = field_types.get(field_name, "text")
            label = field_name.replace("_", " ").replace("/", " ").title()
            
            try:
                if form.form_schema:
                    schema = form.form_schema if isinstance(form.form_schema, dict) else json.loads(form.form_schema) if isinstance(form.form_schema, str) else {}
                    content = schema.get("content", {})
                    survey = content.get("survey", [])
                    for field in survey:
                        if field.get("name") == field_name:
                            field_label_value = field.get("label", label)
                            if isinstance(field_label_value, list) and len(field_label_value) > 0:
                                label = field_label_value[0]
                            elif isinstance(field_label_value, str):
                                label = field_label_value
                            break
            except Exception:
                pass
            
            columns.append(TableColumnDefinition(
                name=field_name,
                label=label,
                type=field_type
            ))
        
        for submission in submissions:
            payload = submission.cleaned_data or submission.submission_data
            if not isinstance(payload, dict):
                payload = {}
            
            row = {}
            for field_name in seen_fields:
                # Prioritize database columns for auto-detected fields
                if field_name == "province":
                    value = submission.province or payload.get("province")
                elif field_name == "district":
                    value = submission.district or payload.get("district")
                else:
                    value = payload.get(field_name)
                
                if value is None:
                    row[field_name] = None
                elif isinstance(value, list):
                    row[field_name] = ", ".join(str(v) for v in value)
                else:
                    row[field_name] = str(value)
            
            rows.append(row)
    
    return TableViewResponse(
        form_id=form_id,
        form_title=form.title,
        total_count=total_count,
        columns=columns,
        rows=rows,
        skip=skip,
        limit=limit,
        has_more=(skip + limit) < total_count
    )


@app.get("/api/forms/{form_id}/map-data")
def get_form_map_data(
    form_id: int,
    filters: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Get map data (locations). Uses DB-side filtering; fetches only lat/lng/name/id/submitted_at."""
    try:
        from analysis_service import AnalysisService

        form = db.query(FormModel).filter(FormModel.id == form_id).first()
        if not form:
            raise HTTPException(status_code=404, detail="Form not found")
        if not check_form_access(current_user, form_id, db):
            raise HTTPException(status_code=403, detail="Access denied to this form")

        filter_dict = {}
        if filters:
            try:
                filter_dict = json.loads(filters) if isinstance(filters, str) else filters
            except (json.JSONDecodeError, TypeError):
                pass
        if not isinstance(filter_dict, dict):
            filter_dict = {}

        query = db.query(Submission).filter(
            Submission.form_id == form_id,
            Submission.location_lat.isnot(None),
            Submission.location_lng.isnot(None),
        )
        if filter_dict:
            service = AnalysisService(db)
            query = _apply_filters_dict(query, service, form, filter_dict)

        rows = query.with_entities(
            Submission.location_lat,
            Submission.location_lng,
            Submission.location_name,
            Submission.id,
            Submission.submitted_at,
        ).all()

        location_groups = {}
        for (lat, lng, name, sid, sub_at) in rows:
            try:
                if lat is None or lng is None:
                    continue
                la, ln = float(lat), float(lng)
                if la != la or ln != ln:
                    continue
                key = f"{round(la, 4)},{round(ln, 4)}"
                if key not in location_groups:
                    location_groups[key] = {"lat": round(la, 4), "lng": round(ln, 4), "name": name or "Unknown", "count": 0, "submissions": []}
                location_groups[key]["count"] += 1
                location_groups[key]["submissions"].append({"submission_id": sid, "submitted_at": sub_at.isoformat() if sub_at else None})
            except (ValueError, TypeError):
                pass

        map_data = [{"lat": g["lat"], "lng": g["lng"], "name": g["name"], "count": g["count"], "submissions": g["submissions"]} for g in location_groups.values()]
        
        return {
            "form_id": form_id,
            "locations": map_data,
            "count": len(map_data),
            "total_submissions": sum(loc["count"] for loc in map_data),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting map data for form {form_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error retrieving map data: {str(e)}")


@app.post("/api/forms/{form_id}/grouped-data")
def get_form_grouped_data(
    form_id: int,
    request_data: ChartDataRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Get grouped/aggregated data for a form with hierarchical grouping support."""
    try:
        form = db.query(FormModel).filter(FormModel.id == form_id).first()
        if not form:
            raise HTTPException(status_code=404, detail="Form not found")
        
        # Check access for non-admin users
        if not check_form_access(current_user, form_id, db):
            raise HTTPException(status_code=403, detail="Access denied to this form")
        
        dimension = request_data.dimension
        secondary_dimension = request_data.secondary_dimension
        filters = request_data.filters or {}
        
        if not dimension:
            raise HTTPException(status_code=400, detail="dimension is required")

        query = db.query(Submission).filter(Submission.form_id == form_id)
        if filters:
            from analysis_service import AnalysisService
            service = AnalysisService(db)
            query = _apply_filters_dict(query, service, form, filters)
        submissions = query.all()

        # Group data
        grouped_data = {}
        
        if secondary_dimension:
            # Hierarchical grouping: dimension -> secondary_dimension -> count
            for submission in submissions:
                try:
                    if not submission.submission_data or not isinstance(submission.submission_data, dict):
                        continue
                    
                    sub_data = submission.submission_data
                    primary_value = str(sub_data.get(dimension, "Unknown"))
                    secondary_value = str(sub_data.get(secondary_dimension, "Unknown"))
                    
                    if primary_value not in grouped_data:
                        grouped_data[primary_value] = {}
                    
                    if secondary_value not in grouped_data[primary_value]:
                        grouped_data[primary_value][secondary_value] = 0
                    
                    grouped_data[primary_value][secondary_value] += 1
                except Exception as e:
                    logger.warning(f"Error processing submission {submission.id}: {e}")
                    continue
            
            # Format as list with breakdown
            formatted_data = []
            for primary_value, secondary_data in sorted(grouped_data.items()):
                primary_item = {
                    "name": primary_value,
                    "value": sum(secondary_data.values()),
                    "breakdown": []
                }
                for secondary_value, count in sorted(secondary_data.items(), key=lambda x: x[1], reverse=True):
                    primary_item["breakdown"].append({
                        "name": secondary_value,
                        "value": count
                    })
                formatted_data.append(primary_item)
        else:
            # Simple grouping by dimension
            for submission in submissions:
                try:
                    if not submission.submission_data or not isinstance(submission.submission_data, dict):
                        continue
                    
                    sub_data = submission.submission_data
                    dim_value = str(sub_data.get(dimension, "Unknown"))
                    
                    if dim_value not in grouped_data:
                        grouped_data[dim_value] = 0
                    
                    grouped_data[dim_value] += 1
                except Exception as e:
                    logger.warning(f"Error processing submission {submission.id}: {e}")
                    continue
            
            # Format as list
            formatted_data = [
                {"name": k, "value": v}
                for k, v in sorted(grouped_data.items(), key=lambda x: x[1], reverse=True)
            ]
        
        return {
            "form_id": form_id,
            "dimension": dimension,
            "secondary_dimension": secondary_dimension,
            "data": formatted_data,
            "total": len(submissions),
            "filtered_count": len(submissions),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting grouped data for form {form_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error retrieving grouped data: {str(e)}")


# ============================================================================
# WebSocket Endpoints (disabled when ENABLE_WEBSOCKETS=0, e.g. PythonAnywhere free)
# Use GET /api/sync/{sync_id}/progress (polling) or /api/sync/{sync_id}/stream (SSE) instead.
# ============================================================================

def _websockets_enabled() -> bool:
    return getattr(settings, "ENABLE_WEBSOCKETS", "1").lower() in ("1", "true", "yes")

if _websockets_enabled():
    from websocket_manager import manager

    @app.websocket("/ws/forms/{form_id}")
    async def websocket_form_updates(websocket: WebSocket, form_id: int):
        """WebSocket endpoint for real-time form updates."""
        db = next(get_db())
        try:
            form = db.query(FormModel).filter(FormModel.id == form_id).first()
            if not form:
                await websocket.close(code=1008, reason="Form not found")
                return
        finally:
            db.close()
        await manager.connect(websocket, form_id)
        try:
            while True:
                data = await websocket.receive_text()
                await websocket.send_json({"type": "pong", "form_id": form_id})
        except WebSocketDisconnect:
            manager.disconnect(websocket, form_id)
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
            manager.disconnect(websocket, form_id)

    @app.websocket("/ws/sync/{sync_id}")
    async def websocket_sync_progress(websocket: WebSocket, sync_id: int):
        """WebSocket endpoint for real-time sync progress updates. Reads in-memory store first."""
        d = sync_progress_store.get(sync_id)
        if d is not None:
            progress = SyncProgressResponse(**{k: v for k, v in d.items() if k in SyncProgressResponse.model_fields})
            await websocket.send_json(progress.model_dump())
        else:
            db = next(get_db())
            try:
                sync_log = db.query(SyncLog).filter(SyncLog.id == sync_id).first()
                if not sync_log:
                    await websocket.close(code=1008, reason="Sync not found")
                    return
                progress = SyncProgressResponse(
                    sync_id=sync_log.id,
                    status=sync_log.status,
                    current_form_index=sync_log.current_form_index or 0,
                    total_forms=sync_log.total_forms or 0,
                    current_form_id=sync_log.current_form_id,
                    current_form_title=sync_log.current_form_title,
                    current_submission_index=sync_log.current_submission_index or 0,
                    total_submissions=sync_log.total_submissions or 0,
                    progress_percentage=float(sync_log.progress_percentage or 0),
                    records_added=sync_log.records_added or 0,
                    records_updated=sync_log.records_updated or 0,
                    records_processed=sync_log.records_processed or 0,
                    started_at=sync_log.started_at.isoformat() if sync_log.started_at else None,
                    completed_at=sync_log.completed_at.isoformat() if sync_log.completed_at else None,
                    error_message=sync_log.error_message,
                    message=None,
                )
                await websocket.send_json(progress.model_dump())
            finally:
                db.close()
        await manager.connect_sync(websocket, sync_id)
        try:
            while True:
                data = await websocket.receive_text()
                await websocket.send_json({"type": "pong", "sync_id": sync_id})
        except WebSocketDisconnect:
            manager.disconnect_sync(websocket, sync_id)
        except Exception as e:
            logger.error(f"Sync WebSocket error: {e}")
            manager.disconnect_sync(websocket, sync_id)


@app.get("/api/sync/{sync_id}/progress", response_model=SyncProgressResponse)
def get_sync_progress(
    sync_id: int,
    current_user: User = Depends(get_current_user_for_sse),
    db: Session = Depends(get_db),
):
    """Get sync progress (polling). Reads in-memory store first, else DB. Auth: Bearer or ?token=."""
    d = sync_progress_store.get(sync_id)
    if d is not None:
        return SyncProgressResponse(**{k: v for k, v in d.items() if k in SyncProgressResponse.model_fields})
    sync_log = db.query(SyncLog).filter(SyncLog.id == sync_id).first()
    if not sync_log:
        raise HTTPException(status_code=404, detail="Sync not found")
    message = None
    if sync_log.status == "running":
        if sync_log.total_forms and sync_log.total_forms > 1:
            message = f"Syncing form {sync_log.current_form_index + 1} of {sync_log.total_forms}"
            if sync_log.current_form_title:
                message += f": {sync_log.current_form_title}"
        elif sync_log.total_submissions and sync_log.total_submissions > 0:
            message = f"Processing submission {sync_log.current_submission_index} of {sync_log.total_submissions}"
    elif sync_log.status == "success":
        message = "Sync completed successfully"
    elif sync_log.status == "error":
        message = f"Sync failed: {sync_log.error_message}"
    return SyncProgressResponse(
        sync_id=sync_log.id,
        status=sync_log.status,
        current_form_index=sync_log.current_form_index or 0,
        total_forms=sync_log.total_forms or 0,
        current_form_id=sync_log.current_form_id,
        current_form_title=sync_log.current_form_title,
        current_submission_index=sync_log.current_submission_index or 0,
        total_submissions=sync_log.total_submissions or 0,
        progress_percentage=float(sync_log.progress_percentage or 0),
        records_added=sync_log.records_added or 0,
        records_updated=sync_log.records_updated or 0,
        records_processed=sync_log.records_processed or 0,
        started_at=sync_log.started_at.isoformat() if sync_log.started_at else None,
        completed_at=sync_log.completed_at.isoformat() if sync_log.completed_at else None,
        error_message=sync_log.error_message,
        message=message,
    )


def _get_sync_state(sync_id: int) -> str:
    """'not_found' | 'active' | 'finished'. Used by SSE to return 409 NO_ACTIVE_SYNC when not running."""
    d = sync_progress_store.get(sync_id)
    if d and d.get("status") == "running":
        return "active"
    if d and d.get("status") in ("success", "error"):
        return "finished"
    db = SessionLocal()
    try:
        row = db.query(SyncLog).filter(SyncLog.id == sync_id).first()
        if not row:
            return "not_found"
        if row.status == "running":
            return "active"
        return "finished"
    finally:
        db.close()


def _fetch_sync_progress_row(sync_id: int) -> Optional[dict]:
    """Read from in-memory store first, else SyncLog. Returns a plain dict. Runs in thread for async."""
    d = sync_progress_store.get(sync_id)
    if d is not None:
        return d
    db = SessionLocal()
    try:
        row = db.query(SyncLog).filter(SyncLog.id == sync_id).first()
        if not row:
            return None
        return {
            "sync_id": row.id,
            "status": row.status,
            "current_form_index": row.current_form_index,
            "total_forms": row.total_forms,
            "current_form_id": row.current_form_id,
            "current_form_title": row.current_form_title,
            "current_submission_index": row.current_submission_index,
            "total_submissions": row.total_submissions,
            "progress_percentage": float(row.progress_percentage or 0),
            "records_added": row.records_added or 0,
            "records_updated": row.records_updated or 0,
            "records_processed": row.records_processed or 0,
            "started_at": row.started_at.isoformat() if row.started_at else None,
            "completed_at": row.completed_at.isoformat() if row.completed_at else None,
            "error_message": row.error_message,
        }
    finally:
        db.close()


@app.get("/api/sync/{sync_id}/stream")
async def stream_sync_progress(
    sync_id: int,
    current_user: User = Depends(get_current_user_for_sse),
):
    """Stream sync progress via SSE. On restricted hosts (ENABLE_WEBSOCKETS=0): 409 SSE_DISABLED immediately so frontend uses polling—avoids long pending and 504."""
    # Free/restricted hosts: don't open the stream; return 409 so frontend switches to polling right away (no long pending, no 504)
    if not _websockets_enabled():
        return JSONResponse(status_code=409, content={"code": "SSE_DISABLED", "message": f"Use GET /api/sync/{sync_id}/progress"})
    state = _get_sync_state(sync_id)
    if state == "not_found":
        raise HTTPException(status_code=404, detail="Sync not found")
    if state == "finished":
        return JSONResponse(status_code=409, content={"code": "NO_ACTIVE_SYNC", "message": "No active sync for this id"})

    async def event_generator():
        # Send immediately so the client and proxy see the stream as started (avoids "pending")
        yield ": ok\n\n"
        last_progress = None
        iter_count = 0
        while True:
            try:
                # Run DB in thread: avoids blocking the event loop (hosted workers often stall otherwise).
                # asyncio.to_thread is 3.9+; use run_in_executor on 3.8.
                to_thread = getattr(asyncio, "to_thread", None)
                if to_thread is not None:
                    result = await to_thread(_fetch_sync_progress_row, sync_id)
                else:
                    loop = asyncio.get_running_loop()
                    result = await loop.run_in_executor(None, lambda: _fetch_sync_progress_row(sync_id))
            except Exception as e:
                logger.error(f"SSE stream error: {e}")
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
                break
            iter_count += 1
            if result is None:
                yield f"data: {json.dumps({'error': 'Sync not found'})}\n\n"
                break
            message = None
            if result["status"] == "running":
                if (result.get("total_forms") or 0) > 1:
                    message = f"Syncing form {result['current_form_index'] + 1} of {result['total_forms']}"
                    if result.get("current_form_title"):
                        message += f": {result['current_form_title']}"
                elif (result.get("total_submissions") or 0) > 0:
                    message = f"Processing submission {result['current_submission_index']} of {result['total_submissions']}"
            elif result["status"] == "success":
                message = "Sync completed successfully"
            elif result["status"] == "error":
                message = f"Sync failed: {result.get('error_message') or ''}"
            progress = {**result, "message": message}
            if progress != last_progress:
                yield f"data: {json.dumps(progress)}\n\n"
                last_progress = progress
            if result["status"] in ["success", "error"]:
                break
            # Heartbeat every ~18s when running to prevent proxy/host idle timeout
            if iter_count % 45 == 0 and result.get("status") == "running":
                yield ": heartbeat\n\n"
            wait = 0.4 if result.get("status") == "running" else 1
            await asyncio.sleep(wait)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream; charset=utf-8",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ============================================================================
# Setup/Branding Endpoints
# ============================================================================

@app.post("/api/setup/branding", response_model=BrandingResponse)
def setup_branding(
    payload: BrandingJSON,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Setup branding for organization (admin only).
    Accepts JSON `BrandingJSON` with optional `file_base64` + `file_name`.
    """
    try:
        if current_user.role != "admin":
            raise HTTPException(status_code=403, detail="Only admin can setup branding")

        # Use a single global branding entry (no organization required)
        branding = db.query(Branding).first()

        company_name = payload.company_name
        primary_color = payload.primary_color
        secondary_color = payload.secondary_color
        description = payload.description
        logo_path = None

        # Treat empty strings as no-file provided
        fb64 = None
        if payload.file_base64 is not None:
            try:
                fb64 = payload.file_base64.strip() if isinstance(payload.file_base64, str) else None
                if fb64 == "":
                    fb64 = None
            except Exception:
                fb64 = None

        if fb64 and payload.file_name:
            try:
                from base64 import b64decode
                from uuid import uuid4

                uploads_dir = Path("uploads/logos")
                uploads_dir.mkdir(parents=True, exist_ok=True)

                filename = f"{uuid4().hex}_{payload.file_name}"
                file_path = uploads_dir / filename

                with open(file_path, "wb") as buffer:
                    buffer.write(b64decode(fb64))

                logo_path = f"uploads/logos/{filename}"

                # remove old logo (use safe path check)
                old_logo = branding.logo_path if branding else None
                if old_logo:
                    try:
                        old_path = Path(old_logo)
                        if old_path.exists():
                            old_path.unlink()
                    except Exception:
                        pass
            except Exception as e:
                logger.error(f"Error saving base64 file: {e}")
                raise HTTPException(status_code=400, detail="Invalid base64 file data")

        # company_name is required
        if not company_name:
            raise HTTPException(status_code=422, detail="company_name is required + ${company_name}")

        if branding:
            branding.company_name = company_name
            if primary_color is not None:
                branding.primary_color = primary_color
            if secondary_color is not None:
                branding.secondary_color = secondary_color
            if description is not None:
                branding.description = description
            if logo_path:
                branding.logo_path = logo_path
            branding.updated_at = datetime.utcnow()
        else:
            # Ensure we have an organization id to satisfy DB constraints
            org = db.query(Organization).filter(Organization.name == "Default").first()
            if not org:
                org = Organization(name="Default", description="Default organization")
                db.add(org)
                db.commit()
                db.refresh(org)

            branding = Branding(
                organization_id=org.id if org else None,
                company_name=company_name,
                logo_path=logo_path,
                primary_color=primary_color,
                secondary_color=secondary_color,
                description=description,
            )
            db.add(branding)

        try:
            db.commit()
            db.refresh(branding)
            return branding
        except Exception as e:
            db.rollback()
            logger.error(f"DB error saving branding: {e}", exc_info=True)
            # Surface the actual DB error to help debugging
            raise HTTPException(status_code=500, detail=f"Error setting up branding: {str(e)}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error setting up branding: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error setting up branding")


@app.get("/api/setup/branding", response_model=BrandingResponse)
def get_branding(
    db: Session = Depends(get_db),
):
    """Get branding (public endpoint)."""
    try:
        branding = db.query(Branding).first()
        if not branding:
            raise HTTPException(status_code=404, detail="Branding not configured")
        
        return branding
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching branding: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error fetching branding")


# ============================================================================
# Health Check
# ============================================================================

@app.get("/api/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.SERVER_HOST, port=settings.SERVER_PORT)

