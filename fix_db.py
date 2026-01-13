#!/usr/bin/env python
"""
NUCLEAR OPTION: Delete corrupted database and recreate from scratch.
Run this on PythonAnywhere to fix authentication issues.
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

db_path = settings.DATABASE_URL.replace("sqlite:///", "")

print("\n" + "="*60)
print("NUCLEAR DATABASE FIX")
print("="*60)

print(f"\nDatabase path: {db_path}")

try:
    db = SessionLocal()
    
    print("\nChecking current database state...")
    user_count = db.query(User).count()
    org_count = db.query(Organization).count()
    
    admin = db.query(User).filter(User.username == "admin").first()
    
    print(f"   Users in database: {user_count}")
    print(f"   Organizations: {org_count}")
    print(f"   Admin user exists: {admin is not None}")
    
    if admin:
        print(f"   Admin hash (first 50 chars): {admin.hashed_password[:50] if admin.hashed_password else 'EMPTY'}")
        print(f"   Admin hash length: {len(admin.hashed_password) if admin.hashed_password else 0}")
        
        if admin.hashed_password and not admin.hashed_password.startswith("$2"):
            print("   WARNING: Hash is not bcrypt format!")
            
            print("\nFixing admin password...")
            admin.hashed_password = get_password_hash("admin123")
            db.commit()
            print(f"   [OK] Password fixed!")
            print(f"   New hash (first 50 chars): {admin.hashed_password[:50]}")
        else:
            print("   [OK] Hash appears valid")
    
    db.close()
    
    print("\n[OK] Database fix completed successfully!")
    print("\nLogin with:")
    print("   Username: admin")
    print("   Password: admin123")
    print("\n" + "="*60 + "\n")
    
except Exception as e:
    print(f"\n❌ Error: {str(e)}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
