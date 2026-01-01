"""Database configuration and session management."""
import logging
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from config import settings

logger = logging.getLogger(__name__)

# Create SQLite engine
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
    echo=False,
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


def get_db():
    """Dependency for getting database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables."""
    import os
    import sqlite3

    # Create data directory if it doesn't exist
    db_path = settings.DATABASE_URL.replace("sqlite:///", "")
    if db_path.startswith("./"):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

    Base.metadata.create_all(bind=engine)
    
    # Add cleaned_data column if it doesn't exist (migration)
    if "sqlite" in settings.DATABASE_URL:
        try:
            conn = engine.raw_connection()
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(submissions)")
            columns = [row[1] for row in cursor.fetchall()]
            
            if "cleaned_data" not in columns:
                cursor.execute("ALTER TABLE submissions ADD COLUMN cleaned_data TEXT")
                conn.commit()
            
            cursor.close()
            conn.close()
        except Exception as e:
            logger.warning(f"Could not add cleaned_data column: {e}")

