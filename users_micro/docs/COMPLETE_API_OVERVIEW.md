# BrainInk Backend - Complete API Overview

## 🏗️ Architecture Overview

Your BrainInk backend is a FastAPI-based school management system with three main modules:

1. **Authentication Module** (`auth.py`) - User registration, login, JWT tokens
2. **Study Area Module** (`study_area.py`) - Schools, users, subjects, roles management  
3. **Grades Module** (`grades.py`) - Assignments and grading system

## 📊 Database Models

### Core Entities:
- **Users** - Basic user accounts (students, teachers, principals, admins)
- **Schools** - Educational institutions with principals
- **Roles** - User permissions (normal_user, student, teacher, principal, admin)
- **Access Codes** - Email-specific invitation codes for joining schools
- **Subjects** - Courses within schools
- **Assignments** - Tasks given by teachers
- **Grades** - Student performance on assignments

### Key Relationships:
- Schools have one Principal (User with principal role)
- Users can have multiple roles (many-to-many)
- Students/Teachers belong to Schools
- Subjects have multiple Teachers and Students
- Assignments belong to Subjects and have Grades

## 🔐 Authentication System

### Base URL: `http://localhost:8000`

### 1. User Registration
```http
POST /register
```
**Body:**
```json
{
  "username": "john_doe",
  "email": "john@example.com", 
  "fname": "John",
  "lname": "Doe",
  "password": "secure_password"
}
```
**Response:** User object with auto-assigned `normal_user` role

### 2. User Login
```http
POST /login
```
**Body:**
```json
{
  "username": "john_doe",
  "password": "secure_password"
}
```
**Response:**
```json
{
  "access_token": "jwt_token_here",
  "token_type": "bearer",
  "user_info": {
    "id": 1,
    "username": "john_doe",
    "email": "john@example.com"
  }
}
```

### 3. Get Current User Info
```http
GET /users/me
```
**Headers:** `Authorization: Bearer <token>`
**Response:** Current user details with roles

---

## 🏫 Study Area Module 

### Base URL: `http://localhost:8000/study-area`

## School Management Workflow

### 1. Create School Request (Any User)
```http
POST /school-requests/create
```
**Headers:** `Authorization: Bearer <token>`
**Body:**
```json
{
  "school_name": "Green Springs High School",
  "school_address": "123 Education St, City, State"
}
```
**Purpose:** Any authenticated user can request to become a principal

### 2. Review School Requests (Admins Only)
```http
GET /school-requests/pending
```
**Headers:** `Authorization: Bearer <admin_token>`
**Response:** List of pending school requests with principal info

```http
PUT /school-requests/{request_id}/review
```
**Body:**
```json
{
  "status": "approved",  // or "rejected"
  "admin_notes": "School approved - good application"
}
```
**Effect:** If approved, creates school and assigns principal role

### 3. Get My School (Principals)
```http
GET /schools/my-school
```
**Headers:** `Authorization: Bearer <principal_token>`
**Response:** School details with statistics (student count, teacher count, etc.)

---

## Access Code System (Core Feature)

### 4. Generate Access Codes (Principals Only)
```http
POST /access-codes/generate
```
**Headers:** `Authorization: Bearer <principal_token>`
**Body:**
```json
{
  "school_id": 1,
  "code_type": "student",  // or "teacher"
  "email": "student@example.com"
}
```
**How it Works:**
- Principal generates email-specific codes
- Code automatically assigns role (student/teacher) when used
- If user exists, role is assigned immediately
- Codes remain active for reuse

### 5. Join School as Student
```http
POST /join-school/student
```
**Headers:** `Authorization: Bearer <student_token>`
**Body:**
```json
{
  "school_name": "Green Springs High School",
  "email": "student@example.com",
  "access_code": "ABCD1234"
}
```
**Validation:**
- Email must match current user's email
- Access code must be for students and assigned to that email
- Creates Student record in database

### 6. Join School as Teacher
```http
POST /join-school/teacher
```
**Same format as student, but creates Teacher record**

---

## Role Management

### 7. Assign Roles (Admins Only)
```http
POST /roles/assign
```
**Body:**
```json
{
  "user_id": 5,
  "role_name": "admin"
}
```

### 8. Get User Roles
```http
GET /users/{user_id}/roles
```
**Response:**
```json
{
  "user_id": 5,
  "username": "john_doe",
  "roles": ["student", "normal_user"]
}
```

---

## Subject Management

### 9. Create Subject (Principals)
```http
POST /subjects/create
```
**Body:**
```json
{
  "name": "Mathematics",
  "description": "Advanced Math course",
  "school_id": 1
}
```

### 10. Assign Teacher to Subject (Principals)
```http
POST /subjects/assign-teacher
```
**Body:**
```json
{
  "subject_id": 1,
  "teacher_id": 3
}
```

### 11. Add Student to Subject (Teachers)
```http
POST /subjects/add-student
```
**Body:**
```json
{
  "subject_id": 1,
  "student_id": 5
}
```

### 12. Get Subject Details
```http
GET /subjects/{subject_id}
```
**Response:** Subject with all teachers and students

---

## User Status & Analytics

