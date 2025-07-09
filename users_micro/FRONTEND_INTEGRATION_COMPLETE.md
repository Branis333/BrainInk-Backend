# BrainInk Backend - Complete Frontend Integration Guide

## Overview

The BrainInk backend has been completely refactored to remove the### 5. Get Available Schools (Any User)
```http
GET /study-area/schools/available
```
**Headers:** `Authorization: Bearer <token>`
**Response:**
```json
[
  {
    "id": 1,
    "name": "Springfield Elementary",
    "address": "123 Main St, Springfield",
    "principal_name": "John Smith",
    "total_students": 300,
    "total_teachers": 15,
    "is_accepting_applications": true,
    "created_date": "2024-01-15T10:30:00",
    "user_role": "principal"
  },
  {
    "id": 2,
    "name": "Riverside High School", 
    "address": "456 Oak Ave, Riverside",
    "principal_name": "Jane Doe",
    "total_students": 800,
    "total_teachers": 45,
    "is_accepting_applications": true,
    "created_date": "2024-01-10T09:00:00",
    "user_role": "teacher"
  }
]
```
**Note:** `user_role` indicates the current user's role in each school (null if not a member)cy access code system and implement a modern, email-based invitation system. This guide provides comprehensive documentation for frontend developers to integrate with the new backend APIs.

## Key Changes from Legacy System

### ❌ Removed (Access Code System)
- `/study-area/join-school-by-code` endpoint
- `/study-area/generate-access-code` endpoint
- `/study-area/verify-access-code` endpoint
- All access code models and schemas
- Manual code generation and sharing workflow

### ✅ New (Email Invitation System)
- Email-based invitations managed by principals
- Automatic role assignment upon joining
- Invitation tracking and management
- Bulk invitation support
- Modern, secure workflow

---

## API Base URL
```
http://localhost:8000
```

## Authentication

All protected endpoints require a JWT token in the Authorization header:
```
Authorization: Bearer <your_jwt_token>
```

---

## 🔐 Authentication Endpoints

### 1. User Registration
```http
POST /register
```
**Body:**
```json
{
  "first_name": "John",
  "last_name": "Doe", 
  "email": "john.doe@example.com",
  "password": "securePassword123",
  "phone_number": "+1234567890"
}
```

