"""Database models."""
from datetime import datetime
from enum import Enum
import uuid

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.orm import relationship

# Define Base here to avoid a separate base.py file and simplify imports
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class UserRole(str, Enum):
    """User roles."""

    ADMIN = "admin"
    VIEWER = "viewer"
    EDITOR = "editor"


class Organization(Base):
    """Organization/Client model."""

    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, index=True, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    users = relationship("User", back_populates="organization", cascade="all, delete-orphan")
    branding = relationship("Branding", back_populates="organization", uselist=False, cascade="all, delete-orphan")


class Branding(Base):
    """Branding/Setup configuration for organization."""

    __tablename__ = "branding"

    id = Column(Integer, primary_key=True, index=True)
    # Allow branding without an organization (global branding)
    organization_id = Column(Integer, ForeignKey("organizations.id"), unique=True, nullable=True)
    company_name = Column(String(255), nullable=False)
    logo_path = Column(String(500), nullable=True)
    primary_color = Column(String(50), nullable=True)
    secondary_color = Column(String(50), nullable=True)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    organization = relationship("Organization", back_populates="branding")


class User(Base):
    """User model."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    role = Column(String(20), default=UserRole.VIEWER.value, nullable=False)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    permissions = relationship("UserPermission", back_populates="user", cascade="all, delete-orphan")
    organization = relationship("Organization", back_populates="users")
    form_access = relationship("UserFormAccess", back_populates="user", cascade="all, delete-orphan")


class UserPermission(Base):
    """User permissions model."""

    __tablename__ = "user_permissions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    resource = Column(String(100), nullable=False)  # e.g., "forms", "indicators", "dashboard"
    action = Column(String(50), nullable=False)  # e.g., "read", "write", "delete"
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="permissions")


class UserFormAccess(Base):
    """User-Form access mapping model."""

    __tablename__ = "user_form_access"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    form_id = Column(Integer, ForeignKey("forms.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="form_access")
    form = relationship("Form", back_populates="form_access")

    # Unique constraint to prevent duplicate access assignments
    __table_args__ = (
        __import__('sqlalchemy').UniqueConstraint('user_id', 'form_id', name='unique_user_form_access'),
    )


class Form(Base):
    """Kobo form model."""

    __tablename__ = "forms"

    id = Column(Integer, primary_key=True, index=True)
    kobo_form_id = Column(String(100), unique=True, index=True, nullable=False)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    form_schema = Column(JSON, nullable=True)  # Store the full form schema from Kobo
    category = Column(String(100), nullable=True)  # e.g., "child_protection", "education"
    is_active = Column(Boolean, default=True, nullable=False)
    last_synced_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    raw_submissions = relationship("RawSubmission", back_populates="form", cascade="all, delete-orphan")
    submissions = relationship("Submission", back_populates="form", cascade="all, delete-orphan")
    indicators = relationship("Indicator", back_populates="form", cascade="all, delete-orphan")
    kpi_values = relationship("KPIValue", back_populates="form", cascade="all, delete-orphan")
    form_access = relationship("UserFormAccess", back_populates="form", cascade="all, delete-orphan")


class RawSubmission(Base):
    """Raw submission data from Kobo (before cleaning)."""

    __tablename__ = "raw_submissions"

    id = Column(Integer, primary_key=True, index=True)
    form_id = Column(Integer, ForeignKey("forms.id"), nullable=False, index=True)
    kobo_submission_id = Column(String(100), unique=True, index=True, nullable=False)
    submission_json = Column(JSON, nullable=False)  # Raw JSON from Kobo
    received_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    form = relationship("Form", back_populates="raw_submissions")


class Submission(Base):
    """Kobo form submission model (cleaned/normalized data)."""

    __tablename__ = "submissions"

    id = Column(Integer, primary_key=True, index=True)
    form_id = Column(Integer, ForeignKey("forms.id"), nullable=False, index=True)
    kobo_submission_id = Column(String(100), unique=True, index=True, nullable=False)
    submission_data = Column(JSON, nullable=False)  # Store the full submission JSON
    cleaned_data = Column(JSON, nullable=True)  # Normalized/cleaned data for easier querying
    submitted_at = Column(DateTime, nullable=True)
    location_lat = Column(Float, nullable=True)
    location_lng = Column(Float, nullable=True)
    location_name = Column(String(500), nullable=True)  # From form (province/district) at sync; or from reverse geocoding of location_lat/lng via backfill_locations or POST /api/submissions/geocode-pending
    # Province/District from form data (user input)
    province = Column(String(255), nullable=True, index=True)
    district = Column(String(255), nullable=True, index=True)
    processed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    form = relationship("Form", back_populates="submissions")


class Indicator(Base):
    """Computed indicator model."""

    __tablename__ = "indicators"

    id = Column(Integer, primary_key=True, index=True)
    form_id = Column(Integer, ForeignKey("forms.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    indicator_type = Column(String(50), nullable=False)  # e.g., "count", "percentage", "average", "sum"
    computation_rule = Column(JSON, nullable=True)  # Store how to compute this indicator
    value = Column(Float, nullable=True)
    indicator_metadata = Column(JSON, nullable=True)  # Additional metadata (renamed from 'metadata' to avoid SQLAlchemy conflict)
    computed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    form = relationship("Form", back_populates="indicators")


class SyncLog(Base):
    """Sync log for tracking ETL operations."""

    __tablename__ = "sync_logs"

    id = Column(Integer, primary_key=True, index=True)
    form_id = Column(Integer, ForeignKey("forms.id"), nullable=True)
    sync_type = Column(String(50), nullable=False)  # e.g., "full", "incremental", "webhook"
    status = Column(String(20), nullable=False)  # e.g., "running", "success", "error", "partial"
    records_processed = Column(Integer, default=0, nullable=False)
    records_added = Column(Integer, default=0, nullable=False)
    records_updated = Column(Integer, default=0, nullable=False)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    
    # Progress tracking fields for real-time updates
    current_form_index = Column(Integer, default=0, nullable=False)  # Which form is being synced (0-based)
    total_forms = Column(Integer, default=0, nullable=False)  # Total forms to sync
    current_submission_index = Column(Integer, default=0, nullable=False)  # Current submission being processed
    total_submissions = Column(Integer, default=0, nullable=False)  # Total submissions in current form
    current_form_id = Column(Integer, nullable=True)  # ID of form currently being synced
    current_form_title = Column(String(500), nullable=True)  # Title of current form
    progress_percentage = Column(Float, default=0.0, nullable=False)  # 0-100 percentage


class KPIDefinition(Base):
    """Formal KPI metadata and definitions."""

    __tablename__ = "kpi_definitions"

    id = Column(Integer, primary_key=True, index=True)
    kpi_code = Column(String(50), unique=True, index=True, nullable=False)
    label = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    unit = Column(String(20), nullable=False)  # %, count, days, kg, etc.
    formula_text = Column(Text, nullable=True)  # Human-readable formula

    computation_logic = Column(JSON, nullable=True)  # How to compute the KPI
    baseline_value = Column(Float, nullable=True)
    target_value = Column(Float, nullable=True)
    acceptable_range_min = Column(Float, nullable=True)
    acceptable_range_max = Column(Float, nullable=True)

    report_category = Column(String(50), nullable=False)  # WASH, Nutrition, Protection, Education, Food Security, Livelihoods
    sub_category = Column(String(100), nullable=True)
    indicator_type = Column(String(50), nullable=True)  # outcome, output, process

    is_active = Column(Boolean, default=True, nullable=False)
    is_custom = Column(Boolean, default=False, nullable=False)  # Custom vs standard
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    values = relationship("KPIValue", back_populates="definition", cascade="all, delete-orphan")


class KPIValue(Base):
    """Computed KPI values with time-series and geographic support."""

    __tablename__ = "kpi_values"

    id = Column(Integer, primary_key=True, index=True)
    kpi_definition_id = Column(Integer, ForeignKey("kpi_definitions.id"), nullable=False, index=True)
    form_id = Column(Integer, ForeignKey("forms.id"), nullable=True, index=True)

    geo_dimension_1 = Column(String(100), nullable=True, index=True)
    geo_dimension_2 = Column(String(100), nullable=True, index=True)
    geo_dimension_3 = Column(String(100), nullable=True, index=True)

    period_start = Column(DateTime, nullable=False, index=True)
    period_end = Column(DateTime, nullable=False)
    period_granularity = Column(String(20), nullable=False)  # daily, weekly, monthly, quarterly, annual

    value = Column(Float, nullable=False)
    baseline = Column(Float, nullable=True)
    target = Column(Float, nullable=True)
    sample_size = Column(Integer, nullable=False)  # Total submissions analyzed
    valid_sample_size = Column(Integer, nullable=False)  # After filtering/validation

    percent_complete = Column(Float, nullable=True)
    has_errors = Column(Boolean, default=False, nullable=False)

    computed_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    is_cached = Column(Boolean, default=False, nullable=False)
    cache_expires_at = Column(DateTime, nullable=True)

    definition = relationship("KPIDefinition", back_populates="values")
    form = relationship("Form")


class ReportCache(Base):
    """Cache pre-computed reports for performance."""

    __tablename__ = "report_cache"

    id = Column(Integer, primary_key=True, index=True)
    report_type = Column(String(50), nullable=False, index=True)
    filters_hash = Column(String(64), unique=True, nullable=False, index=True)
    form_id = Column(Integer, ForeignKey("forms.id"), nullable=True, index=True)

    result_json = Column(JSON, nullable=False)
    compressed = Column(Boolean, default=False, nullable=False)
    size_bytes = Column(Integer, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False, index=True)
    hit_count = Column(Integer, default=0, nullable=False)


class FormFieldMapping(Base):
    """Maps form fields to standard report dimensions (age, gender, location, etc.)."""

    __tablename__ = "form_field_mappings"

    id = Column(Integer, primary_key=True, index=True)
    form_id = Column(Integer, ForeignKey("forms.id"), nullable=False, unique=True, index=True)

    age_field = Column(String(255), nullable=True)  # e.g., "demographics/age" or NULL if not applicable
    gender_field = Column(String(255), nullable=True)
    household_size_field = Column(String(255), nullable=True)
    location_field = Column(String(255), nullable=True)
    
    # Custom mappings for Child Protection / Education
    custom_mappings = Column(JSON, nullable=True)  # e.g., {"grade_level": "education/grade", "protection_status": "..."}
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    form = relationship("Form")


class DatabaseMigration(Base):
    """Track database schema migrations and initializations."""

    __tablename__ = "database_migrations"

    id = Column(Integer, primary_key=True, index=True)
    initializer_guid = Column(String(36), unique=True, nullable=False, index=True, default=lambda: str(uuid.uuid4()))
    version = Column(Integer, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    applied_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Document(Base):
    """Track documents with unique identifiers."""

    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    document_guid = Column(String(36), unique=True, nullable=False, index=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    document_type = Column(String(100), nullable=False)  # e.g., "submission", "report", "export"
    entity_id = Column(Integer, nullable=True)  # Reference to the entity (submission_id, etc.)
    entity_type = Column(String(100), nullable=True)  # Type of entity (submission, form, etc.)
    doc_metadata = Column(JSON, nullable=True)  # Additional metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

