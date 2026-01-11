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
from database import get_db, init_db
from models import User, Form as FormModel, Submission, Indicator, SyncLog, UserPermission, RawSubmission, Organization, Branding
from typing import Optional
from schemas import (
    UserCreate,
    UserResponse,
    UserUpdate,
    Token,
    LoginRequest,
    FormResponse,
    SubmissionResponse,
    IndicatorResponse,
    DashboardSummary,
    IndicatorDashboardData,
    AccountabilityDashboardData,
    SyncRequest,
    SyncLogResponse,
    WebhookPayload,
    PermissionCreate,
    PermissionResponse,
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
)
from auth import (
    get_current_active_user,
    get_password_hash,
    create_access_token,
    verify_password,
    require_role,
    get_current_user,
)
from kobo_client import KoboClient
from etl import ETLPipeline
from datetime import datetime, timedelta, date as date_type
from typing import Optional, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import WebSocket manager
from websocket_manager import manager
from discover import discover_router



@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown."""
    try:
        logger.info("Application starting...")
        
        db = next(get_db())
        try:
            # Check and create default organization
            org = db.query(Organization).filter(Organization.name == "Default").first()
            if not org:
                org = Organization(name="Default", description="Default organization")
                db.add(org)
                db.commit()
                db.refresh(org)
                logger.info("Default organization created")
            
            # Check and create default admin user
            admin = db.query(User).filter(User.username == "admin").first()
            if not admin:
                admin = User(
                    username="admin",
                    email="admin@example.com",
                    hashed_password=get_password_hash("admin123"),
                    full_name="Administrator",
                    role="admin",
                    organization_id=org.id,
                    is_active=True,
                )
                db.add(admin)
                db.commit()
                logger.info("Default admin user created (username: admin, password: admin123)")
            elif not admin.organization_id:
                admin.organization_id = org.id
                db.commit()
                logger.info("Admin user linked to default organization")
        finally:
            db.close()
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


# CORS middleware
app.add_middleware(
    CORSMiddleware,
   allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "https://samimsafi22-001-site1.jtempurl.com",
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
    user = db.query(User).filter(User.username == login_data.username).first()
    if not user or not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


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
    """
    try:
        target_date: date_type = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format, expected YYYY-MM-DD")

    query = db.query(Submission)
    if form_id is not None:
        query = query.filter(Submission.form_id == form_id)

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
    """List all users (admin only)."""
    users = db.query(User).offset(skip).limit(limit).all()
    return users


