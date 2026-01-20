# User Management System (UMS) - Complete API Guide

## Base Configuration
```
Base URL: http://localhost:8000  (or your deployed domain)
API Prefix: /api
Authentication: Bearer Token (JWT)
Content-Type: application/json
```

---

## ROLES & ACCESS LEVELS

### User Roles Table

| Role | Level | Form Access | User Management | Admin Panel |
|------|-------|-------------|-----------------|------------|
| **admin** | 3 | All forms | Full control | Full access |
| **editor** | 2 | Assigned forms only | Cannot manage | Read/Write data |
| **viewer** | 1 | Assigned forms only | Cannot manage | Read-only |

### Detailed Permissions Matrix

| Resource | Action | Admin | Editor | Viewer |
|----------|--------|-------|--------|--------|
| **Forms** | List own | ✅ | ✅ | ✅ |
| **Forms** | List all | ✅ | ❌ | ❌ |
| **Forms** | View details | ✅ | ✅ | ✅ |
| **Forms** | Create data | ✅ | ✅ | ❌ |
| **Forms** | Edit data | ✅ | ✅ | ❌ |
| **Forms** | Delete data | ✅ | ❌ | ❌ |
| **Users** | List users | ✅ | ❌ | ❌ |
| **Users** | Create user | ✅ | ❌ | ❌ |
| **Users** | Edit user | ✅ | ❌ | ❌ |
| **Users** | Delete user | ✅ | ❌ | ❌ |
| **Forms** | Assign to users | ✅ | ❌ | ❌ |
| **Forms** | Revoke access | ✅ | ❌ | ❌ |

---

## COMPLETE API ENDPOINTS

---

## 1. AUTHENTICATION APIs

### 1.1 Login
```
Method: POST
URL: http://localhost:8000/api/auth/login
Authentication: None (Public)
```

**Request Payload:**
```json
{
  "username": "admin",
  "password": "admin123"
}
```

**Success Response (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhZG1pbiIsImV4cCI6MTYzMjU2NzQ4NH0.K8q8Z3X...",
  "token_type": "bearer"
}
```

**Error Responses:**

| Status | Error | Reason |
|--------|-------|--------|
| 401 | Incorrect username or password | Wrong credentials |
| 400 | Inactive user | User account is disabled |

---

### 1.2 Register
```
Method: POST
URL: http://localhost:8000/api/auth/register
Authentication: None (Public)
```

**Request Payload:**
```json
{
  "username": "john_doe",
  "email": "john@example.com",
  "full_name": "John Doe",
  "password": "securepass123",
  "role": "viewer"
}
```

**Success Response (200 OK):**
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

| Status | Error | Reason |
|--------|-------|--------|
| 400 | Username already registered | Duplicate username |
| 400 | Email already registered | Duplicate email |

---

### 1.3 Get Current User Info
```
Method: GET
URL: http://localhost:8000/api/auth/me
Authentication: Required (Bearer Token)
```

**Request Headers:**
```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**Success Response (200 OK):**
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

| Status | Error | Reason |
|--------|-------|--------|
| 401 | Invalid token | Token is malformed |
| 401 | Token expired | Token has expired |
| 401 | Not authenticated | No token provided |

---

## 2. USER MANAGEMENT APIs (Admin Only)

### 2.1 List All Users
```
Method: GET
URL: http://localhost:8000/api/users?skip=0&limit=100
Authentication: Required (Admin Role)
```

**Request Headers:**
```
Authorization: Bearer {admin_token}
```

**Query Parameters:**
```
skip: 0 (default) - Number of records to skip
limit: 100 (default) - Number of records to return
```