### 13. Get User Status (Any User)
```http
GET /user/status
```
**Response:**
```json
{
  "user_info": {
    "id": 1,
    "roles": ["student", "normal_user"]
  },
  "school_request_status": {
    "has_request": false,
    "status": null
  },
  "schools": {
    "as_principal": {"school_id": null},
    "as_student": [{"school_id": 1, "school_name": "Green Springs"}],
    "as_teacher": []
  },
  "available_actions": [
    {
      "action": "create_school_request",
      "description": "Request to become a principal",
      "endpoint": "/school-requests/create"
    }
  ]
}
```

### 14. School Analytics (Principals)

**School Overview:**
```http
GET /analytics/school-overview
```
**Response:** Comprehensive school statistics with overall averages and completion rates

**Subject Performance:**
```http
GET /analytics/subject-performance
```
**Response:** Performance metrics by subject with trends

**Grade Distribution:**
```http
GET /analytics/grade-distribution
```
**Response:** Grade distribution percentages (A/B/C/D/F)

**Completion Rate:**
```http
GET /analytics/completion-rate
```
**Response:** Assignment completion statistics

**Daily Active Students:**
```http
GET /analytics/daily-active
```
**Response:** Daily active student counts

**Session Time:**
```http
GET /analytics/session-time
```
**Response:** Average session time metrics

---

## 📝 Grades Module

### Base URL: `http://localhost:8000/grades`

## Assignment Management

### 1. Create Assignment (Teachers)
```http
POST /assignments/create
```
**Headers:** `Authorization: Bearer <teacher_token>`
**Body:**
```json
{
  "title": "Chapter 5 Quiz",
  "description": "Quiz on algebra fundamentals",
  "subtopic": "Quadratic Equations",
  "max_points": 100,
  "due_date": "2025-07-15T23:59:59",
  "subject_id": 1
}
```
**Validation:** Teacher must be assigned to the subject

### 2. Get Teacher's Assignments
```http
GET /assignments/my-assignments
```
**Response:** All assignments created by the teacher with grade statistics

### 3. Get Subject Assignments
```http
GET /assignments/subject/{subject_id}
```
**Access:** Teachers assigned to subject or principals

### 4. Update Assignment
```http
PUT /assignments/{assignment_id}
```
**Body:** Partial update (any field from AssignmentUpdate schema)

## Grading System

### 5. Create Single Grade (Teachers)
```http
POST /grades/create
```
**Body:**
```json
{
  "assignment_id": 1,
  "student_id": 3,
  "points_earned": 85,
  "feedback": "Good work, but review problem #5"
}
```

### 6. Bulk Grade Assignment (Teachers)
```http
POST /grades/bulk-create
```
**Body:**
```json
{
  "assignment_id": 1,
  "grades": [
    {
      "student_id": 3,
      "points_earned": 85,
      "feedback": "Great job!"
    },
    {
      "student_id": 4,
      "points_earned": 92,
      "feedback": "Excellent work!"
    }
  ]
}
```

### 7. Get Student Grades (Students)
```http
GET /grades/my-grades
```
**Response:** All grades for the current student organized by subject

### 8. Get Subject Grade Summary (Teachers/Principals)
```http
GET /grades/subject/{subject_id}/summary
```
**Response:** Complete grading overview for a subject

---

## 🔄 Frontend Integration Guidelines

### Authentication Flow:
1. **Registration/Login** → Store JWT token
2. **Get User Status** → Determine user's current state and available actions
3. **Route to appropriate dashboard** based on roles

### Role-Based UI:
```javascript
// Example role checking
const userRoles = userData.roles;

if (userRoles.includes('principal')) {
  // Show principal dashboard
  // - School management
  // - Access code generation
  // - Analytics
} else if (userRoles.includes('teacher')) {
  // Show teacher dashboard  
  // - My subjects
  // - Create assignments
  // - Grade students
} else if (userRoles.includes('student')) {
  // Show student dashboard
  // - My subjects
  // - View assignments
  // - Check grades
} else {
  // Show options to join school or request principal status
}
```

### Error Handling:
```javascript
// Common HTTP status codes:
// 200 - Success
// 400 - Bad Request (validation errors)
// 401 - Unauthorized (invalid/missing token)
// 403 - Forbidden (insufficient role permissions)
// 404 - Not Found
// 500 - Server Error
```

### Required Headers:
```javascript
const headers = {
  'Authorization': `Bearer ${token}`,
  'Content-Type': 'application/json'
}
```

### School Workflow for Frontend:
1. **New User:** Register → Login → Join school with access code OR request to create school
2. **Principal:** Create school → Generate access codes → Manage subjects → Assign teachers
3. **Teacher:** Join school → Get assigned to subjects → Create assignments → Grade students  
4. **Student:** Join school → Get added to subjects → View assignments → Check grades

### Key Frontend Components Needed:
- **Login/Register forms**
- **Role-based dashboards**
- **Access code input form**
- **School request form**
- **Subject management interface**
- **Assignment creation/grading interface**
- **Grade viewing interface**

## 🚀 Quick Start for Frontend

1. **Server URL:** `http://localhost:8000`
2. **Swagger Docs:** `http://localhost:8000/docs`
3. **Health Check:** `GET /health`

## 🔧 Testing the API

Use the test files provided:
- `test_new_access_codes.py` - Test access code system
- `test_multiple_roles.py` - Test role assignments
- `test_study_area.py` - Test school and subject management

The backend is designed to handle the complete school management workflow from user registration to grade reporting. Each endpoint has proper validation, error handling, and role-based access control.
