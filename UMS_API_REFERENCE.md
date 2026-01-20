# User Management System (UMS) - API Reference for Frontend

## Base Configuration
```
Base URL: http://localhost:8000/api
Authentication: Bearer Token (JWT)
Content-Type: application/json
```

---

## ROLES & ACCESS LEVELS

### User Roles

| Role | Form Access | User Management | Data Edit |
|------|-------------|-----------------|-----------|
| **admin** | All forms | Full control ✅ | Yes ✅ |
| **editor** | Assigned forms only | No ❌ | Yes ✅ |
| **viewer** | Assigned forms only | No ❌ | No ❌ |

---

## API ENDPOINTS

---

## 1. AUTHENTICATION

### Login
```
POST /auth/login
No Authentication Required
```

**Request:**
```json
{
  "username": "admin",
  "password": "admin123"
}
```

**Response (200):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

**Errors:**
- `401`: Incorrect username or password
- `400`: Inactive user

---

### Register
```
POST /auth/register
No Authentication Required
```

**Request:**
```json
{
  "username": "john_doe",
  "email": "john@example.com",
  "full_name": "John Doe",
  "password": "securepass123",
  "role": "viewer"
}
```

**Response (200):**
```json
{
  "id": 2,
  "username": "john_doe",
  "email": "john@example.com",
  "full_name": "John Doe",
  "role": "viewer",
  "is_active": true,
  "created_at": "2026-01-19T13:05:00",
  "updated_at": "2026-01-19T13:05:00"
}
```

**Errors:**
- `400`: Username already registered
- `400`: Email already registered

---

### Get Current User
```
GET /auth/me
Authentication: Required (Bearer Token)
```

**Response (200):**
```json
{
  "id": 1,
  "username": "admin",
  "email": "admin@example.com",
  "full_name": "Administrator",
  "role": "admin",
  "is_active": true,
  "created_at": "2026-01-19T12:00:00",
  "updated_at": "2026-01-19T12:00:00"
}
```

**Errors:**
- `401`: Invalid token
- `401`: Token expired
- `401`: Not authenticated

---

### Change Password
```
POST /auth/change-password
Authentication: Required (Bearer Token)
```

**Request:**
```json
{
  "old_password": "old_secure_pass",
  "new_password": "new_secure_pass123"
}
```

**Response (200):**
```json
{
  "detail": "Password changed successfully"
}
```

**Errors:**
- `400`: Incorrect old password
- `401`: Not authenticated

---

## 2. USER MANAGEMENT (Admin Only)

### List Users
```
GET /users?skip=0&limit=100
Authentication: Required (Admin)
```

**Response (200):**
```json
[
  {
    "id": 1,
    "username": "admin",
    "email": "admin@example.com",
    "full_name": "Administrator",
    "role": "admin",
    "is_active": true,
    "created_at": "2026-01-19T12:00:00",
    "updated_at": "2026-01-19T12:00:00"
  },
  {
    "id": 2,
    "username": "john_doe",
    "email": "john@example.com",
    "full_name": "John Doe",
    "role": "viewer",
    "is_active": true,
    "created_at": "2026-01-19T13:00:00",
    "updated_at": "2026-01-19T13:00:00"
  }
]
```

**Errors:**
- `403`: Not admin
- `401`: Not authenticated

---

### Get User
```
GET /users/{user_id}
Authentication: Required (Admin)
```

**Response (200):**
```json
{
  "id": 2,
  "username": "john_doe",
  "email": "john@example.com",
  "full_name": "John Doe",
  "role": "viewer",
  "is_active": true,
  "created_at": "2026-01-19T13:00:00",
  "updated_at": "2026-01-19T13:00:00"
}
```

**Errors:**
- `404`: User not found
- `403`: Not admin

---

### Update User
```
PUT /users/{user_id}
Authentication: Required (Admin)
```

**Request:**
```json
{
  "email": "john_new@example.com",
  "full_name": "John Updated",
  "role": "editor",
  "is_active": true
}
```

**Response (200):**
```json
{
  "id": 2,
  "username": "john_doe",
  "email": "john_new@example.com",
  "full_name": "John Updated",
  "role": "editor",
  "is_active": true,
  "created_at": "2026-01-19T13:00:00",
  "updated_at": "2026-01-19T14:30:00"
}
```

**Errors:**
- `404`: User not found
- `403`: Not admin

---

### Reset User Password
```
POST /users/{user_id}/reset-password
Authentication: Required (Admin)
```

**Request:**
```json
{
  "new_password": "new_secure_pass123"
}
```

