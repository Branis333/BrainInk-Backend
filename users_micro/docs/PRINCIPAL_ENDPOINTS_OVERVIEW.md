# 🎓 Principal Endpoints - Complete Overview

## 🎯 Principal Role Summary

Principals are the highest authority within their schools. They can create and manage schools, invite teachers and students, oversee academic programs, and access comprehensive analytics.

---

## 🏫 School Management Endpoints

### 1. Request School Creation
```http
POST /study-area/school-requests/create
```
**Purpose:** Request to create a new school (requires admin approval)  
**Authentication:** Any authenticated user  
**Body:**
```json
{
  "school_name": "Springfield Elementary School",
  "school_address": "123 Education Street, Springfield, IL 62701"
}
```
**Response:**
```json
{
  "id": 1,
  "school_name": "Springfield Elementary School",
  "school_address": "123 Education Street, Springfield, IL 62701",
  "principal_id": 123,
  "status": "pending",
  "request_date": "2024-01-15T10:30:00Z"
}
```

### 2. Get My School Details
```http
GET /study-area/schools/my-school
```
**Purpose:** Get detailed information about principal's managed school  
**Authentication:** Principal role required  
**Response:**
```json
{
  "id": 1,
  "name": "Springfield Elementary School",
  "address": "123 Education Street, Springfield, IL 62701",
  "principal_id": 123,
  "created_date": "2024-01-15T10:30:00Z",
  "is_active": true,
  "total_students": 300,
  "total_teachers": 15,
  "total_classrooms": 12,
  "active_access_codes": 0
}
```

### 3. Get School Analytics Overview
```http
GET /study-area/analytics/school-overview
```
**Purpose:** Comprehensive analytics dashboard for the school  
**Authentication:** Principal role required  
**Response:**
```json
{
  "school_info": {
    "name": "Springfield Elementary School",
    "address": "123 Education Street, Springfield, IL 62701",
    "created_at": "2024-01-15T10:30:00Z"
  },
  "user_counts": {
    "total_students": 300,
    "total_teachers": 15,
    "recent_students": 5,
    "recent_teachers": 2
  },
  "infrastructure": {
    "total_classrooms": 12
  },
  "analytics": {
    "overall_average": 85.2,
    "completion_rate": 78.5,
    "total_assignments": 45,
    "graded_assignments": 38
  }
}
```

### 4. Get Subject Performance Analytics
```http
GET /study-area/analytics/subject-performance
```
**Purpose:** Performance metrics by subject with trends  
**Authentication:** Principal role required  
**Response:**
```json
{
  "subject_performance": [
    {
      "subject": "Mathematics",
      "average": 87.3,
      "trend": "+2.1%",
      "total_grades": 156
    },
    {
      "subject": "Science",
      "average": 83.7,
      "trend": "-1.2%",
      "total_grades": 142
    }
  ]
}
```

### 5. Get Grade Distribution
```http
GET /study-area/analytics/grade-distribution
```
**Purpose:** Grade distribution percentages (A/B/C/D/F)  
**Authentication:** Principal role required  
**Response:**
```json
{
  "grade_distribution": {
    "Grade A": 28,
    "Grade B": 35,
    "Grade C": 25,
    "Grade D": 8,
    "Grade F": 4
  }
}
```

### 6. Get Completion Rate Details
```http
GET /study-area/analytics/completion-rate
```
**Purpose:** Assignment completion statistics  
**Authentication:** Principal role required  
**Response:**
```json
{
  "completion_rate": 78.5,
  "graded_submissions": 234,
  "expected_submissions": 298,
  "improvement": "+5.1%"
}
```

### 7. Get Daily Active Students
```http
GET /study-area/analytics/daily-active
```
**Purpose:** Daily active student counts  
**Authentication:** Principal role required  
**Response:**
```json
{
  "daily_active": 225,
  "peak_engagement": true,
  "total_students": 300
}
```

### 8. Get Session Time Analytics
```http
GET /study-area/analytics/session-time
```
**Purpose:** Average session time metrics  
**Authentication:** Principal role required  
**Response:**
```json
{
  "average_session_time": "45 minutes",
  "quality_engagement": true
}
```

---

## 📧 Invitation Management Endpoints

