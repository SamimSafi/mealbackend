"""Migrate database to add organizations and branding tables."""
import sys
import sqlite3
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

def migrate_db():
    """Migrate existing database to new schema."""
    db_path = "data/kobo_dashboard.db"
    
    if not Path(db_path).exists():
        print("[OK] Database doesn't exist yet. It will be created on first run.")
        return
    
    print(f"Migrating database: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='organizations';")
        if cursor.fetchone():
            print("[OK] Organizations table already exists")
        else:
            print("Creating organizations table...")
            cursor.execute("""
                CREATE TABLE organizations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name VARCHAR(255) UNIQUE NOT NULL,
                    description TEXT,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
            print("[OK] Organizations table created")
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='branding';")
        if cursor.fetchone():
            print("[OK] Branding table already exists")
        else:
            print("Creating branding table...")
            cursor.execute("""
                CREATE TABLE branding (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    organization_id INTEGER UNIQUE NOT NULL,
                    company_name VARCHAR(255) NOT NULL,
                    logo_path VARCHAR(500),
                    primary_color VARCHAR(50),
                    secondary_color VARCHAR(50),
                    description TEXT,
                    is_active BOOLEAN DEFAULT 1,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (organization_id) REFERENCES organizations (id)
                )
            """)
            conn.commit()
            print("[OK] Branding table created")
        
        cursor.execute("PRAGMA table_info(users)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if "organization_id" not in columns:
            print("Adding organization_id column to users table...")
            cursor.execute("""
                ALTER TABLE users ADD COLUMN organization_id INTEGER REFERENCES organizations(id)
            """)
            conn.commit()
            print("[OK] organization_id column added to users table")
        else:
            print("[OK] organization_id column already exists in users table")
        
        cursor.execute("SELECT COUNT(*) FROM organizations;")
        org_count = cursor.fetchone()[0]
        
        if org_count == 0:
            print("Creating default organization...")
            cursor.execute("""
                INSERT INTO organizations (name, description)
                VALUES ('Default', 'Default organization')
            """)
            conn.commit()
            
            cursor.execute("SELECT id FROM organizations WHERE name='Default';")
            org_id = cursor.fetchone()[0]
            
            cursor.execute("""
                UPDATE users SET organization_id = ? WHERE role = 'admin'
            """, (org_id,))
            conn.commit()
            print("[OK] Default organization created and linked to admin users")
        else:
            print("[OK] Organizations already exist")
        
        print("\n[SUCCESS] Migration completed successfully!")
        
    except Exception as e:
        print(f"[ERROR] Migration failed: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    try:
        migrate_db()
    except Exception as e:
        print(f"Error during migration: {e}")
        sys.exit(1)
