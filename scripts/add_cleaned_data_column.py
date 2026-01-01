"""Script to add cleaned_data column to submissions table if it doesn't exist."""
import sqlite3
import os
from config import settings

def add_cleaned_data_column():
    """Add cleaned_data column to submissions table if it doesn't exist."""
    db_path = settings.DATABASE_URL.replace("sqlite:///", "")
    if db_path.startswith("./"):
        db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), db_path[2:])
    
    if not os.path.exists(db_path):
        print(f"Database file not found: {db_path}")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if column exists
        cursor.execute("PRAGMA table_info(submissions)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if "cleaned_data" not in columns:
            print("Adding cleaned_data column to submissions table...")
            cursor.execute("ALTER TABLE submissions ADD COLUMN cleaned_data TEXT")
            conn.commit()
            print("Column added successfully!")
        else:
            print("cleaned_data column already exists.")
    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    add_cleaned_data_column()

