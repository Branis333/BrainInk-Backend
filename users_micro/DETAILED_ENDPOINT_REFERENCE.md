# BrainInk API - Detailed Endpoint Reference

## 🔐 Authentication Endpoints

### POST /register
**Purpose:** Create a new user account
**Authentication:** None required
**Request Body:**
```json
{
  "username": "john_doe",
  "email": "john@example.com",
  "fname": "John", 
  "lname": "Doe",
  "password": "secure_password123"
}
```
**Success Response (201):**
```json
{
  "id": 1,
  "username": "john_doe",
  "email": "john@example.com",
  "fname": "John",
  "lname": "Doe",
  "is_active": true,
  "created_at": "2025-07-02T10:30:00Z",
  "roles": ["normal_user"]
}
```

### POST /login
**Purpose:** Authenticate user and get JWT token
**Authentication:** None required
**Request Body:**
```json
{
  "username": "john_doe",
  "password": "secure_password123"
}
```
**Success Response (200):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user_info": {
    "id": 1,
    "username": "john_doe",
    "email": "john@example.com"
  }
}
```

### GET /users/me
**Purpose:** Get current authenticated user info
**Authentication:** Bearer token required
**Success Response (200):**
```json
{
  "id": 1,
  "username": "john_doe",
  "email": "john@example.com",
  "fname": "John",
  "lname": "Doe",
  "is_active": true,
  "created_at": "2025-07-02T10:30:00Z",
  "roles": ["normal_user", "student"]
}
```

---

## 🏫 Study Area Endpoints

### School Requests

#### POST /study-area/school-requests/create
**Purpose:** Request to become a principal and create a school
**Authentication:** Any authenticated user
**Request Body:**
```json
{
  "school_name": "Green Springs High School",
  "school_address": "123 Education Street, Springfield, IL 62701"
}
```
**Success Response (200):**
```json
{
  "id": 1,
  "school_name": "Green Springs High School", 
  "school_address": "123 Education Street, Springfield, IL 62701",
  "principal_id": 1,
  "request_date": "2025-07-02T10:30:00Z",
  "status": "pending",
  "admin_notes": null,
  "reviewed_by": null,
  "reviewed_date": null
}
```

#### GET /study-area/school-requests/pending
**Purpose:** Get all pending school requests (admin only)
**Authentication:** Admin role required
**Success Response (200):**
```json
[
  {
    "id": 1,
    "school_name": "Green Springs High School",
    "school_address": "123 Education Street, Springfield, IL 62701", 
    "principal_id": 1,
    "request_date": "2025-07-02T10:30:00Z",
    "status": "pending",
    "admin_notes": null,
    "reviewed_by": null,
    "reviewed_date": null,
    "principal_name": "John Doe",
    "principal_email": "john@example.com"
  }
]
```

#### PUT /study-area/school-requests/{request_id}/review
**Purpose:** Approve or reject school request (admin only)
**Authentication:** Admin role required
**Request Body:**
```json
{
  "status": "approved",
  "admin_notes": "Application looks good, school approved"
}
```
**Success Response (200):**
```json
{
  "id": 1,
  "school_name": "Green Springs High School",
  "school_address": "123 Education Street, Springfield, IL 62701",
  "principal_id": 1,
  "request_date": "2025-07-02T10:30:00Z", 
  "status": "approved",
  "admin_notes": "Application looks good, school approved",
  "reviewed_by": 2,
  "reviewed_date": "2025-07-02T11:00:00Z"
}
```

### School Management

#### GET /study-area/schools/my-school
**Purpose:** Get school managed by current principal with stats
**Authentication:** Principal role required
**Success Response (200):**
```json
{
  "id": 1,
  "name": "Green Springs High School",
  "address": "123 Education Street, Springfield, IL 62701",
  "principal_id": 1,
  "created_date": "2025-07-02T11:00:00Z",
  "is_active": true,
  "total_students": 150,
  "total_teachers": 12,
  "total_classrooms": 8,
  "active_access_codes": 5
}
```

### Access Code Management

#### POST /study-area/access-codes/generate
**Purpose:** Generate access code for specific email (principal only)
**Authentication:** Principal role required
**Request Body:**
```json
{
  "school_id": 1,
  "code_type": "student",
  "email": "student@example.com"
}
```
**Success Response (200):**
```json
{
  "id": 1,
  "code": "ABCD1234",
  "code_type": "student",
  "school_id": 1,
  "email": "student@example.com",
  "created_date": "2025-07-02T12:00:00Z",
  "is_active": true
}
```

#### GET /study-area/access-codes/my-school
**Purpose:** Get all access codes for principal's school
**Authentication:** Principal role required
**Success Response (200):**
```json
[
  {
    "id": 1,
    "code": "ABCD1234",
    "code_type": "student",
    "school_id": 1,
    "email": "student@example.com",
    "created_date": "2025-07-02T12:00:00Z",
    "is_active": true
  },
  {
    "id": 2,
    "code": "EFGH5678",
    "code_type": "teacher", 
    "school_id": 1,
    "email": "teacher@example.com",
    "created_date": "2025-07-02T12:15:00Z",
    "is_active": true
  }
]
```

### Joining Schools

#### POST /study-area/join-school/student
**Purpose:** Join school as student using access code
**Authentication:** Any authenticated user
**Request Body:**
```json
{
  "school_name": "Green Springs High School",
  "email": "student@example.com",
  "access_code": "ABCD1234"
}
```
**Success Response (200):**
```json
{
  "id": 1,
  "user_id": 3,
  "school_id": 1,
  "classroom_id": null
}
```

#### POST /study-area/join-school/teacher
**Purpose:** Join school as teacher using access code
**Authentication:** Any authenticated user
**Request Body:**
```json
{
  "school_name": "Green Springs High School",
  "email": "teacher@example.com", 
  "access_code": "EFGH5678"
}
```
**Success Response (200):**
```json
{
  "id": 1,
  "user_id": 4,
  "school_id": 1,
  "classroom_id": null
}
```

### Subject Management

#### POST /study-area/subjects/create
**Purpose:** Create a new subject (principal only)
**Authentication:** Principal role required
**Request Body:**
```json
{
  "name": "Mathematics",
  "description": "Advanced Mathematics course covering algebra and calculus",
  "school_id": 1
}
```
**Success Response (200):**
```json
{
  "id": 1,
  "name": "Mathematics",
  "description": "Advanced Mathematics course covering algebra and calculus",
  "school_id": 1,
  "created_by": 1,
  "created_date": "2025-07-02T13:00:00Z",
  "is_active": true
}
```

#### GET /study-area/subjects/my-school
**Purpose:** Get all subjects for principal's school
**Authentication:** Principal role required
**Success Response (200):**
```json
[
  {
    "id": 1,
    "name": "Mathematics",
    "description": "Advanced Mathematics course",
    "school_id": 1,
    "created_by": 1,
    "created_date": "2025-07-02T13:00:00Z",
    "is_active": true,
    "teacher_count": 2,
    "student_count": 25
  }
]
```

#### POST /study-area/subjects/assign-teacher
**Purpose:** Assign teacher to subject (principal only)
**Authentication:** Principal role required
**Request Body:**
```json
{
  "subject_id": 1,
  "teacher_id": 2
}
```
**Success Response (200):**
```json
{
  "message": "Teacher Jane Smith assigned to Mathematics"
}
```

### User Status

#### GET /study-area/user/status
**Purpose:** Get current user's complete status and available actions
**Authentication:** Any authenticated user
**Success Response (200):**
```json
{
  "user_info": {
    "id": 1,
    "username": "john_doe",
    "email": "john@example.com",
    "full_name": "John Doe",
    "roles": ["normal_user", "student"]
  },
  "school_request_status": {
    "has_request": false,
    "status": null,
    "school_name": null,
    "created_date": null,
    "admin_notes": null
  },
  "schools": {
    "as_principal": {
      "school_id": null,
      "school_name": null
    },
    "as_student": [
      {
        "student_id": 1,
        "school_id": 1,
        "school_name": "Green Springs High School",
        "enrollment_date": "2025-07-02T14:00:00Z"
      }
    ],
    "as_teacher": []
  },
  "available_actions": [
    {
      "action": "create_school_request",
      "description": "Request to become a principal and create a school",
      "endpoint": "/school-requests/create"
    },
    {
      "action": "join_as_teacher",
      "description": "Join a school as a teacher using an access code", 
      "endpoint": "/join-school/teacher"
    }
  ]
}
```

---

## 📝 Grades Endpoints

### Assignment Management

#### POST /grades/assignments/create
**Purpose:** Create new assignment (teacher only)
**Authentication:** Teacher role required
**Request Body:**
```json
{
  "title": "Chapter 5 Quiz",
  "description": "Quiz covering quadratic equations and functions",
  "subtopic": "Quadratic Equations",
  "max_points": 100,
  "due_date": "2025-07-15T23:59:59Z",
  "subject_id": 1
}
```
**Success Response (200):**
```json
{
  "id": 1,
  "title": "Chapter 5 Quiz",
  "description": "Quiz covering quadratic equations and functions",
  "subtopic": "Quadratic Equations", 
  "max_points": 100,
  "due_date": "2025-07-15T23:59:59Z",
  "subject_id": 1,
  "teacher_id": 2,
  "created_date": "2025-07-02T15:00:00Z",
  "is_active": true,
  "subject_name": "Mathematics",
  "teacher_name": "Jane Smith"
}
```

#### GET /grades/assignments/my-assignments
**Purpose:** Get all assignments created by current teacher
**Authentication:** Teacher role required
**Success Response (200):**
```json
[
  {
    "id": 1,
    "title": "Chapter 5 Quiz",
    "description": "Quiz covering quadratic equations",
    "subtopic": "Quadratic Equations",
    "max_points": 100,
    "due_date": "2025-07-15T23:59:59Z",
    "subject_id": 1,
    "teacher_id": 2,
    "created_date": "2025-07-02T15:00:00Z",
    "is_active": true,
    "subject_name": "Mathematics",
    "teacher_name": "Jane Smith",
    "grades": [],
    "total_students": 25,
    "graded_count": 15,
    "average_score": 87.5
  }
]
```

### Grading

#### POST /grades/grades/create
**Purpose:** Create grade for student assignment
**Authentication:** Teacher role required
**Request Body:**
```json
{
  "assignment_id": 1,
  "student_id": 3,
  "points_earned": 85,
  "feedback": "Good work! Review problem #7 for next time."
}
```
**Success Response (200):**
```json
{
  "id": 1,
  "assignment_id": 1,
  "student_id": 3,
  "teacher_id": 2,
  "points_earned": 85,
  "feedback": "Good work! Review problem #7 for next time.",
  "graded_date": "2025-07-02T16:00:00Z",
  "is_active": true,
  "assignment_title": "Chapter 5 Quiz",
  "assignment_max_points": 100,
  "student_name": "John Doe",
  "teacher_name": "Jane Smith",
  "percentage": 85.0
}
```

#### POST /grades/grades/bulk-create
**Purpose:** Grade multiple students at once
**Authentication:** Teacher role required
**Request Body:**
```json
{
  "assignment_id": 1,
  "grades": [
    {
      "student_id": 3,
      "points_earned": 85,
      "feedback": "Good work!"
    },
    {
      "student_id": 4, 
      "points_earned": 92,
      "feedback": "Excellent job!"
    },
    {
      "student_id": 5,
      "points_earned": 78,
      "feedback": "Review section 5.3"
    }
  ]
}
```
**Success Response (200):**
```json
{
  "successful_grades": [
    {
      "id": 1,
      "assignment_id": 1,
      "student_id": 3,
      "points_earned": 85,
      "percentage": 85.0
    },
    {
      "id": 2,
      "assignment_id": 1,
      "student_id": 4,
      "points_earned": 92,
      "percentage": 92.0
    }
  ],
  "failed_grades": [
    {
      "student_id": 5,
      "error": "Student not enrolled in this subject"
    }
  ],
  "total_processed": 3,
  "total_successful": 2,
  "total_failed": 1
}
```

#### GET /grades/grades/my-grades
**Purpose:** Get all grades for current student
**Authentication:** Student role required
**Success Response (200):**
```json
[
  {
    "student_id": 3,
    "student_name": "John Doe",
    "subject_id": 1,
    "subject_name": "Mathematics",
    "grades": [
      {
        "id": 1,
        "assignment_id": 1,
        "points_earned": 85,
        "assignment_title": "Chapter 5 Quiz",
        "assignment_max_points": 100,
        "percentage": 85.0,
        "feedback": "Good work!",
        "graded_date": "2025-07-02T16:00:00Z"
      }
    ],
    "total_assignments": 3,
    "completed_assignments": 1,
    "average_percentage": 85.0
  }
]
```

---

## 🔧 Error Responses

### Common Error Formats

#### 400 Bad Request
```json
{
  "detail": "Validation error message"
}
```

#### 401 Unauthorized
```json
{
  "detail": "Could not validate credentials"
}
```

#### 403 Forbidden
```json
{
  "detail": "Only users with teacher role can access this endpoint"
}
```

#### 404 Not Found
```json
{
  "detail": "School not found"
}
```

#### 500 Internal Server Error
```json
{
  "detail": "Database connection error: [details]"
}
```

---

## 🚀 Integration Tips

### 1. Authentication Flow
```javascript
// Login and store token
const loginResponse = await fetch('/login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ username, password })
});
const { access_token } = await loginResponse.json();
localStorage.setItem('token', access_token);

// Use token in subsequent requests
const headers = {
  'Authorization': `Bearer ${localStorage.getItem('token')}`,
  'Content-Type': 'application/json'
};
```

### 2. Role-Based Navigation
```javascript
// Get user status to determine what they can do
const statusResponse = await fetch('/study-area/user/status', { headers });
const userStatus = await statusResponse.json();

// Route based on roles and current state
if (userStatus.user_info.roles.includes('principal')) {
  // Show principal dashboard
} else if (userStatus.user_info.roles.includes('teacher')) {
  // Show teacher dashboard
} else if (userStatus.user_info.roles.includes('student')) {
  // Show student dashboard
} else {
  // Show onboarding flow
}
```

### 3. Error Handling
```javascript
const handleApiCall = async (url, options) => {
  try {
    const response = await fetch(url, options);
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'API Error');
    }
    return await response.json();
  } catch (error) {
    console.error('API Error:', error.message);
    // Handle specific error codes
    if (error.message.includes('credentials')) {
      // Redirect to login
    }
    throw error;
  }
};
```

This comprehensive reference should give you everything you need to integrate the backend with your frontend seamlessly!
