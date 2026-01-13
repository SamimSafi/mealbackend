"""Database configuration and session management."""
import logging
import sys
import os
from pathlib import Path

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent))

from config import settings
# Import Base from models to avoid a separate base.py file
from models import Base

logger = logging.getLogger(__name__)

# Create SQLite engine
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
    echo=False,  # Set to True for SQL query logging (debug only)
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """Dependency for getting database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables and default data."""
    # IMPORTANT: Import models inside the function to avoid circular imports
    from models import (
        Organization, User, Branding, Form, RawSubmission, 
        Submission, Indicator, UserPermission, SyncLog,
        KPIDefinition, KPIValue, ReportCache, FormFieldMapping,
        DatabaseMigration, Document
    )
    from auth import get_password_hash
    from migrations import check_schema_changes
    
    logger.info("Initializing database...")
    
    # Create all tables
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Database tables created successfully")
        
        # Verify tables were created
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        logger.info(f"📋 Tables created: {', '.join(tables)}")
        
        # Check if 'users' table exists
        if 'users' in tables:
            logger.info("✅ 'users' table exists and is ready")
        else:
            logger.error("❌ 'users' table was NOT created!")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error creating tables: {e}")
        raise
    
    # Create default organization if it doesn't exist
    db = SessionLocal()
    try:
        # Check if default organization exists
        org_exists = db.query(Organization).filter(Organization.name == "Default").first()
        if not org_exists:
            org = Organization(
                name="Default", 
                description="Default organization for initial setup"
            )
            db.add(org)
            db.commit()
            logger.info("✅ Default organization created")
        else:
            logger.info("✅ Default organization already exists")
            
        # Create default admin user if it doesn't exist
        user_exists = db.query(User).filter(User.username == "admin").first()
        if not user_exists:
            admin_user = User(
                username="admin",
                email="admin@example.com",
                hashed_password=get_password_hash("admin123"),
                full_name="Administrator",
                role="admin",
                organization_id=1,
                is_active=True
            )
            db.add(admin_user)
            db.commit()
            logger.info("✅ Default admin user created (username: 'admin', password: 'admin123')")
        else:
            logger.info("✅ Default admin user already exists")
            
    except Exception as e:
        logger.error(f"⚠️ Error creating default data: {e}")
        db.rollback()
    finally:
        db.close()
    
    return True


def migrate_db():
    """
    Run database migrations and schema updates.
    Called automatically on app startup.
    """
    from models import DatabaseMigration, Organization, User
    from auth import get_password_hash
    from migrations import check_schema_changes
    
    db = SessionLocal()
    try:
        logger.info("Running database migrations...")
        
        if not check_schema_changes(engine, Base):
            logger.info("Schema changes detected, recreating tables...")
            Base.metadata.create_all(bind=engine)
            logger.info("Tables recreated successfully")
        
        org_exists = db.query(Organization).filter(Organization.name == "Default").first()
        if not org_exists:
            org = Organization(
                name="Default",
                description="Default organization for initial setup"
            )
            db.add(org)
            db.commit()
            db.refresh(org)
            logger.info("Default organization created")
        
        admin_exists = db.query(User).filter(User.username == "admin").first()
        if not admin_exists:
            admin = User(
                username="admin",
                email="admin@example.com",
                hashed_password=get_password_hash("admin123"),
                full_name="Administrator",
                role="admin",
                organization_id=1,
                is_active=True
            )
            db.add(admin)
            db.commit()
            logger.info("Default admin user created")
        
        logger.info("Database migration complete")
        return True
        
    except Exception as e:
        logger.error(f"Error during migration: {e}")
        db.rollback()
        return False
    finally:
        db.close()