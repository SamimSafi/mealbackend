"""Authentication utilities."""
from datetime import datetime, timedelta
from typing import Optional

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from config import settings
from database import get_db
from models import User

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")


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


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    """Get the current authenticated user."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return user


def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
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