**Response (200):**
```json
{
  "detail": "Password reset successfully for user john_doe"
}
```

**Errors:**
- `404`: User not found
- `403`: Not admin

---

## 3. FORM ACCESS MANAGEMENT (Admin Only)

### Assign Form to User
```
POST /users/{user_id}/forms/{form_id}
Authentication: Required (Admin)
```

**Request:** Empty body

**Response (200):**
```json
{
  "id": 5,
  "user_id": 2,
  "form_id": 1,
  "created_at": "2026-01-19T14:00:00",
  "updated_at": "2026-01-19T14:00:00"
}
```

**Errors:**
- `404`: User not found
- `404`: Form not found
- `400`: User already has access to this form
- `403`: Not admin

---

### Bulk Assign Forms
```
POST /users/{user_id}/forms/bulk
Authentication: Required (Admin)
```

**Request:**
```json
{
  "form_ids": [1, 2, 3]
}
```

**Response (200):**
```json
{
  "detail": "Successfully assigned 3 forms. 0 skipped (already assigned or invalid)."
}
```

**Errors:**
- `404`: User not found
- `403`: Not admin

---

### Revoke Form Access
```
DELETE /users/{user_id}/forms/{form_id}
Authentication: Required (Admin)
```

**Response (200):**
```json
{
  "detail": "Form access revoked successfully"
}
```

**Errors:**
- `404`: Form access not found
- `403`: Not admin

---

### Bulk Revoke Forms
```
DELETE /users/{user_id}/forms/bulk
Authentication: Required (Admin)
```

**Request:**
```json
{
  "form_ids": [1, 2, 3]
}
```

**Response (200):**
```json
{
  "detail": "Successfully revoked access to 3 forms. 0 skipped (not assigned)."
}
```

**Errors:**
- `404`: User not found
- `403`: Not admin

---

### Get User's Forms (Admin View)
```
GET /users/{user_id}/forms?skip=0&limit=100
Authentication: Required (Admin)
```

**Response (200):**
```json
[
  {
    "id": 1,
    "title": "Health Survey",
    "description": "Monthly health assessment form",
    "category": "health",
    "kobo_form_id": "kobo_123",
    "is_active": true,
    "last_synced_at": "2026-01-19T13:00:00",
    "created_at": "2026-01-18T12:00:00",
    "updated_at": "2026-01-19T13:00:00",
    "submission_count": 45
  },
  {
    "id": 2,
    "title": "Education Survey",
    "description": "Education assessment form",
    "category": "education",
    "kobo_form_id": "kobo_124",
    "is_active": true,
    "last_synced_at": "2026-01-19T13:00:00",
    "created_at": "2026-01-18T12:00:00",
    "updated_at": "2026-01-19T13:00:00",
    "submission_count": 32
  }
]
```

**Errors:**
- `404`: User not found
- `403`: Not admin

---

## 4. FORMS (Role-Based Access Control)

### List Forms
```
GET /forms?skip=0&limit=100&category=health
Authentication: Required
```

**Response (200):**
```json
[
  {
    "id": 1,
    "title": "Health Survey",
    "description": "Monthly health assessment form",
    "category": "health",
    "kobo_form_id": "kobo_123",
    "is_active": true,
    "last_synced_at": "2026-01-19T13:00:00",
    "created_at": "2026-01-18T12:00:00",
    "updated_at": "2026-01-19T13:00:00",
    "submission_count": 45
  }
]
```

**Access Control:**
- **Admin users**: See all forms in the system
- **Editor/Viewer users**: See only forms assigned to them

---

### Get Specific Form
```
GET /forms/{form_id}
Authentication: Required
```

**Response (200):**
```json
{
  "id": 1,
  "title": "Health Survey",
  "description": "Monthly health assessment form",
  "category": "health",
  "kobo_form_id": "kobo_123",
  "is_active": true,
  "last_synced_at": "2026-01-19T13:00:00",
  "created_at": "2026-01-18T12:00:00",
  "updated_at": "2026-01-19T13:00:00",
  "submission_count": 45
}
```

**Errors:**
- `404`: Form not found
- `403`: Access denied to this form (non-admin without access)
- `401`: Not authenticated

---

## HTTP Status Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 400 | Bad Request |
| 401 | Unauthorized |
| 403 | Forbidden |
| 404 | Not Found |
| 500 | Server Error |

---

## Authentication Header

All authenticated endpoints require:
```
Authorization: Bearer {access_token}
```

Store token from login response and include in all subsequent requests.
