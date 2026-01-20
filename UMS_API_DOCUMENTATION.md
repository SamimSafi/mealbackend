# User Management System (UMS) - API Documentation

## Base URL
```
https://your-domain.com/api
```

## Authentication
All endpoints (except login/register) require a Bearer token in the Authorization header:
```
Authorization: Bearer {access_token}
```

---

## 1. Authentication Endpoints

### 1.1 User Login
**POST** `/auth/login`

**Request:**
```json
{
  "username": "admin",
  "password": "admin123"
}
```

**Response (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

**Error Responses:**
- **401 Unauthorized**: Incorrect username or password
- **400 Bad Request**: Inactive user

---

### 1.2 User Registration
**POST** `/auth/register`

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

**Response (200 OK):**
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

**Error Responses:**
- **400 Bad Request**: Username already registered / Email already registered

---

### 1.3 Get Current User Info
**GET** `/auth/me`

**Headers:**
```
Authorization: Bearer {access_token}
```

**Response (200 OK):**
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

**Error Responses:**
- **401 Unauthorized**: Invalid or expired token

---

## 2. User Management Endpoints (Admin Only)

### 2.1 List All Users
**GET** `/users?skip=0&limit=100`

**Headers:**
```
Authorization: Bearer {admin_token}
```

**Query Parameters:**
- `skip` (optional): Number of users to skip (default: 0)
- `limit` (optional): Maximum number of users to return (default: 100)

**Response (200 OK):**
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
    "username": "john_viewer",
    "email": "john@example.com",
    "full_name": "John Viewer",
    "role": "viewer",
    "is_active": true,
    "created_at": "2026-01-19T13:00:00",
    "updated_at": "2026-01-19T13:00:00"
  }
]
```

**Error Responses:**
- **403 Forbidden**: User is not admin

---

### 2.2 Get Specific User
**GET** `/users/{user_id}`

**Headers:**
```
Authorization: Bearer {admin_token}
```

**Response (200 OK):**
```json
{
  "id": 2,
  "username": "john_viewer",
  "email": "john@example.com",
  "full_name": "John Viewer",
  "role": "viewer",
  "is_active": true,
  "created_at": "2026-01-19T13:00:00",
  "updated_at": "2026-01-19T13:00:00"
}
```

**Error Responses:**
- **404 Not Found**: User not found
- **403 Forbidden**: User is not admin

---

### 2.3 Update User
**PUT** `/users/{user_id}`

**Headers:**
```
Authorization: Bearer {admin_token}
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

**Response (200 OK):**
```json
{
  "id": 2,
  "username": "john_viewer",
  "email": "john_new@example.com",
  "full_name": "John Updated",
  "role": "editor",
  "is_active": true,
  "created_at": "2026-01-19T13:00:00",
  "updated_at": "2026-01-19T14:30:00"
}
```

**Error Responses:**
- **404 Not Found**: User not found
- **403 Forbidden**: User is not admin

---

## 3. User Form Access Endpoints (Admin Only)

### 3.1 Assign Form to User
**POST** `/users/{user_id}/forms/{form_id}`

**Headers:**
```
Authorization: Bearer {admin_token}
```

**Response (200 OK):**
```json
{
  "id": 5,
  "user_id": 2,
  "form_id": 1,
  "created_at": "2026-01-19T14:00:00",
  "updated_at": "2026-01-19T14:00:00"
}
```

**Error Responses:**
- **404 Not Found**: User not found / Form not found
- **400 Bad Request**: User already has access to this form
- **403 Forbidden**: User is not admin

---

### 3.2 Revoke Form Access from User
**DELETE** `/users/{user_id}/forms/{form_id}`

**Headers:**
```
Authorization: Bearer {admin_token}
```

**Response (200 OK):**
```json
{
  "detail": "Form access revoked successfully"
}
```

**Error Responses:**
- **404 Not Found**: Form access not found
- **403 Forbidden**: User is not admin

---

### 3.3 Get All Forms Assigned to User
**GET** `/users/{user_id}/forms?skip=0&limit=100`

