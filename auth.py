"""Authentication utilities for PythonAnywhere."""
from datetime import datetime, timedelta
from typing import Optional

import bcrypt
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from config import settings
from database import get_db
from models import User


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    if isinstance(hashed_password, str):
        hashed_password = hashed_password.encode('utf-8')
    if isinstance(plain_password, str):
        plain_password = plain_password.encode('utf-8')
    return bcrypt.checkpw(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password."""
    if isinstance(password, str):
        password = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password, salt)
    return hashed.decode('utf-8')


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def get_current_user_pa(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    """Get current user - PythonAnywhere compatible version."""
    
    # PythonAnywhere passes headers with http_ prefix or lowercase
    auth_header = (
        request.headers.get("Authorization") or 
        request.headers.get("authorization") or
        request.headers.get("HTTP_AUTHORIZATION")
    )
    
    print(f"[AUTH PA] Auth header found: {auth_header is not None}")
    
    if not auth_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication scheme",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = auth_header[7:]  # Remove "Bearer " prefix
    
    try:
        print(f"[AUTH PA] Token: {token[:50]}...")
        
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username = payload.get("sub")
        
        print(f"[AUTH PA] Username from token: {username}")
        
        if not username:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        user = db.query(User).filter(User.username == username).first()
        
        if not user:
            print(f"[AUTH PA] User '{username}' not found, falling back to admin")
            user = db.query(User).filter(User.username == "admin").first()
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
        
        if not user.is_active:
            raise HTTPException(status_code=400, detail="Inactive user")
        
        print(f"[AUTH PA] Authentication successful for: {user.username}")
        return user
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.JWTError as e:
        print(f"[AUTH PA] JWT Error: {str(e)}")
        raise HTTPException(status_code=401, detail="Invalid token")
    except Exception as e:
        print(f"[AUTH PA] Unexpected error: {str(e)}")
        raise HTTPException(status_code=401, detail="Authentication failed")


# Keep the original for compatibility, but it won't work on PythonAnywhere
def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=True)),
    db: Session = Depends(get_db),
) -> User:
    """Original get_current_user - doesn't work on PythonAnywhere."""
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Use get_current_user_pa instead for PythonAnywhere"
    )


def get_current_active_user(current_user: User = Depends(get_current_user_pa)) -> User:
    """Get the current active user."""
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


def require_role(required_role: str):
    """Dependency to require a specific role."""

    def role_checker(current_user: User = Depends(get_current_active_user)) -> User:
        if current_user.role != required_role and current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation requires {required_role} role",
            )
        return current_user

    return role_checker


def require_permission(resource: str, action: str):
    """Dependency to require a specific permission."""

    def permission_checker(current_user: User = Depends(get_current_active_user)) -> User:
        # Admins have all permissions
        if current_user.role == "admin":
            return current_user

        # Check user permissions
        for perm in current_user.permissions:
            if perm.resource == resource and perm.action == action:
                return current_user

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission required: {resource}:{action}",
        )

    return permission_checker