@app.get("/api/users/{user_id}", response_model=UserResponse)
def get_user(
    user_id: int,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """Get a specific user (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


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
    """List all forms from the local cache/database."""
    query = db.query(FormModel)
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
    """Get a specific form."""
    form = db.query(FormModel).filter(FormModel.id == form_id).first()
    if not form:
        raise HTTPException(status_code=404, detail="Form not found")
    
    form_dict = {
        **{c.name: getattr(form, c.name) for c in form.__table__.columns},
        "submission_count": db.query(func.count(Submission.id))
        .filter(Submission.form_id == form.id)
        .scalar(),
    }
    return FormResponse(**form_dict)


# ============================================================================
# Submission Endpoints
# ============================================================================

@app.get("/api/submissions", response_model=list[SubmissionResponse])
def list_submissions(
    form_id: int = None,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """List submissions."""
    query = db.query(Submission)
    if form_id:
        query = query.filter(Submission.form_id == form_id)
    
    submissions = query.order_by(desc(Submission.created_at)).offset(skip).limit(limit).all()
    return submissions


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
    """Get a specific submission."""
    submission = db.query(Submission).filter(Submission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    return submission


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
    """List indicators."""
    query = db.query(Indicator)
    if form_id:
        query = query.filter(Indicator.form_id == form_id)
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


@app.post("/form/{form_id}/aggregate")
def aggregate_form_data(
    form_id: int,
    request: AggregateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Generic aggregate endpoint for a form.

    This powers flexible cards/charts similar to survey dashboards:
    - filters: equality filters on cleaned/submission data
    - group_by: list of fields to group by
    - metrics: list of metrics to compute per group
    """
    form = db.query(FormModel).filter(FormModel.id == form_id).first()
    if not form:
        raise HTTPException(status_code=404, detail="Form not found")

    # Base query
    submissions_query = db.query(Submission).filter(Submission.form_id == form_id)
    submissions = submissions_query.all()

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

    This is designed for visualising the distribution of a Kobo field
    (e.g. duration, numeric score, _id) similar to the Streamlit dashboard.
    """
    from statistics import median

    form = db.query(FormModel).filter(FormModel.id == request.form_id).first()
    if not form:
        raise HTTPException(status_code=404, detail="Form not found")

    # Load all submissions for the form
    submissions = db.query(Submission).filter(Submission.form_id == form.id).all()

    if not submissions:
        raise HTTPException(
            status_code=400,
            detail=f"No submissions found for form_id {request.form_id}. Please sync data first."
        )

    # Apply simple equality / IN filters on cleaned_data/submission_data
    filters = request.filters or {}
    values: list[float] = []
    sample_payload_keys = None
    non_numeric_count = 0
    empty_count = 0
    total_checked = 0

    for sub in submissions:
        payload = sub.cleaned_data or sub.submission_data
        if not payload or not isinstance(payload, dict):
            continue

        total_checked += 1
        
        # Save sample keys for debugging (first submission only)
        if sample_payload_keys is None:
            sample_payload_keys = list(payload.keys())[:30]

        # Filter row-level
        matches = True
        for fname, fval in filters.items():
            if fval is None or fval == "" or fval == []:
                continue
            v = get_nested_field_value(payload, fname)
            if isinstance(fval, list):
                if v not in fval:
                    matches = False
                    break
            else:
                if str(v) != str(fval):
                    matches = False
                    break
        if not matches:
            continue

        # Extract numeric column value (handle nested field names like beneficiary/hh_size)
        # First try direct lookup (like /api/forms/{form_id}/chart-data does)
        raw_val = None
        if isinstance(payload, dict):
            raw_val = payload.get(request.column)
        
        # If not found, try get_nested_field_value (handles nested paths like beneficiary/hh_size)
        if raw_val in (None, ""):
            raw_val = get_nested_field_value(payload, request.column)
        
        # If still not found, try common variations (beneficiary/hh_size, info/hh_size, hh_size)
        if raw_val in (None, ""):
            # Try variations: hh_size -> beneficiary/hh_size, info/hh_size, etc.
            if '/' not in request.column:
                variations = [
                    f"beneficiary/{request.column}",
                    f"info/{request.column}",
                    f"group/{request.column}",
                ]
                for variant in variations:
                    raw_val = get_nested_field_value(payload, variant)
                    if raw_val not in (None, ""):
                        break
        
        if raw_val in (None, ""):
            empty_count += 1
            continue
        try:
            num_val = float(raw_val)
            values.append(num_val)
        except (ValueError, TypeError):
            non_numeric_count += 1
            continue

    if not values:
        # Provide detailed error message with all debugging info
        error_msg = (
            f"No numeric data available for column '{request.column}'. "
            f"Form ID: {request.form_id}, Total submissions: {len(submissions)}, "
            f"Checked after filters: {total_checked}, Empty values: {empty_count}, "
            f"Non-numeric values: {non_numeric_count}."
        )
        if sample_payload_keys:
            # Filter out internal keys starting with _
            visible_keys = [k for k in sample_payload_keys if not k.startswith('_')][:15]
            error_msg += f" Available fields (sample): {visible_keys}"
        
        logger.warning(f"Box plot error: {error_msg}")
        raise HTTPException(status_code=400, detail=error_msg)

    # Sort values for quantile computations
    values.sort()
    series = values

    def percentile(p: float) -> float:
        if not series:
            return 0.0
        k = (len(series) - 1) * p
        f = int(k)
        c = min(f + 1, len(series) - 1)
        if f == c:
            return float(series[int(k)])
        d0 = series[f] * (c - k)
        d1 = series[c] * (k - f)
        return float(d0 + d1)

    q1 = percentile(0.25)
    med = percentile(0.5)
    q3 = percentile(0.75)
    iqr = q3 - q1
    lower_bound = q1 - 1.5 * iqr
    upper_bound = q3 + 1.5 * iqr

    # Whiskers and outliers
    whisker_min_vals = [v for v in series if v >= lower_bound]
    whisker_max_vals = [v for v in series if v <= upper_bound]
    whisker_min = float(min(whisker_min_vals)) if whisker_min_vals else float(min(series))
    whisker_max = float(max(whisker_max_vals)) if whisker_max_vals else float(max(series))

    outliers = [float(v) for v in series if v < lower_bound or v > upper_bound]

    return BoxPlotResponse(
        form_id=form.id,
        column=request.column,
        q1=float(q1),
        median=float(med),
        q3=float(q3),
        whisker_min=whisker_min,
        whisker_max=whisker_max,
        outliers=outliers,
    )


@app.post("/api/charts/bar_chart", response_model=BarChartResponse)
def generate_bar_chart(
    request: BarChartRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Categorical bar chart for a form.
    
    Auto-groups by the first filter field if group_by is not provided or empty.
    Returns counts per distinct value with actual field values (not codes).
    """
    form = db.query(FormModel).filter(FormModel.id == request.form_id).first()
    if not form:
        raise HTTPException(status_code=404, detail="Form not found")

    submissions = db.query(Submission).filter(Submission.form_id == form.id).all()
    filters = request.filters or {}
    
    # Auto-detect group_by from filters if not provided
    # The first field in filters is used for grouping (to show all its values)
    group_by_field = request.group_by
    if not group_by_field or (isinstance(group_by_field, str) and group_by_field.strip() == ""):
        # Use the first filter field as group_by
        # Example: {"filters": {"info/Province": []}} -> group by "info/Province"
        if filters and len(filters) > 0:
            group_by_field = list(filters.keys())[0]
        else:
            raise HTTPException(
                status_code=400,
                detail="group_by field is required. Either provide group_by parameter or send a field in filters (e.g., {\"info/Province\": []})."
            )
    
    if not group_by_field:
        raise HTTPException(
            status_code=400,
            detail="group_by field is required. Either provide group_by parameter or send a field in filters (e.g., {\"info/Province\": []})."
        )

    counts: dict[str, int] = {}

    for sub in submissions:
        payload = sub.cleaned_data or sub.submission_data
        if not payload or not isinstance(payload, dict):
            continue

        # Apply filters (excluding the group_by field - we want ALL values of that field)
        # Other fields in filters are applied as actual filters
        matches = True
        for fname, fval in filters.items():
            # Skip the field we're grouping by - we want ALL its values, not filtered
            if fname == group_by_field:
                continue
            # Skip empty/null filter values (empty array means no filter)
            if fval is None or fval == "" or (isinstance(fval, list) and len(fval) == 0):
                continue
            # Apply actual filter
            v = get_nested_field_value(payload, fname)
            if isinstance(fval, list):
                if v not in fval:
                    matches = False
                    break
            else:
                if str(v) != str(fval):
                    matches = False
                    break
        if not matches:
            continue

        # Extract the grouping field value (e.g., "Kabul", "Balkh" for "info/Province")
        # First try direct lookup (like /api/forms/{form_id}/chart-data does)
        raw_cat = None
        if isinstance(payload, dict):
            raw_cat = payload.get(group_by_field)
        
        # If not found, try get_nested_field_value (handles nested paths)
        if raw_cat in (None, ""):
            raw_cat = get_nested_field_value(payload, group_by_field)
        
        # Get the actual display value, not codes
        # Try variations if still not found (e.g., province -> info/province, beneficiary/province)
        if raw_cat in (None, ""):
            # Try alternative field names and common prefixes
            alternatives = []
            
            # If field doesn't have slash, try with common prefixes
            if '/' not in group_by_field:
                alternatives.extend([
                    f"info/{group_by_field}",
                    f"beneficiary/{group_by_field}",
                    f"group/{group_by_field}",
                ])
            
            # Always try these variations
            alternatives.extend([
                group_by_field.replace('/', '_'),  # info/province -> info_province
                group_by_field.split('/')[-1] if '/' in group_by_field else None,  # info/province -> province
                group_by_field.lower(),
                group_by_field.upper(),
            ])
            
            for alt in alternatives:
                if alt:
                    raw_cat = get_nested_field_value(payload, alt)
                    if raw_cat not in (None, ""):
                        break
            
            if raw_cat in (None, ""):
                # Skip this submission if field not found (don't count as "Unknown")
                continue
        
        # Clean and normalize the category value
        category = str(raw_cat).strip()
        
        # Normalize code to label using Kobo best practices
        # Build schema maps once and use efficient lookup
        if form.form_schema and category:
            original_category = category
            
            # Build schema maps (question_map and choice_map) following Kobo pattern
            question_map, choice_map = build_schema_maps(form.form_schema)
            
            # Find the field in question_map (try multiple matching strategies)
            field_meta = None
            field_name_variations = [
                group_by_field,
                group_by_field.lower(),
                group_by_field.replace("/", "_"),
                group_by_field.replace("/", "_").lower(),
                group_by_field.split("/")[-1],
                group_by_field.split("/")[-1].lower(),
            ]
            
            for var_name in field_name_variations:
                if var_name in question_map:
                    field_meta = question_map[var_name]
                    break
                # Also try partial match
                for q_name, q_meta in question_map.items():
                    if var_name in q_name.lower() or q_name.lower().endswith(var_name):
                        field_meta = q_meta
                        break
                if field_meta:
                    break
            
            # If field found and has a choice list, look up the label
            if field_meta and field_meta.get("list_name"):
                list_name = field_meta["list_name"]
                if list_name in choice_map:
                    # Look up code in choice_map (case-insensitive)
                    code_lower = str(category).lower()
                    for code_key, label_value in choice_map[list_name].items():
                        if str(code_key).lower() == code_lower:
                            category = label_value
                            logger.info(f"Converted code '{original_category}' to label '{category}' for field '{group_by_field}' using schema maps")
                            break
            
            # Fallback to original lookup if schema maps didn't work
            if category == original_category:
                label = get_choice_label(form.form_schema, group_by_field, category)
                if label != category:
                    category = label
                    logger.info(f"Converted code '{original_category}' to label '{category}' for field '{group_by_field}' (fallback lookup)")
                else:
                    # Try dynamic lookup as last resort
                    label = get_choice_label_dynamic(form.form_schema, group_by_field, category)
                    if label != category:
                        category = label
                        logger.info(f"Converted code '{original_category}' to label '{category}' for field '{group_by_field}' (dynamic lookup)")
                    elif len(category) <= 5 and (
                        (len(category) >= 2 and category[0].islower() and category[1:].isdigit()) or
                        (len(category) >= 2 and category[0].isupper() and category[1:].isdigit())
                    ):
                        logger.warning(
                            f"Could not find label for code '{category}' in field '{group_by_field}'. "
                            f"Debug: GET /api/forms/{form.id}/debug-schema?field_name={group_by_field}"
                        )
        
        # Only add if we have a valid category
        if category:
            counts[category] = counts.get(category, 0) + 1

    if not counts:
        # Provide helpful error message with detailed debugging info
        sample_sub = next((s for s in submissions if s.cleaned_data or s.submission_data), None)
        sample_keys = []
        if sample_sub:
            payload = sample_sub.cleaned_data or sample_sub.submission_data
            if payload and isinstance(payload, dict):
                sample_keys = [k for k in list(payload.keys())[:30] if not k.startswith('_')]
        
        # Try to find similar field names
        similar_fields = []
        if sample_keys:
            field_lower = group_by_field.lower()
            for key in sample_keys:
                if field_lower in key.lower() or key.lower() in field_lower:
                    similar_fields.append(key)
        
        error_msg = (
            f"No data found for group_by field '{group_by_field}'. "
            f"Total submissions: {len(submissions)}. "
        )
        if sample_keys:
            error_msg += f"Available fields: {sample_keys[:20]}. "
        if similar_fields:
            error_msg += f"Similar fields found: {similar_fields}. "
        error_msg += "Check if the field name matches exactly (case-sensitive)."
        
        logger.warning(f"Bar chart error: {error_msg}")
        raise HTTPException(status_code=400, detail=error_msg)

    # Calculate statistics
    total_submissions_included = sum(counts.values())
    unique_values_count = len(counts)
    
    # Get human-readable label for the field (try to extract from form schema)
    field_label = None
    if form.form_schema:
        try:
            schema = form.form_schema if isinstance(form.form_schema, dict) else json.loads(form.form_schema) if isinstance(form.form_schema, str) else {}
            content = schema.get("content", {})
            survey = content.get("survey", [])
            for field in survey:
                field_name = field.get("name", "")
                if field_name == group_by_field or field_name.replace("/", "_") == group_by_field.replace("/", "_"):
                    label = field.get("label", "")
                    if isinstance(label, list) and len(label) > 0:
                        field_label = label[0]
                    elif isinstance(label, str):
                        field_label = label
                    break
        except Exception:
            pass
    
    # If no label found, create a readable one from field name
    if not field_label:
        field_label = group_by_field.split("/")[-1].replace("_", " ").title()

    items = [
        BarChartItem(category=cat, count=count)
        for cat, count in sorted(counts.items(), key=lambda x: x[1], reverse=True)
    ]

    return BarChartResponse(
        form_id=form.id,
        group_by=group_by_field,
        items=items,
        total_submissions=total_submissions_included,
        unique_values=unique_values_count,
        field_label=field_label
    )


@app.get("/api/indicators/{indicator_id}", response_model=IndicatorResponse)
def get_indicator(
    indicator_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Get a specific indicator."""
    indicator = db.query(Indicator).filter(Indicator.id == indicator_id).first()
    if not indicator:
        raise HTTPException(status_code=404, detail="Indicator not found")
    return indicator


# ============================================================================
# Dashboard Endpoints
# ============================================================================

@app.get("/api/dashboard/summary", response_model=DashboardSummary)
def get_dashboard_summary(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Get dashboard summary."""
    total_forms = db.query(func.count(FormModel.id)).scalar()
    total_submissions = db.query(func.count(Submission.id)).scalar()
    total_indicators = db.query(func.count(Indicator.id)).scalar()
    
    # Recent submissions (last 7 days)
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    recent_submissions = (
        db.query(func.count(Submission.id))
        .filter(Submission.created_at >= seven_days_ago)
        .scalar()
    )
    
    # Forms by category
    forms_by_category = {}
    categories = db.query(FormModel.category).distinct().all()
    for (category,) in categories:
        if category:
            count = db.query(func.count(FormModel.id)).filter(FormModel.category == category).scalar()
            forms_by_category[category] = count
    
    # Submissions by date (last 30 days)
    submissions_by_date = []
    for i in range(30):
        date = datetime.utcnow() - timedelta(days=29 - i)
        date_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        date_end = date.replace(hour=23, minute=59, second=59, microsecond=999999)
        count = (
            db.query(func.count(Submission.id))
            .filter(Submission.created_at >= date_start, Submission.created_at <= date_end)
            .scalar()
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
    """Get indicator dashboard data."""
    query = db.query(Indicator)
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
        count = (
            db.query(func.count(Indicator.id))
            .filter(Indicator.computed_at >= date_start, Indicator.computed_at <= date_end)
            .scalar()
        )
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
    """Get accountability and complaints dashboard data."""
    # Get complaints (assuming forms with category "complaints" or "accountability")
    complaint_forms = db.query(FormModel).filter(
        (FormModel.category == "complaints") | (FormModel.category == "accountability")
    ).all()
    
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
# Sync Endpoints
# ============================================================================

@app.post("/api/sync", response_model=SyncLogResponse)
def sync_forms(
    sync_request: SyncRequest,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """Sync forms from Kobo (admin only)."""
    etl = ETLPipeline(db)
    
    if sync_request.form_id:
        # Sync specific form
        form = db.query(FormModel).filter(FormModel.id == sync_request.form_id).first()
        if not form:
            raise HTTPException(status_code=404, detail="Form not found")
        sync_log = etl.sync_form(form.kobo_form_id, sync_type=sync_request.sync_type)
    else:
        # Sync all forms
        sync_logs = etl.sync_all_forms(sync_type=sync_request.sync_type)
        sync_log = sync_logs[0] if sync_logs else None
        if not sync_log:
            raise HTTPException(status_code=500, detail="Sync failed")
    
    return SyncLogResponse.model_validate(sync_log)


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
            for field in filter_fields:
                field_name = field["name"]
                if field_name in field_value_counts:
                    unique_values = sorted(field_value_counts[field_name])
                    # Populate options for select fields and text fields with data
                    if field["type"] in ["select_one", "select_multiple", "text"]:
                        # Only update if options are empty or for text fields
                        if not field["options"] or field["type"] == "text":
                            field["options"] = [
                                {"value": val, "label": val.replace("_", " ").title() if len(unique_values) <= 50 else val}
                                for val in unique_values[:100]  # Limit to 100 options
                            ]
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
        
        # Query submissions
        query = db.query(Submission).filter(Submission.form_id == form_id)
        submissions = query.all()
        
        # Apply filters - use cleaned_data or submission_data, and handle nested fields
        if filters:
            filtered_submissions = []
            for sub in submissions:
                try:
                    # Use cleaned_data (normalized) or submission_data (raw)
                    payload = sub.cleaned_data or sub.submission_data
                    if not payload or not isinstance(payload, dict):
                        continue
                    
                    matches = True
                    for field_name, filter_value in filters.items():
                        # Skip empty filters (empty list means no filter - show all)
                        if filter_value is None or filter_value == "" or (isinstance(filter_value, list) and len(filter_value) == 0):
                            continue
                        
                        # Use get_nested_field_value to handle nested paths like info/province
                        field_value = get_nested_field_value(payload, field_name)
                        
                        if isinstance(filter_value, list):
                            # Filter by list of values
                            if field_value not in filter_value:
                                matches = False
                                break
                        else:
                            # Filter by single value
                            if str(field_value) != str(filter_value):
                                matches = False
                                break
                    if matches:
                        filtered_submissions.append(sub)
                except Exception as e:
                    logger.warning(f"Error filtering submission {sub.id}: {e}")
                    continue
            submissions = filtered_submissions
        
        if not submissions:
            return {
                "form_id": form_id,
                "chart_type": chart_type,
                "dimension": dimension,
                "data": [],
                "total": 0,
            }
        
        # Process data based on chart type
        try:
            # Handle special dimension cases
            actual_dimension = dimension
            apply_age_grouping = False
            
            if dimension in ["age", "age_of_respondent", "respondent_age"]:
                apply_age_grouping = True
            
            if chart_type == "line" and time_dimension:
                # Line chart: group by time dimension
                chart_data = _process_line_chart(submissions, time_dimension, dimension)
            elif chart_type in ["stacked_bar", "diverging_stacked_bar"] and secondary_dimension:
                # Stacked bar chart: group by dimension, stack by secondary_dimension
                chart_data = _process_stacked_bar_chart(submissions, dimension, secondary_dimension)
            elif chart_type == "histogram":
                # Histogram: frequency distribution of numeric dimension
                chart_data = _process_histogram(submissions, dimension, bin_count)
            elif chart_type == "scatter" and secondary_dimension:
                # Scatter plot: relationship between two numeric variables
                chart_data = _process_scatter_plot(submissions, dimension, secondary_dimension)
            elif chart_type in ["pie", "donut"]:
                # Pie/Donut chart: proportions
                chart_data = _process_pie_chart(submissions, dimension, form.form_schema)
            else:
                # Bar chart: simple grouping by dimension
                if apply_age_grouping:
                    # Apply age grouping
                    chart_data = _process_bar_chart_with_grouping(submissions, dimension, _group_by_age_range)
                else:
                    chart_data = _process_bar_chart(submissions, dimension, form.form_schema)
        except Exception as e:
            logger.error(f"Error processing chart data for form {form_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Error processing chart data: {str(e)}")
        
        return {
            "form_id": form_id,
            "chart_type": chart_type,
            "dimension": dimension,
            "secondary_dimension": secondary_dimension,
            "data": chart_data,
            "total": len(submissions),
        }
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


def _process_line_chart(submissions: list, time_dimension: str, value_dimension: Optional[str] = None) -> list:
    """Process data for line chart - trends over time."""
    from datetime import datetime
    
    time_data = {}
    for submission in submissions:
        try:
            if not submission.submission_data or not isinstance(submission.submission_data, dict):
                continue
            sub_data = submission.submission_data
            time_value = sub_data.get(time_dimension)
            
            if not time_value:
                continue
            
            # Parse date
            try:
                if isinstance(time_value, str):
                    # Try parsing various date formats
                    date_obj = None
                    for fmt in ["%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y"]:
                        try:
                            date_obj = datetime.strptime(time_value.split("T")[0], fmt)
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
                    value = sub_data.get(value_dimension, "All")
                    if date_key not in time_data:
                        time_data[date_key] = {}
                    time_data[date_key][str(value)] = time_data[date_key].get(str(value), 0) + 1
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
            for value in all_values:
                point[value] = time_data.get(date, {}).get(value, 0)
            chart_data.append(point)
    else:
        chart_data = [{"name": k, "value": v, "date": k} for k, v in sorted(time_data.items())]
    
    return chart_data


def _process_stacked_bar_chart(submissions: list, dimension: str, secondary_dimension: str) -> list:
    """Process data for stacked bar chart - group by dimension, stack by secondary."""
    grouped_data = {}
    
    for submission in submissions:
        try:
            if not submission.submission_data or not isinstance(submission.submission_data, dict):
                continue
            sub_data = submission.submission_data
            primary_value = str(sub_data.get(dimension, "Unknown"))
            secondary_value = str(sub_data.get(secondary_dimension, "Unknown"))
            
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
        for secondary_value in all_secondary_values:
            point[secondary_value] = secondary_data.get(secondary_value, 0) if isinstance(secondary_data, dict) else 0
        chart_data.append(point)
    
    return chart_data


def _process_histogram(submissions: list, dimension: str, bin_count: int) -> list:
    """Process data for histogram - frequency distribution of numeric data."""
    values = []
    for submission in submissions:
        try:
            if not submission.submission_data or not isinstance(submission.submission_data, dict):
                continue
            sub_data = submission.submission_data
            value = sub_data.get(dimension)
            try:
                if value is not None:
                    num_value = float(value)
                    values.append(num_value)
            except (ValueError, TypeError):
                continue
        except Exception as e:
            logger.warning(f"Error processing submission {submission.id} for histogram: {e}")
            continue
    
    if not values:
        return []
    
    try:
        min_val = min(values)
        max_val = max(values)
        bin_width = (max_val - min_val) / bin_count if max_val > min_val else 1
        
        bins = {}
        for value in values:
            bin_index = int((value - min_val) / bin_width) if bin_width > 0 else 0
            bin_index = min(bin_index, bin_count - 1)
            bin_start = min_val + (bin_index * bin_width)
            bin_end = min_val + ((bin_index + 1) * bin_width)
            bin_label = f"{bin_start:.1f}-{bin_end:.1f}"
            bins[bin_label] = bins.get(bin_label, 0) + 1
        
        chart_data = [{"name": k, "value": v} for k, v in sorted(bins.items(), key=lambda x: float(x[0].split("-")[0]))]
        return chart_data
    except Exception as e:
        logger.error(f"Error processing histogram: {e}", exc_info=True)
        return []


def _process_scatter_plot(submissions: list, x_dimension: str, y_dimension: str) -> list:
    """Process data for scatter plot - relationship between two numeric variables."""
    points = []
    for submission in submissions:
        try:
            if not submission.submission_data or not isinstance(submission.submission_data, dict):
                continue
            sub_data = submission.submission_data
            x_value = sub_data.get(x_dimension)
            y_value = sub_data.get(y_dimension)
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
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Get submissions for a specific form with optional filters."""
    form = db.query(FormModel).filter(FormModel.id == form_id).first()
    if not form:
        raise HTTPException(status_code=404, detail="Form not found")
    
    query = db.query(Submission).filter(Submission.form_id == form_id)
    
    # Apply filters if provided (simplified - use proper JSON querying in production)
    submissions = query.order_by(desc(Submission.created_at)).offset(skip).limit(limit).all()
    
    return [SubmissionResponse.model_validate(s) for s in submissions]


@app.get("/api/forms/{form_id}/map-data")
def get_form_map_data(
    form_id: int,
    filters: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Get map data (locations) for a specific form with optional filtering."""
    try:
        form = db.query(FormModel).filter(FormModel.id == form_id).first()
        if not form:
            raise HTTPException(status_code=404, detail="Form not found")
        
        query = db.query(Submission).filter(
            Submission.form_id == form_id,
            Submission.location_lat.isnot(None),
            Submission.location_lng.isnot(None),
        )
        
        submissions = query.all()
        
        # Parse and apply filters if provided
        filter_dict = {}
        if filters:
            try:
                filter_dict = json.loads(filters) if isinstance(filters, str) else filters
            except (json.JSONDecodeError, TypeError):
                filter_dict = {}
        
        # Apply filters to submissions
        if filter_dict:
            filtered_submissions = []
            for sub in submissions:
                try:
                    if not sub.submission_data or not isinstance(sub.submission_data, dict):
                        continue
                    
                    sub_data = sub.submission_data
                    matches = True
                    for field_name, filter_value in filter_dict.items():
                        if filter_value is None or filter_value == "":
                            continue
                        field_value = sub_data.get(field_name)
                        if isinstance(filter_value, list):
                            if field_value not in filter_value:
                                matches = False
                                break
                        else:
                            if str(field_value) != str(filter_value):
                                matches = False
                                break
                    if matches:
                        filtered_submissions.append(sub)
                except Exception as e:
                    logger.warning(f"Error filtering submission {sub.id}: {e}")
                    continue
            submissions = filtered_submissions
        
        # Group locations by lat/lng to aggregate multiple submissions at same location
        location_groups = {}
        map_data = []
        
        for submission in submissions:
            try:
                # Ensure location values are valid floats
                lat = float(submission.location_lat) if submission.location_lat is not None else None
                lng = float(submission.location_lng) if submission.location_lng is not None else None
                
                if lat is None or lng is None:
                    continue
                
                # Round coordinates to 4 decimal places for grouping
                lat_rounded = round(lat, 4)
                lng_rounded = round(lng, 4)
                location_key = f"{lat_rounded},{lng_rounded}"
                
                if location_key not in location_groups:
                    location_groups[location_key] = {
                        "lat": lat_rounded,
                        "lng": lng_rounded,
                        "name": submission.location_name or "Unknown",
                        "count": 0,
                        "submissions": []
                    }
                
                location_groups[location_key]["count"] += 1
                location_groups[location_key]["submissions"].append({
                    "submission_id": submission.id,
                    "submitted_at": submission.submitted_at.isoformat() if submission.submitted_at else None,
                })
            except (ValueError, TypeError) as e:
                logger.warning(f"Error processing submission {submission.id} for map data: {e}")
                continue
        
        # Convert grouped locations to map data
        for location_key, location_info in location_groups.items():
            map_data.append({
                "lat": location_info["lat"],
                "lng": location_info["lng"],
                "name": location_info["name"],
                "count": location_info["count"],
                "submissions": location_info["submissions"]
            })
        
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
        
        dimension = request_data.dimension
        secondary_dimension = request_data.secondary_dimension
        filters = request_data.filters or {}
        
        if not dimension:
            raise HTTPException(status_code=400, detail="dimension is required")
        
        # Query submissions
        query = db.query(Submission).filter(Submission.form_id == form_id)
        submissions = query.all()
        
        # Apply filters
        if filters:
            filtered_submissions = []
            for sub in submissions:
                try:
                    if not sub.submission_data or not isinstance(sub.submission_data, dict):
                        continue
                    
                    sub_data = sub.submission_data
                    matches = True
                    for field_name, filter_value in filters.items():
                        if filter_value is None or filter_value == "":
                            continue
                        field_value = sub_data.get(field_name)
                        if isinstance(filter_value, list):
                            if field_value not in filter_value:
                                matches = False
                                break
                        else:
                            if str(field_value) != str(filter_value):
                                matches = False
                                break
                    if matches:
                        filtered_submissions.append(sub)
                except Exception as e:
                    logger.warning(f"Error filtering submission {sub.id}: {e}")
                    continue
            submissions = filtered_submissions
        
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
# WebSocket Endpoint
# ============================================================================

@app.websocket("/ws/forms/{form_id}")
async def websocket_form_updates(websocket: WebSocket, form_id: int):
    """WebSocket endpoint for real-time form updates."""
    # Verify form exists
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
            # Keep connection alive and wait for messages
            data = await websocket.receive_text()
            # Echo back or handle client messages
            await websocket.send_json({"type": "pong", "form_id": form_id})
    except WebSocketDisconnect:
        manager.disconnect(websocket, form_id)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket, form_id)


# ============================================================================
# Setup/Branding Endpoints
# ============================================================================

@app.post("/api/setup/branding", response_model=BrandingResponse)
async def setup_branding(
    company_name: str = Form(...),
    primary_color: Optional[str] = Form(None),
    secondary_color: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Setup branding for organization (admin only).
    Can be called multiple times to update settings.
    """
    try:
        if current_user.role != "admin":
            raise HTTPException(status_code=403, detail="Only admin can setup branding")
        
        org = db.query(Organization).filter(Organization.id == current_user.organization_id).first()
        if not org:
            raise HTTPException(status_code=404, detail="Organization not found")
        
        branding = db.query(Branding).filter(Branding.organization_id == org.id).first()
        
        logo_path = None
        if file:
            uploads_dir = Path("uploads/logos")
            uploads_dir.mkdir(parents=True, exist_ok=True)
            
            filename = f"{org.id}_{file.filename}"
            file_path = uploads_dir / filename
            
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            logo_path = f"uploads/logos/{filename}"
            
            old_logo = branding.logo_path if branding else None
            if old_logo and os.path.exists(old_logo):
                os.remove(old_logo)
        
        if branding:
            branding.company_name = company_name
            if primary_color:
                branding.primary_color = primary_color
            if secondary_color:
                branding.secondary_color = secondary_color
            if description is not None:
                branding.description = description
            if logo_path:
                branding.logo_path = logo_path
            branding.updated_at = datetime.utcnow()
        else:
            branding = Branding(
                organization_id=org.id,
                company_name=company_name,
                logo_path=logo_path,
                primary_color=primary_color,
                secondary_color=secondary_color,
                description=description,
            )
            db.add(branding)
        
        db.commit()
        db.refresh(branding)
        
        return branding
    
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

