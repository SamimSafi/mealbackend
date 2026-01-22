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


def test_delete_user_as_admin(client, admin_headers, test_user, db):
    """Test deleting a user as admin."""
    # Ensure user exists
    user_id = test_user.id
    response = client.get(f"/api/users/{user_id}", headers=admin_headers)
    assert response.status_code == status.HTTP_200_OK

    # Delete user
    response = client.delete(f"/api/users/{user_id}", headers=admin_headers)
    assert response.status_code == status.HTTP_200_OK
    assert "deleted successfully" in response.json()["detail"]

    # Verify user is gone
    response = client.get(f"/api/users/{user_id}", headers=admin_headers)
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_delete_user_unauthorized(client, auth_headers, test_user):
    """Test deleting a user without admin role."""
    user_id = test_user.id
    response = client.delete(f"/api/users/{user_id}", headers=auth_headers)
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_delete_self_not_allowed(client, admin_headers, admin_user):
    """Test that an admin cannot delete themselves."""
    user_id = admin_user.id
    response = client.delete(f"/api/users/{user_id}", headers=admin_headers)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Cannot delete your own account" in response.json()["detail"]