### 2. User Login
```http
POST /login
```
**Body:**
```json
{
  "email": "john.doe@example.com",
  "password": "securePassword123"
}
```
**Response:**
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "token_type": "bearer",
  "user_id": 123,
  "email": "john.doe@example.com"
}
```

### 3. Principal Login (Separate Endpoint)
```http
POST /principal-login
```
**Body:**
```json
{
  "email": "principal@school.com",
  "password": "principalPassword123"
}
```

### 4. Teacher Login (Separate Endpoint)
```http
POST /teacher-login
```
**Body:**
```json
{
  "email": "teacher@school.com", 
  "password": "teacherPassword123"
}
```

---

## 🏫 School Management Endpoints

### 1. Create School (Principals Only)
```http
POST /study-area/create-school
```
**Headers:** `Authorization: Bearer <token>`
**Body:**
```json
{
  "name": "Springfield Elementary",
  "description": "A great school for learning",
  "address": "123 Main St, Springfield",
  "phone_number": "+1234567890"
}
```

### 2. Get School Details
```http
GET /study-area/school/{school_id}
```
**Headers:** `Authorization: Bearer <token>`

### 3. Update School (Principals Only)
```http
PUT /study-area/school/{school_id}
```
**Headers:** `Authorization: Bearer <token>`
**Body:**
```json
{
  "name": "Updated School Name",
  "description": "Updated description",
  "address": "New address",
  "phone_number": "+1987654321"
}
```

### 4. Get Schools by Principal
```http
GET /study-area/schools/by-principal/{principal_id}
```
**Headers:** `Authorization: Bearer <token>`

### 6. Get School Analytics
```http
GET /study-area/school/{school_id}/analytics
```
**Headers:** `Authorization: Bearer <token>`
**Response:**
```json
{
  "school_id": 1,
  "school_name": "Springfield Elementary",
  "total_teachers": 15,
  "total_students": 300,
  "total_subjects": 8,
  "total_assignments": 45,
  "average_grade": 85.5
}
```

---

## 📧 School Invitation System (NEW)

### 1. Create Single Invitation (Principals Only)
```http
POST /study-area/invitations/create
```
**Headers:** `Authorization: Bearer <token>`
**Body:**
```json
{
  "email": "teacher@example.com",
  "invitation_type": "teacher",
  "school_id": 1
}
```
**Response:**
```json
{
  "id": 123,
  "email": "teacher@example.com",
  "invitation_type": "teacher",
  "school_id": 1,
  "school_name": "Springfield Elementary",
  "invited_by": 456,
  "invited_date": "2024-01-15T10:30:00",
  "is_used": false,
  "used_date": null,
  "is_active": true
}
```

### 2. Create Bulk Invitations (Principals Only)
```http
POST /study-area/invitations/bulk-create
```
**Headers:** `Authorization: Bearer <token>`
**Body:**
```json
{
  "emails": [
    "teacher1@example.com",
    "teacher2@example.com", 
    "student1@example.com"
  ],
  "invitation_type": "teacher",
  "school_id": 1
}
```
**Response:**
```json
{
  "successful_invitations": [
    {
      "id": 124,
      "email": "teacher1@example.com",
      "invitation_type": "teacher",
      "school_id": 1,
      "school_name": "Springfield Elementary",
      "invited_by": 456,
      "invited_date": "2024-01-15T10:30:00",
      "is_used": false,
      "used_date": null,
      "is_active": true
    }
  ],
  "failed_emails": ["teacher2@example.com"],
  "errors": ["teacher2@example.com: Already has active invitation"],
  "total_sent": 1,
  "total_failed": 1
}
```

### 3. Get School Invitations (Principals Only)
```http
GET /study-area/invitations/school/{school_id}?invitation_type=teacher&status=active
```
**Headers:** `Authorization: Bearer <token>`
**Query Parameters:**
- `invitation_type` (optional): "teacher" or "student"
- `status` (optional): "active", "used", "all"

### 4. Cancel Invitation (Principals Only)
```http
DELETE /study-area/invitations/{invitation_id}
```
**Headers:** `Authorization: Bearer <token>`

### 5. Join School by Email (Teachers/Students)
```http
POST /study-area/join-school-by-email
```
**Headers:** `Authorization: Bearer <token>`
**Body:**
```json
{
  "email": "teacher@example.com"
}
```
**Response:**
```json
{
  "message": "Successfully joined Springfield Elementary as teacher",
  "school_id": 1,
  "school_name": "Springfield Elementary",
  "role_assigned": "teacher",
  "teacher_id": 789,
  "student_id": null
}
```

### 6. Check Available Invitations for User
```http
GET /study-area/invitations/available
```
**Headers:** `Authorization: Bearer <token>`
**Response:**
```json
[
  {
    "id": 123,
    "school_name": "Springfield Elementary", 
    "invitation_type": "teacher",
    "invited_date": "2024-01-15T10:30:00"
  }
]
```

---

## 👥 Role Management

### 1. Get User Roles
```http
GET /study-area/user/{user_id}/roles
```
**Headers:** `Authorization: Bearer <token>`

### 2. Assign Role to User (System Use)
```http
POST /study-area/assign-role
```
**Headers:** `Authorization: Bearer <token>`
**Body:**
```json
{
  "user_id": 123,
  "role": "teacher",
  "school_id": 1
}
```

---

## 📚 Academic Management

### 1. Create Subject (Teachers Only)
```http
POST /study-area/academic/subjects
```
**Headers:** `Authorization: Bearer <token>`
**Body:**
```json
{
  "name": "Mathematics",
  "description": "Advanced Mathematics Course",
  "school_id": 1
}
```

### 2. Get School Subjects
```http
GET /study-area/academic/subjects/school/{school_id}
```
**Headers:** `Authorization: Bearer <token>`

### 3. Get Teacher Subjects
```http
GET /study-area/academic/subjects/teacher/{teacher_id}
```
**Headers:** `Authorization: Bearer <token>`

### 4. Update Subject
```http
PUT /study-area/academic/subjects/{subject_id}
```
**Headers:** `Authorization: Bearer <token>`
**Body:**
```json
{
  "name": "Advanced Mathematics",
  "description": "Updated description"
}
```

### 5. Delete Subject
```http
DELETE /study-area/academic/subjects/{subject_id}
```
**Headers:** `Authorization: Bearer <token>`

---

## 📝 Assignments & Grades

### 1. Create Assignment (Teachers Only)
```http
POST /study-area/grades/assignments
```
**Headers:** `Authorization: Bearer <token>`
**Body:**
```json
{
  "title": "Math Quiz 1",
  "description": "Chapter 1-3 quiz",
  "due_date": "2024-02-01T23:59:59",
  "total_points": 100,
  "subject_id": 1
}
```

### 2. Get Subject Assignments
```http
GET /study-area/grades/assignments/subject/{subject_id}
```
**Headers:** `Authorization: Bearer <token>`

### 3. Get Teacher Assignments
```http
GET /study-area/grades/assignments/teacher/{teacher_id}
```
**Headers:** `Authorization: Bearer <token>`

### 4. Submit Grade (Teachers Only)
```http
POST /study-area/grades/grades
```
**Headers:** `Authorization: Bearer <token>`
**Body:**
```json
{
  "assignment_id": 1,
  "student_id": 123,
  "points_earned": 85,
  "feedback": "Good work, minor errors in problem 3"
}
```

### 5. Get Student Grades
```http
GET /study-area/grades/grades/student/{student_id}
```
**Headers:** `Authorization: Bearer <token>`

### 6. Get Assignment Grades
```http
GET /study-area/grades/grades/assignment/{assignment_id}
```
**Headers:** `Authorization: Bearer <token>`

---

## 🎯 Frontend Integration Workflow

### For Principals

1. **Login:** Use `/principal-login` endpoint
2. **Create School:** Use `/study-area/create-school`
3. **Invite Teachers/Students:** 
   - Single: `/study-area/invitations/create`
   - Bulk: `/study-area/invitations/bulk-create`
4. **Manage Invitations:** 
   - View: `/study-area/invitations/school/{school_id}`
   - Cancel: DELETE `/study-area/invitations/{invitation_id}`
5. **View Analytics:** `/study-area/school/{school_id}/analytics`

### For Teachers

1. **Login:** Use `/teacher-login` endpoint
2. **Check Invitations:** `/study-area/invitations/available`
3. **Join School:** `/study-area/join-school-by-email`
4. **Create Subjects:** `/study-area/academic/subjects`
5. **Create Assignments:** `/study-area/grades/assignments`
6. **Submit Grades:** `/study-area/grades/grades`

### For Students

1. **Login:** Use `/login` endpoint
2. **Check Invitations:** `/study-area/invitations/available`
3. **Join School:** `/study-area/join-school-by-email`
4. **View Assignments:** `/study-area/grades/assignments/subject/{subject_id}`
5. **View Grades:** `/study-area/grades/grades/student/{student_id}`

---

## 🔒 Permission Matrix

| Endpoint | Principal | Teacher | Student |
|----------|-----------|---------|---------|
| Create School | ✅ | ❌ | ❌ |
| Create Invitations | ✅ | ❌ | ❌ |
| Join School | ❌ | ✅ | ✅ |
| Create Subjects | ❌ | ✅ | ❌ |
| Create Assignments | ❌ | ✅ | ❌ |
| Submit Grades | ❌ | ✅ | ❌ |
| View Grades | ✅ | ✅ | ✅ (own only) |

---

## 🚨 Error Handling

### Common Error Responses

**400 Bad Request:**
```json
{
  "detail": "Active invitation already exists for teacher@example.com as teacher"
}
```

**401 Unauthorized:**
```json
{
  "detail": "Invalid credentials"
}
```

**403 Forbidden:**
```json
{
  "detail": "You can only create invitations for schools you manage"
}
```

**404 Not Found:**
```json
{
  "detail": "School not found"
}
```

**422 Validation Error:**
```json
{
  "detail": [
    {
      "loc": ["body", "email"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

---

## 📱 Frontend Implementation Examples

### React/TypeScript Example

```typescript
// API Client
class BrainInkAPI {
  private baseURL = 'http://localhost:8000';
  private token: string | null = null;

  setToken(token: string) {
    this.token = token;
  }

  private async request(endpoint: string, options: RequestInit = {}) {
    const headers = {
      'Content-Type': 'application/json',
      ...(this.token && { Authorization: `Bearer ${this.token}` }),
      ...options.headers,
    };

    const response = await fetch(`${this.baseURL}${endpoint}`, {
      ...options,
      headers,
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return response.json();
  }

  // Auth methods
  async login(email: string, password: string) {
    return this.request('/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
  }

  async principalLogin(email: string, password: string) {
    return this.request('/principal-login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
  }

  // Invitation methods
  async createInvitation(email: string, invitationType: 'teacher' | 'student', schoolId: number) {
    return this.request('/study-area/invitations/create', {
      method: 'POST',
      body: JSON.stringify({
        email,
        invitation_type: invitationType,
        school_id: schoolId,
      }),
    });
  }

  async joinSchoolByEmail(email: string) {
    return this.request('/study-area/join-school-by-email', {
      method: 'POST',
      body: JSON.stringify({ email }),
    });
  }

  async getAvailableInvitations() {
    return this.request('/study-area/invitations/available');
  }

  // School methods
  async createSchool(name: string, description: string, address: string, phoneNumber: string) {
    return this.request('/study-area/create-school', {
      method: 'POST',
      body: JSON.stringify({
        name,
        description,
        address,
        phone_number: phoneNumber,
      }),
    });
  }

  async getSchoolAnalytics(schoolId: number) {
    return this.request(`/study-area/school/${schoolId}/analytics`);
  }
}

// Usage in React component
const api = new BrainInkAPI();

const LoginComponent = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [userType, setUserType] = useState<'student' | 'teacher' | 'principal'>('student');

  const handleLogin = async () => {
    try {
      let response;
      if (userType === 'principal') {
        response = await api.principalLogin(email, password);
      } else if (userType === 'teacher') {
        response = await api.teacherLogin(email, password);
      } else {
        response = await api.login(email, password);
      }
      
      api.setToken(response.access_token);
      // Handle successful login
    } catch (error) {
      console.error('Login failed:', error);
    }
  };

  return (
    <div>
      <select value={userType} onChange={(e) => setUserType(e.target.value)}>
        <option value="student">Student</option>
        <option value="teacher">Teacher</option>
        <option value="principal">Principal</option>
      </select>
      <input
        type="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        placeholder="Email"
      />
      <input
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        placeholder="Password"
      />
      <button onClick={handleLogin}>Login</button>
    </div>
  );
};
```

---

## 🔄 Migration from Access Codes

### What to Update in Frontend

1. **Remove Access Code Components:**
   - Delete any UI for entering/generating access codes
   - Remove access code validation logic
   - Remove manual code sharing features

2. **Add Invitation Management:**
   - Principal dashboard for sending invitations
   - Bulk invitation upload functionality
   - Invitation status tracking
   - Email-based joining workflow

3. **Update User Flows:**
   - Replace "Enter Access Code" with "Check Your Email for Invitations"
   - Add invitation acceptance workflow
   - Update onboarding to show available invitations

4. **Update API Calls:**
   - Replace `/join-school-by-code` with `/join-school-by-email`
   - Replace access code endpoints with invitation endpoints
   - Update error handling for new error messages

---

## ✅ Testing Checklist

### Principal Workflow
- [ ] Principal can login successfully
- [ ] Principal can create a school
- [ ] Principal can send single invitations
- [ ] Principal can send bulk invitations
- [ ] Principal can view all school invitations
- [ ] Principal can cancel invitations
- [ ] Principal can view school analytics

### Teacher Workflow
- [ ] Teacher can login successfully
- [ ] Teacher can see available invitations
- [ ] Teacher can join school via email
- [ ] Teacher can create subjects
- [ ] Teacher can create assignments
- [ ] Teacher can submit grades

### Student Workflow
- [ ] Student can login successfully
- [ ] Student can see available invitations
- [ ] Student can join school via email
- [ ] Student can view assignments
- [ ] Student can view grades

### Error Handling
- [ ] Proper error messages for invalid credentials
- [ ] Proper error messages for permission denied
- [ ] Proper error messages for duplicate invitations
- [ ] Proper error messages for non-existent resources

---

## 📞 Support

For questions about the API integration or if you encounter any issues, please refer to:

- `API_DOCUMENTATION.md` - Detailed endpoint documentation
- `SYSTEM_WORKFLOW_ARCHITECTURE.md` - System architecture overview
- Backend logs for debugging information

The new invitation system provides a more secure, manageable, and user-friendly way to onboard teachers and students to schools. The email-based workflow eliminates the need for manual code sharing and provides better tracking and management capabilities for principals.
