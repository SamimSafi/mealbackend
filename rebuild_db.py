#!/usr/bin/env python
"""
EXTREME: Delete corrupted database completely and rebuild from scratch.
WARNS before deleting - requires user confirmation.
"""

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from database import engine, SessionLocal, init_db
from models import Base, User, Organization
from auth import get_password_hash
from config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

db_url = settings.DATABASE_URL
if db_url.startswith("sqlite:///"):
    db_path = db_url.replace("sqlite:///", "")
else:
    print("❌ Only SQLite databases can be rebuilt this way!")
    sys.exit(1)

print("\n" + "="*70)
print("WARNING: DATABASE REBUILD - EXTREME OPTION")
print("="*70)
print(f"\nDatabase path: {db_path}")
print("\nWARNING: This will DELETE the entire database and rebuild it!")
print("   All data will be lost. Only do this if database is corrupted.")

response = input("\nType 'YES' to proceed with database rebuild: ").strip()

if response != "YES":
    print("Rebuild cancelled")
    sys.exit(0)

print("\n" + "="*70)

try:
    if os.path.exists(db_path):
        print(f"\nDeleting corrupted database...")
        os.remove(db_path)
        print("   [OK] Database file deleted")
    else:
        print(f"\nWARNING: Database file not found at {db_path}")
    
    print("\nRebuilding database from scratch...")
    
    Base.metadata.drop_all(bind=engine)
    print("   [OK] Old tables dropped")
    
    init_db()
    print("   [OK] New tables created")
    
    db = SessionLocal()
    admin = db.query(User).filter(User.username == "admin").first()
    
    if admin:
        print(f"   [OK] Admin user created:")
        print(f"      Username: {admin.username}")
        print(f"      Email: {admin.email}")
        print(f"      Role: {admin.role}")
        print(f"      Active: {admin.is_active}")
        print(f"      Hash (first 50 chars): {admin.hashed_password[:50]}")
    else:
        print("   ERROR: Admin user not created!")
        db.close()
        sys.exit(1)
    
    db.close()
    
    print("\n" + "="*70)
    print("DATABASE REBUILD COMPLETE!")
    print("="*70)
    print("\nDefault login credentials:")
    print("   Username: admin")
    print("   Password: admin123")
    print("\nIMPORTANT: Change this password after first login!")
    print("="*70 + "\n")
    
except Exception as e:
    print(f"\n❌ Error during rebuild: {str(e)}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