**Headers:**
```
Authorization: Bearer {admin_token}
```

**Query Parameters:**
- `skip` (optional): Number of forms to skip (default: 0)
- `limit` (optional): Maximum number of forms to return (default: 100)

**Response (200 OK):**
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

**Error Responses:**
- **404 Not Found**: User not found
- **403 Forbidden**: User is not admin

---

## 4. Form Access - User Perspective

### 4.1 Get My Forms (Current User)
**GET** `/me/forms?skip=0&limit=100&category=health`

**Headers:**
```
Authorization: Bearer {user_token}
```

**Query Parameters:**
- `skip` (optional): Number of forms to skip (default: 0)
- `limit` (optional): Maximum number of forms to return (default: 100)
- `category` (optional): Filter by form category

**Response (200 OK):**
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

**Note:** Non-admin users only see forms assigned to them. Admins see all forms.

---

### 4.2 List Forms (Access Controlled)
**GET** `/forms?skip=0&limit=100&category=health`

**Headers:**
```
Authorization: Bearer {user_token}
```

**Query Parameters:**
- `skip` (optional): Number of forms to skip (default: 0)
- `limit` (optional): Maximum number of forms to return (default: 100)
- `category` (optional): Filter by form category

**Response (200 OK):**
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
- **Admins**: See all forms
- **Regular Users**: See only assigned forms

---

### 4.3 Get Specific Form
**GET** `/forms/{form_id}`

**Headers:**
```
Authorization: Bearer {user_token}
```

**Response (200 OK):**
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

**Error Responses:**
- **404 Not Found**: Form not found
- **403 Forbidden**: Access denied to this form (non-admin user doesn't have access)

---

## 5. User Roles

| Role | Description | Permissions |
|------|-------------|-------------|
| **admin** | Administrator | Full access to all features, forms, and user management |
| **editor** | Editor | Can view forms, create/edit data |
| **viewer** | Viewer | Read-only access, can view forms and statistics |

---

## 6. Common Request/Response Formats

### UserResponse Schema
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

### FormResponse Schema
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

### UserFormAccessResponse Schema
```json
{
  "id": 5,
  "user_id": 2,
  "form_id": 1,
  "created_at": "2026-01-19T14:00:00",
  "updated_at": "2026-01-19T14:00:00"
}
```

---

## 7. HTTP Status Codes

| Code | Meaning |
|------|---------|
| **200** | OK - Request successful |
| **400** | Bad Request - Invalid input |
| **401** | Unauthorized - Invalid credentials or token |
| **403** | Forbidden - No permission |
| **404** | Not Found - Resource not found |
| **500** | Internal Server Error |

---

## 8. Frontend Integration Example

### Login Flow
```javascript
// 1. Login
const response = await fetch('https://your-domain.com/api/auth/login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    username: 'admin',
    password: 'admin123'
  })
});

const data = await response.json();
const token = data.access_token;
localStorage.setItem('token', token);

// 2. Get current user info
const userResponse = await fetch('https://your-domain.com/api/auth/me', {
  headers: {
    'Authorization': `Bearer ${token}`
  }
});
const user = await userResponse.json();

// 3. Get user's forms
const formsResponse = await fetch('https://your-domain.com/api/me/forms', {
  headers: {
    'Authorization': `Bearer ${token}`
  }
});
const forms = await formsResponse.json();

// 4. Display forms in dropdown
forms.forEach(form => {
  console.log(`${form.id}: ${form.title}`);
});
```

### Admin - Assign Form to User
```javascript
const token = localStorage.getItem('token');

// Assign form 1 to user 2
const response = await fetch('https://your-domain.com/api/users/2/forms/1', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`
  }
});

if (response.ok) {
  console.log('Form assigned successfully');
}
```

---

## Notes
- Token expiration: Check `settings.ACCESS_TOKEN_EXPIRE_MINUTES` (typically 30-60 minutes)
- All timestamps are in UTC format (ISO 8601)
- Default admin credentials: `username: admin`, `password: admin123`
- Never expose tokens in URLs or logs