### 9. Create Single Invitation
```http
POST /study-area/invitations/create
```
**Purpose:** Invite a teacher or student by email  
**Authentication:** Principal role required  
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
  "school_name": "Springfield Elementary School",
  "invited_by": 456,
  "invited_date": "2024-01-15T10:30:00Z",
  "is_used": false,
  "used_date": null,
  "is_active": true
}
```

### 10. Create Bulk Invitations
```http
POST /study-area/invitations/bulk-create
```
**Purpose:** Invite multiple people at once  
**Authentication:** Principal role required  
**Body:**
```json
{
  "emails": [
    "teacher1@example.com",
    "teacher2@example.com",
    "student1@example.com",
    "student2@example.com"
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
      "school_name": "Springfield Elementary School",
      "invited_by": 456,
      "invited_date": "2024-01-15T10:30:00Z",
      "is_used": false,
      "used_date": null,
      "is_active": true
    }
  ],
  "failed_emails": ["teacher2@example.com"],
  "errors": ["teacher2@example.com: Already has active invitation"],
  "success_count": 1,
  "failed_count": 1
}
```

### 11. Get School Invitations
```http
GET /study-area/invitations/my-school
```
**Purpose:** View all invitations sent for the school  
**Authentication:** Principal role required  
**Response:**
```json
[
  {
    "id": 123,
    "email": "teacher@example.com",
    "invitation_type": "teacher",
    "school_id": 1,
    "school_name": "Springfield Elementary School",
    "invited_by": 456,
    "invited_date": "2024-01-15T10:30:00Z",
    "is_used": false,
    "used_date": null,
    "is_active": true
  }
]
```

### 12. Cancel Invitation
```http
DELETE /study-area/invitations/{invitation_id}
```
**Purpose:** Cancel/deactivate a pending invitation  
**Authentication:** Principal role required  
**Response:**
```json
{
  "message": "Invitation cancelled successfully"
}
```

---

## 📚 Academic Management Endpoints

### 13. Create Subject
```http
POST /study-area/academic/subjects
```
**Purpose:** Create a new subject/course in the school  
**Authentication:** Principal role required  
**Body:**
```json
{
  "name": "Advanced Mathematics",
  "description": "Advanced mathematics course for grade 10",
  "school_id": 1
}
```
**Response:**
```json
{
  "id": 1,
  "name": "Advanced Mathematics",
  "description": "Advanced mathematics course for grade 10",
  "school_id": 1,
  "created_by": 123,
  "created_date": "2024-01-15T10:30:00Z",
  "is_active": true
}
```

### 14. Get School Subjects
```http
GET /study-area/academic/subjects/my-school
```
**Purpose:** Get all subjects in the principal's school  
**Authentication:** Principal role required  
**Response:**
```json
[
  {
    "id": 1,
    "name": "Advanced Mathematics",
    "description": "Advanced mathematics course for grade 10",
    "school_id": 1,
    "created_by": 123,
    "created_date": "2024-01-15T10:30:00Z",
    "is_active": true,
    "teacher_count": 2,
    "student_count": 25
  }
]
```

### 15. Assign Teacher to Subject
```http
POST /study-area/academic/subjects/assign-teacher
```
**Purpose:** Assign a teacher to teach a specific subject  
**Authentication:** Principal role required  
**Body:**
```json
{
  "subject_id": 1,
  "teacher_id": 456
}
```
**Response:**
```json
{
  "message": "Teacher John Smith assigned to Advanced Mathematics successfully"
}
```

### 16. Remove Teacher from Subject
```http
DELETE /study-area/academic/subjects/remove-teacher
```
**Purpose:** Remove a teacher from teaching a subject  
**Authentication:** Principal role required  
**Body:**
```json
{
  "subject_id": 1,
  "teacher_id": 456
}
```

### 17. Add Student to Subject
```http
POST /study-area/academic/subjects/add-student
```
**Purpose:** Enroll a student in a specific subject  
**Authentication:** Principal role required  
**Body:**
```json
{
  "subject_id": 1,
  "student_id": 789
}
```

### 18. Remove Student from Subject
```http
DELETE /study-area/academic/subjects/remove-student
```
**Purpose:** Remove a student from a subject  
**Authentication:** Principal role required  
**Body:**
```json
{
  "subject_id": 1,
  "student_id": 789
}
```

---

## 🏛️ Classroom Management Endpoints

### 19. Create Classroom
```http
POST /study-area/classrooms/create
```
**Purpose:** Create a new classroom in the school  
**Authentication:** Principal role required  
**Body:**
```json
{
  "name": "Math Room A",
  "description": "Primary mathematics classroom",
  "school_id": 1
}
```
**Response:**
```json
{
  "id": 1,
  "name": "Math Room A",
  "description": "Primary mathematics classroom",
  "school_id": 1,
  "is_active": true,
  "created_date": "2024-01-15T10:30:00Z"
}
```

### 20. Get School Classrooms
```http
GET /study-area/classrooms/my-school
```
**Purpose:** Get all classrooms in the principal's school  
**Authentication:** Principal role required  
**Response:**
```json
[
  {
    "id": 1,
    "name": "Math Room A",
    "description": "Primary mathematics classroom",
    "school_id": 1,
    "is_active": true,
    "created_date": "2024-01-15T10:30:00Z"
  }
]
```

---

## 👥 Staff & Student Management Endpoints

### 21. Get School Students
```http
GET /study-area/students/my-school
```
**Purpose:** Get all students enrolled in the school  
**Authentication:** Principal role required  
**Response:**
```json
[
  {
    "id": 1,
    "user_id": 789,
    "school_id": 1,
    "classroom_id": 1,
    "enrollment_date": "2024-01-10T09:00:00Z",
    "is_active": true
  }
]
```

### 22. Get School Teachers
```http
GET /study-area/teachers/my-school
```
**Purpose:** Get all teachers working in the school  
**Authentication:** Principal role required  
**Response:**
```json
[
  {
    "id": 1,
    "user_id": 456,
    "school_id": 1,
    "hire_date": "2024-01-05T08:00:00Z",
    "is_active": true
  }
]
```

---

## 🔐 Role & User Management Endpoints

### 23. Get User Status
```http
GET /study-area/user/status
```
**Purpose:** Get comprehensive status of current principal  
**Authentication:** Principal role required  
**Response:**
```json
{
  "user_id": 123,
  "username": "principal_user",
  "email": "principal@school.com",
  "roles": ["principal"],
  "principal_info": {
    "school_id": 1,
    "school_name": "Springfield Elementary School",
    "school_address": "123 Education Street, Springfield, IL 62701"
  }
}
```

### 24. Get Available Schools
```http
GET /study-area/schools/available
```
**Purpose:** Get list of all schools with principal's role indicator  
**Authentication:** Any authenticated user  
**Response:**
```json
[
  {
    "id": 1,
    "name": "Springfield Elementary School",
    "address": "123 Education Street, Springfield, IL 62701",
    "principal_name": "John Smith",
    "total_students": 300,
    "total_teachers": 15,
    "is_accepting_applications": true,
    "created_date": "2024-01-15T10:30:00Z",
    "user_role": "principal"
  }
]
```

---

## 📊 Advanced Analytics & Reporting

### 25. Subject Details with Members
```http
GET /study-area/academic/subjects/{subject_id}
```
**Purpose:** Get detailed subject information including teachers and students  
**Authentication:** Principal role required  
**Response:**
```json
{
  "id": 1,
  "name": "Advanced Mathematics",
  "description": "Advanced mathematics course for grade 10",
  "school_id": 1,
  "created_by": 123,
  "created_date": "2024-01-15T10:30:00Z",
  "is_active": true,
  "teachers": [
    {
      "teacher_id": 456,
      "user_id": 456,
      "name": "John Smith",
      "email": "john.smith@example.com"
    }
  ],
  "students": [
    {
      "student_id": 789,
      "user_id": 789,
      "name": "Jane Doe",
      "email": "jane.doe@example.com"
    }
  ]
}
```

---

## 🎯 Principal Workflow Summary

### School Setup Flow
```
1. Request School Creation → 2. Wait for Admin Approval → 
3. Get Principal Role → 4. Access School Dashboard
```

### Teacher Onboarding Flow
```
1. Create Teacher Invitation → 2. Teacher Receives Email → 
3. Teacher Joins School → 4. Assign Teacher to Subjects
```

### Student Onboarding Flow
```
1. Create Student Invitation → 2. Student Receives Email → 
3. Student Joins School → 4. Enroll Student in Subjects
```

### Academic Management Flow
```
1. Create Subjects → 2. Assign Teachers → 
3. Enroll Students → 4. Monitor Progress via Analytics
```

---

## 🔒 Principal Permissions Summary

| Action | Permission Level |
|--------|------------------|
| Create/Manage School | ✅ Own School Only |
| Send Invitations | ✅ Own School Only |
| Create Subjects | ✅ Own School Only |
| Assign Teachers | ✅ Own School Only |
| Enroll Students | ✅ Own School Only |
| View Analytics | ✅ Own School Only |
| Create Classrooms | ✅ Own School Only |
| View All Staff/Students | ✅ Own School Only |

---

## ⚠️ Important Notes

1. **School Ownership:** Principals can only manage schools they own
2. **Invitation System:** Replaces legacy access codes - more secure and trackable
3. **Academic Oversight:** Complete control over subjects, teachers, and student enrollment
4. **Analytics Access:** Comprehensive reporting on school performance
5. **Role Restrictions:** Cannot perform actions on other schools
6. **Auto-Assignment:** Principal role is automatically assigned when school request is approved

---

## 🚀 Getting Started as Principal

1. **Create Account:** Register with email and password
2. **Request School:** Submit school creation request
3. **Wait for Approval:** Admin reviews and approves request
4. **Access Dashboard:** Automatic principal role assignment
5. **Invite Staff:** Send email invitations to teachers
6. **Setup Academics:** Create subjects and assign teachers
7. **Enroll Students:** Send invitations and enroll in subjects
8. **Monitor Progress:** Use analytics dashboard for insights
