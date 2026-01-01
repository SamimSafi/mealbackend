"""Tests for authentication."""
import pytest
from fastapi import status


def test_login_success(client, test_user):
    """Test successful login."""
    response = client.post(
        "/api/auth/login",
        data={"username": "testuser", "password": "testpass123"},
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_invalid_credentials(client, test_user):
    """Test login with invalid credentials."""
    response = client.post(
        "/api/auth/login",
        data={"username": "testuser", "password": "wrongpassword"},
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_get_current_user(client, auth_headers):
    """Test getting current user info."""
    response = client.get("/api/auth/me", headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["username"] == "testuser"


def test_get_current_user_unauthorized(client):
    """Test getting current user without token."""
    response = client.get("/api/auth/me")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_register_user(client):
    """Test user registration."""
    response = client.post(
        "/api/auth/register",
        json={
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "password123",
            "full_name": "New User",
            "role": "viewer",
        },
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["username"] == "newuser"
    assert data["email"] == "newuser@example.com"


def test_register_duplicate_username(client, test_user):
    """Test registering with duplicate username."""
    response = client.post(
        "/api/auth/register",
        json={
            "username": "testuser",
            "email": "different@example.com",
            "password": "password123",
        },
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST

