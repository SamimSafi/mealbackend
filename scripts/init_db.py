"""Initialize database."""
import sys
from pathlib import Path

# Add parent directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import init_db

if __name__ == "__main__":
    print("Initializing database...")
    init_db()
    print("Database initialized successfully!")

