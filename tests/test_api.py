"""Tests for API endpoints."""
import pytest
from fastapi import status


def test_health_check(client):
    """Test health check endpoint."""
    response = client.get("/api/health")
    assert response.status_code == status.HTTP_200_OK
    assert "status" in response.json()


def test_list_forms_unauthorized(client):
    """Test listing forms without authentication."""
    response = client.get("/api/forms")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_list_forms(client, auth_headers):
    """Test listing forms."""
    response = client.get("/api/forms", headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK
    assert isinstance(response.json(), list)


def test_get_dashboard_summary(client, auth_headers):
    """Test getting dashboard summary."""
    response = client.get("/api/dashboard/summary", headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "total_forms" in data
    assert "total_submissions" in data
    assert "total_indicators" in data


def test_list_users_admin_only(client, auth_headers):
    """Test that listing users requires admin role."""
    response = client.get("/api/users", headers=auth_headers)
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_list_users_as_admin(client, admin_headers):
    """Test listing users as admin."""
    response = client.get("/api/users", headers=admin_headers)
    assert response.status_code == status.HTTP_200_OK
    assert isinstance(response.json(), list)


def test_sync_requires_admin(client, auth_headers):
    """Test that sync requires admin role."""
    response = client.post(
        "/api/sync",
        json={"sync_type": "incremental"},
        headers=auth_headers,
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN

