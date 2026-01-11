"""Database models."""
from datetime import datetime
from enum import Enum

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
    location_name = Column(String(500), nullable=True)
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
    status = Column(String(20), nullable=False)  # e.g., "success", "error", "partial"
    records_processed = Column(Integer, default=0, nullable=False)
    records_added = Column(Integer, default=0, nullable=False)
    records_updated = Column(Integer, default=0, nullable=False)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)

