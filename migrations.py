"""Database migration system with automatic schema management."""
import logging
import uuid
from datetime import datetime
from typing import List, Callable, Dict

from sqlalchemy import inspect
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class Migration:
    """Represents a single database migration."""
    
    def __init__(self, version: int, name: str, description: str = ""):
        self.version = version
        self.name = name
        self.description = description
        self.initializer_guid = str(uuid.uuid4())
        self.upgrade_func = None
        self.downgrade_func = None
    
    def upgrade(self, db: Session):
        """Apply the migration upgrade."""
        if self.upgrade_func:
            self.upgrade_func(db)
    
    def downgrade(self, db: Session):
        """Revert the migration."""
        if self.downgrade_func:
            self.downgrade_func(db)


class MigrationManager:
    """Manages database migrations."""
    
    def __init__(self, engine, session_factory):
        self.engine = engine
        self.session_factory = session_factory
        self.migrations: Dict[int, Migration] = {}
    
    def register(self, version: int, name: str, description: str = ""):
        """Register a migration decorator."""
        def decorator(func):
            migration = Migration(version, name, description)
            migration.upgrade_func = func
            self.migrations[version] = migration
            return func
        return decorator
    
    def get_applied_migrations(self, db: Session) -> List[int]:
        """Get list of already applied migration versions."""
        try:
            from models import DatabaseMigration
            applied = db.query(DatabaseMigration.version).all()
            return [v[0] for v in applied]
        except Exception:
            return []
    
    def apply_migration(self, db: Session, migration: Migration) -> bool:
        """Apply a single migration."""
        try:
            logger.info(f"Applying migration {migration.version}: {migration.name}")
            
            migration.upgrade(db)
            
            from models import DatabaseMigration
            migration_record = DatabaseMigration(
                initializer_guid=migration.initializer_guid,
                version=migration.version,
                name=migration.name,
                description=migration.description,
                applied_at=datetime.utcnow(),
            )
            db.add(migration_record)
            db.commit()
            
            logger.info(f"Migration {migration.version} applied successfully")
            return True
        except Exception as e:
            logger.error(f"Error applying migration {migration.version}: {e}")
            db.rollback()
            return False
    
    def run_pending_migrations(self, db: Session) -> bool:
        """Run all pending migrations."""
        try:
            from models import DatabaseMigration
            
            applied_versions = self.get_applied_migrations(db)
            pending = sorted([v for v in self.migrations.keys() if v not in applied_versions])
            
            if not pending:
                logger.info("No pending migrations")
                return True
            
            logger.info(f"Found {len(pending)} pending migrations")
            
            for version in pending:
                migration = self.migrations[version]
                if not self.apply_migration(db, migration):
                    return False
            
            logger.info("All pending migrations applied successfully")
            return True
        except Exception as e:
            logger.error(f"Error running migrations: {e}")
            return False


def check_schema_changes(engine, Base) -> bool:
    """
    Detect if there are schema changes between models and database.
    Returns True if schema matches, False if changes detected.
    """
    try:
        inspector = inspect(engine)
        db_tables = set(inspector.get_table_names())
        model_tables = set(Base.metadata.tables.keys())
        
        if db_tables != model_tables:
            missing = model_tables - db_tables
            extra = db_tables - model_tables
            if missing:
                logger.warning(f"Missing tables: {missing}")
            if extra:
                logger.warning(f"Extra tables: {extra}")
            return False
        
        for table_name in model_tables:
            model_table = Base.metadata.tables[table_name]
            db_table = inspector.get_table_names()
            
            if table_name in db_table:
                db_columns = {col['name'] for col in inspector.get_columns(table_name)}
                model_columns = {col.name for col in model_table.columns}
                
                if db_columns != model_columns:
                    missing = model_columns - db_columns
                    extra = db_columns - model_columns
                    if missing:
                        logger.warning(f"Table {table_name} missing columns: {missing}")
                    if extra:
                        logger.warning(f"Table {table_name} extra columns: {extra}")
                    return False
        
        logger.info("Schema matches models")
        return True
    except Exception as e:
        logger.error(f"Error checking schema: {e}")
        return False