**Success Response (200 OK):**
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
  },
  {
    "id": 3,
    "username": "jane_editor",
    "email": "jane@example.com",
    "full_name": "Jane Smith",
    "role": "editor",
    "is_active": true,
    "created_at": "2026-01-19T14:00:00",
    "updated_at": "2026-01-19T14:00:00"
  }
]
```

**Error Responses:**

| Status | Error | Reason |
|--------|-------|--------|
| 403 | Operation requires admin role | User is not admin |
| 401 | Not authenticated | No token provided |

---

### 2.2 Get Specific User
```
Method: GET
URL: http://localhost:8000/api/users/{user_id}
Authentication: Required (Admin Role)
```

**Request Example:**
```
GET http://localhost:8000/api/users/2
Authorization: Bearer {admin_token}
```

**Success Response (200 OK):**
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

**Error Responses:**

| Status | Error | Reason |
|--------|-------|--------|
| 404 | User not found | User ID doesn't exist |
| 403 | Operation requires admin role | Not admin |

---

### 2.3 Update User
```
Method: PUT
URL: http://localhost:8000/api/users/{user_id}
Authentication: Required (Admin Role)
```

**Request Example:**
```
PUT http://localhost:8000/api/users/2
Authorization: Bearer {admin_token}
Content-Type: application/json
```

**Request Payload:**
```json
{
  "email": "john_new@example.com",
  "full_name": "John Updated",
  "role": "editor",
  "is_active": true
}
```

**Success Response (200 OK):**
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

**Error Responses:**

| Status | Error | Reason |
|--------|-------|--------|
| 404 | User not found | User ID doesn't exist |
| 403 | Operation requires admin role | Not admin |

---

## 3. FORM ACCESS MANAGEMENT APIs (Admin Only)

### 3.1 Assign Form to User
```
Method: POST
URL: http://localhost:8000/api/users/{user_id}/forms/{form_id}
Authentication: Required (Admin Role)
```

**Request Example:**
```
POST http://localhost:8000/api/users/2/forms/1
Authorization: Bearer {admin_token}
Content-Type: application/json
```

**Request Payload:** (Empty body or optional)
```json
{}
```

**Success Response (200 OK):**
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

| Status | Error | Reason |
|--------|-------|--------|
| 404 | User not found | User ID doesn't exist |
| 404 | Form not found | Form ID doesn't exist |
| 400 | User already has access to this form | Duplicate assignment |
| 403 | Operation requires admin role | Not admin |

---

### 3.2 Revoke Form Access
```
Method: DELETE
URL: http://localhost:8000/api/users/{user_id}/forms/{form_id}
Authentication: Required (Admin Role)
```

**Request Example:**
```
DELETE http://localhost:8000/api/users/2/forms/1
Authorization: Bearer {admin_token}
```

**Success Response (200 OK):**
```json
{
  "detail": "Form access revoked successfully"
}
```

**Error Responses:**

| Status | Error | Reason |
|--------|-------|--------|
| 404 | Form access not found | User doesn't have this form |
| 403 | Operation requires admin role | Not admin |

---

### 3.3 Get All Forms Assigned to User (Admin View)
```
Method: GET
URL: http://localhost:8000/api/users/{user_id}/forms?skip=0&limit=100
Authentication: Required (Admin Role)
```

**Request Example:**
```
GET http://localhost:8000/api/users/2/forms
Authorization: Bearer {admin_token}
```

**Query Parameters:**
```
skip: 0 (default) - Number of records to skip
limit: 100 (default) - Number of records to return
```

**Success Response (200 OK):**
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

| Status | Error | Reason |
|--------|-------|--------|
| 404 | User not found | User ID doesn't exist |
| 403 | Operation requires admin role | Not admin |

---

## 4. FORM ACCESS APIs (User Perspective)

### 4.1 Get My Forms (Current User)
```
Method: GET
URL: http://localhost:8000/api/me/forms?skip=0&limit=100&category=health
Authentication: Required (All Roles)
```

**Request Example:**
```
GET http://localhost:8000/api/me/forms
Authorization: Bearer {user_token}
```

**Query Parameters:**
```
skip: 0 (default) - Number of records to skip
limit: 100 (default) - Number of records to return
category: health (optional) - Filter by category
```

**Success Response (200 OK):**
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

**Notes:**
- **Admin users**: See all forms in system
- **Regular users**: See only assigned forms
- **Empty list**: Means no forms assigned to user

**Error Responses:**

| Status | Error | Reason |
|--------|-------|--------|
| 401 | Not authenticated | No token provided |
| 401 | Token expired | Token has expired |

---

### 4.2 List Forms (Access Controlled)
```
Method: GET
URL: http://localhost:8000/api/forms?skip=0&limit=100&category=health
Authentication: Required (All Roles)
```

**Request Example:**
```
GET http://localhost:8000/api/forms
Authorization: Bearer {user_token}
```

**Query Parameters:**
```
skip: 0 (default) - Number of records to skip
limit: 100 (default) - Number of records to return
category: health (optional) - Filter by category
```

**Success Response (200 OK):**
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
- **Admin users**: See all forms
- **Editor/Viewer users**: See only forms assigned to them

**Error Responses:**

| Status | Error | Reason |
|--------|-------|--------|
| 401 | Not authenticated | No token provided |

---

### 4.3 Get Specific Form
```
Method: GET
URL: http://localhost:8000/api/forms/{form_id}
Authentication: Required (All Roles)
```

**Request Example:**
```
GET http://localhost:8000/api/forms/1
Authorization: Bearer {user_token}
```

**Success Response (200 OK):**
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

| Status | Error | Reason |
|--------|-------|--------|
| 404 | Form not found | Form ID doesn't exist |
| 403 | Access denied to this form | Non-admin user doesn't have access |
| 401 | Not authenticated | No token provided |

---

## 5. CURL COMMAND EXAMPLES

### Login
```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "admin123"
  }'
