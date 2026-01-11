"""Initialize database."""
import sys
from pathlib import Path

# Add parent directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import init_db, engine
from sqlalchemy import text

if __name__ == "__main__":
    print("Initializing database...")
    init_db()
    
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
        conn.commit()
    
    print("Database initialized successfully!")

