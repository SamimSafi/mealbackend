#!/usr/bin/env python
"""Reset admin user password to fix 'Invalid salt' error."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from database import SessionLocal
from models import User
from auth import get_password_hash

db = SessionLocal()

try:
    admin = db.query(User).filter(User.username == "admin").first()
    
    if not admin:
        print("❌ Admin user not found")
        sys.exit(1)
    
    print(f"✅ Found admin user: {admin.username}")
    print(f"   Email: {admin.email}")
    print(f"   Current hash (first 50 chars): {admin.hashed_password[:50] if admin.hashed_password else 'None'}")
    
    new_password = "admin123"
    admin.hashed_password = get_password_hash(new_password)
    
    db.commit()
    
    print(f"✅ Password reset successfully")
    print(f"   New password hash (first 50 chars): {admin.hashed_password[:50]}")
    print(f"\n📝 Login credentials:")
    print(f"   Username: admin")
    print(f"   Password: {new_password}")
    
except Exception as e:
    print(f"❌ Error resetting password: {e}")
    db.rollback()
    sys.exit(1)
finally:
    db.close()