```

### Get Current User
```bash
curl -X GET http://localhost:8000/api/auth/me \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### List All Users (Admin)
```bash
curl -X GET http://localhost:8000/api/users \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN"
```

### Update User (Admin)
```bash
curl -X PUT http://localhost:8000/api/users/2 \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "role": "editor",
    "full_name": "John Updated"
  }'
```

### Assign Form to User (Admin)
```bash
curl -X POST http://localhost:8000/api/users/2/forms/1 \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN"
```

### Revoke Form Access (Admin)
```bash
curl -X DELETE http://localhost:8000/api/users/2/forms/1 \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN"
```

### Get My Forms
```bash
curl -X GET http://localhost:8000/api/me/forms \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Get All Forms
```bash
curl -X GET http://localhost:8000/api/forms \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Get Specific Form
```bash
curl -X GET http://localhost:8000/api/forms/1 \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

## 6. JAVASCRIPT/FETCH EXAMPLES

### Login & Store Token
```javascript
async function login(username, password) {
  const response = await fetch('http://localhost:8000/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password })
  });
  
  const data = await response.json();
  if (response.ok) {
    localStorage.setItem('token', data.access_token);
    return data.access_token;
  }
  throw new Error(data.detail || 'Login failed');
}
```

### Get Current User
```javascript
async function getCurrentUser() {
  const token = localStorage.getItem('token');
  const response = await fetch('http://localhost:8000/api/auth/me', {
    headers: { 'Authorization': `Bearer ${token}` }
  });
  return await response.json();
}
```

### Get My Forms (Dropdown)
```javascript
async function getMyForms() {
  const token = localStorage.getItem('token');
  const response = await fetch('http://localhost:8000/api/me/forms', {
    headers: { 'Authorization': `Bearer ${token}` }
  });
  
  const forms = await response.json();
  
  // Populate dropdown
  const dropdown = document.getElementById('form-dropdown');
  dropdown.innerHTML = '';
  forms.forEach(form => {
    const option = document.createElement('option');
    option.value = form.id;
    option.textContent = form.title;
    dropdown.appendChild(option);
  });
}
```

### Assign Multiple Forms (Admin)
```javascript
async function assignFormsToUser(userId, formIds) {
  const token = localStorage.getItem('token');
  
  for (const formId of formIds) {
    const response = await fetch(
      `http://localhost:8000/api/users/${userId}/forms/${formId}`,
      {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
      }
    );
    
    if (!response.ok) {
      console.error(`Failed to assign form ${formId}`);
    }
  }
}

// Usage
assignFormsToUser(2, [1, 2, 3]);
```

### Get User's Forms (Admin)
```javascript
async function getUserForms(userId) {
  const token = localStorage.getItem('token');
  const response = await fetch(
    `http://localhost:8000/api/users/${userId}/forms`,
    {
      headers: { 'Authorization': `Bearer ${token}` }
    }
  );
  return await response.json();
}
```

---

## 7. HTTP STATUS CODES REFERENCE

| Code | Status | Meaning |
|------|--------|---------|
| 200 | OK | Request successful |
| 201 | Created | Resource created successfully |
| 400 | Bad Request | Invalid request data |
| 401 | Unauthorized | Missing/invalid authentication |
| 403 | Forbidden | No permission for this action |
| 404 | Not Found | Resource doesn't exist |
| 500 | Internal Error | Server error |

---

## 8. TOKEN MANAGEMENT

### Token Structure
JWT Token contains:
- `sub`: Username
- `exp`: Expiration time (timestamp)

### Token Expiration
- Default: 30-60 minutes (configurable)
- After expiration: Re-login required

### Best Practices
- Store token in `localStorage` or `sessionStorage`
- Always include in `Authorization: Bearer {token}` header
- Never expose in URLs
- Refresh token when expired

---

## 9. ROLE-BASED ACCESS SUMMARY

### Admin Role
- Full access to all features
- Can manage users
- Can assign/revoke forms
- Sees all forms and data

### Editor Role
- Can access assigned forms only
- Can create/edit form submissions
- Cannot delete submissions
- Cannot manage users

### Viewer Role
- Can access assigned forms only
- Read-only access
- Cannot create/edit data
- Cannot delete data

---

## 10. TYPICAL WORKFLOW

### User Registration & Setup (Admin)
```
1. Register user: POST /api/auth/register
2. Assign forms: POST /api/users/{id}/forms/{form_id}
3. Verify assignment: GET /api/users/{id}/forms
```

### User Login & Access Forms
```
1. Login: POST /api/auth/login
2. Get current info: GET /api/auth/me
3. Get my forms: GET /api/me/forms (displays in dropdown)
4. View form details: GET /api/forms/{form_id}
5. Access form data: GET /api/forms/{form_id}/submissions
```

