"""Script to create a new user."""
import sys
from pathlib import Path
from sqlalchemy.orm import Session

# Add parent directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import SessionLocal
from models import User
from auth import get_password_hash


def create_user(username: str, email: str, password: str, role: str = "viewer", full_name: str = None):
    """Create a new user."""
    db: Session = SessionLocal()
    try:
        # Check if user exists
        existing = db.query(User).filter(
            (User.username == username) | (User.email == email)
        ).first()
        if existing:
            print(f"User with username '{username}' or email '{email}' already exists!")
            return False
        
        # Create user
        user = User(
            username=username,
            email=email,
            hashed_password=get_password_hash(password),
            full_name=full_name or username,
            role=role,
            is_active=True,
        )
        db.add(user)
        db.commit()
        print(f"User '{username}' created successfully!")
        return True
    except Exception as e:
        print(f"Error creating user: {e}")
        db.rollback()
        return False
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python create_user.py <username> <email> <password> [role] [full_name]")
        sys.exit(1)
    
    username = sys.argv[1]
    email = sys.argv[2]
    password = sys.argv[3]
    role = sys.argv[4] if len(sys.argv) > 4 else "viewer"
    full_name = sys.argv[5] if len(sys.argv) > 5 else None
    
    create_user(username, email, password, role, full_name)

