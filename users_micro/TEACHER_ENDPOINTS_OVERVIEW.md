# 👨‍🏫 Teacher Endpoints - Complete Overview

## 🎯 Teacher Role Summary

Teachers are responsible for academic instruction within their assigned schools. They can manage subjects, create assignments, grade student work, and track academic progress.

---

## 🏫 School Access & Management

### 1. Join School via Email Invitation
```http
POST /study-area/join-school/teacher
```
**Purpose:** Join a school using email-based invitation  
**Authentication:** Teacher role required  
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

### 2. Check Available Invitations
```http
GET /study-area/invitations/available
```
**Purpose:** Check if there are pending school invitations for the teacher  
**Authentication:** Any authenticated user  
**Response:**
```json
[
  {
    "id": 123,
    "school_name": "Springfield Elementary",
    "invitation_type": "teacher",
    "invited_date": "2024-01-15T10:30:00Z"
  }
]
```

### 3. Login to Specific School
```http
POST /study-area/login-school/select-teacher
```
**Purpose:** Select and login to a specific school (for teachers in multiple schools)  
**Authentication:** Teacher role required  
**Body:**
```json
{
  "school_id": 1,
  "email": "teacher@example.com"
}
```
**Response:**
```json
{
  "message": "Successfully logged in as teacher at Springfield Elementary",
  "status": "success",
  "school_name": "Springfield Elementary",
  "note": "Teacher login successful",
  "success": true,
  "school_id": 1,
  "role": "teacher"
}
```

### 4. Get Available Schools
```http
GET /study-area/schools/available
```
**Purpose:** Get list of all schools with teacher's role indicator  
**Authentication:** Any authenticated user  
**Response:**
```json
[
  {
    "id": 1,
    "name": "Springfield Elementary",
    "address": "123 Education Street",
    "principal_name": "John Smith",
    "total_students": 300,
    "total_teachers": 15,
    "is_accepting_applications": true,
    "created_date": "2024-01-15T10:30:00Z",
    "user_role": "teacher"
  }
]
```

---

## 📚 Subject Management Endpoints

### 5. Get My Assigned Subjects
```http
GET /study-area/academic/teachers/my-subjects
```
**Purpose:** Get all subjects assigned to the current teacher  
**Authentication:** Teacher role required  
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

### 6. Get Subject Details with Students
```http
GET /study-area/academic/subjects/{subject_id}
```
**Purpose:** Get detailed information about a specific subject including enrolled students  
**Authentication:** Teacher role required (must be assigned to subject)  
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

## 📝 Assignment Management Endpoints

### 7. Create Assignment
```http
POST /study-area/academic/assignments/create
```
**Purpose:** Create a new assignment for students  
**Authentication:** Teacher role required  
**Body:**
```json
{
  "title": "Chapter 5 Quiz",
  "description": "Quiz covering algebraic expressions and equations",
  "due_date": "2024-02-15T23:59:59Z",
  "total_points": 100,
  "subject_id": 1
}
```
**Response:**
```json
{
  "id": 1,
  "title": "Chapter 5 Quiz",
  "description": "Quiz covering algebraic expressions and equations",
  "due_date": "2024-02-15T23:59:59Z",
  "total_points": 100,
  "subject_id": 1,
  "teacher_id": 456,
  "teacher_name": "John Smith",
  "created_date": "2024-01-20T10:00:00Z",
  "is_active": true
}
```

### 8. Get My Assignments
```http
GET /study-area/grades/assignments-management/my-assignments
```
**Purpose:** Get all assignments created by the current teacher  
**Authentication:** Teacher role required  
**Response:**
```json
[
  {
    "id": 1,
    "title": "Chapter 5 Quiz",
    "description": "Quiz covering algebraic expressions and equations",
    "due_date": "2024-02-15T23:59:59Z",
    "total_points": 100,
    "subject_id": 1,
    "teacher_id": 456,
    "teacher_name": "John Smith",
    "created_date": "2024-01-20T10:00:00Z",
    "is_active": true,
    "total_submissions": 23,
    "graded_submissions": 18,
    "average_score": 87.5
  }
]
```

### 9. Get Subject Assignments
```http
GET /study-area/academic/assignments/subject/{subject_id}
```
**Purpose:** Get all assignments for a specific subject  
**Authentication:** Teacher role required (must be assigned to subject)  
**Response:**
```json
[
  {
    "id": 1,
    "title": "Chapter 5 Quiz",
    "description": "Quiz covering algebraic expressions and equations",
    "due_date": "2024-02-15T23:59:59Z",
    "total_points": 100,
    "subject_id": 1,
    "teacher_id": 456,
    "teacher_name": "John Smith",
    "created_date": "2024-01-20T10:00:00Z",
    "is_active": true
  }
]
```

### 10. Update Assignment
```http
PUT /study-area/academic/assignments/{assignment_id}
```
**Purpose:** Update an existing assignment  
**Authentication:** Teacher role required (must be assignment creator)  
**Body:**
```json
{
  "title": "Chapter 5 Quiz - Updated",
  "description": "Updated quiz covering algebraic expressions, equations, and inequalities",
  "due_date": "2024-02-20T23:59:59Z",
  "total_points": 120
}
```

### 11. Delete Assignment
```http
DELETE /study-area/academic/assignments/{assignment_id}
```
**Purpose:** Delete an assignment  
**Authentication:** Teacher role required (must be assignment creator)  
**Response:**
```json
{
  "message": "Assignment deleted successfully"
}
```

---

## ✅ Grading Management Endpoints

### 12. Create Grade
```http
POST /study-area/academic/grades/create
```
**Purpose:** Grade a student's assignment  
**Authentication:** Teacher role required  
**Body:**
```json
{
  "assignment_id": 1,
  "student_id": 789,
  "points_earned": 85,
  "feedback": "Good work! Review problems 7-9 for next time."
}
```
**Response:**
```json
{
  "id": 1,
  "assignment_id": 1,
  "student_id": 789,
  "teacher_id": 456,
  "points_earned": 85,
  "percentage": 85.0,
  "feedback": "Good work! Review problems 7-9 for next time.",
  "graded_date": "2024-01-25T14:30:00Z"
}
```

### 13. Bulk Grade Creation
```http
POST /study-area/academic/grades/bulk
```
**Purpose:** Grade multiple students at once  
**Authentication:** Teacher role required  
**Body:**
```json
{
  "assignment_id": 1,
  "grades": [
    {
      "student_id": 789,
      "points_earned": 85,
      "feedback": "Good work!"
    },
    {
      "student_id": 790,
      "points_earned": 92,
      "feedback": "Excellent work!"
    }
  ]
}
```
**Response:**
```json
{
  "successful_grades": [
    {
      "id": 1,
      "student_id": 789,
      "points_earned": 85,
      "percentage": 85.0
    },
    {
      "id": 2,
      "student_id": 790,
      "points_earned": 92,
      "percentage": 92.0
    }
  ],
  "failed_grades": [],
  "total_successful": 2,
  "total_failed": 0
}
```

### 14. Get Assignment Grades
```http
GET /study-area/academic/grades/assignment/{assignment_id}
```
**Purpose:** Get all grades for a specific assignment  
**Authentication:** Teacher role required (must be assignment creator)  
**Response:**
```json
[
  {
    "id": 1,
    "assignment_id": 1,
    "student_id": 789,
    "student_name": "Jane Doe",
    "teacher_id": 456,
    "points_earned": 85,
    "percentage": 85.0,
    "feedback": "Good work!",
    "graded_date": "2024-01-25T14:30:00Z"
  }
]
```

### 15. Get Subject Grades Summary
```http
GET /study-area/academic/grades/subject/{subject_id}/summary
```
**Purpose:** Get comprehensive grading summary for a subject  
**Authentication:** Teacher role required (must be assigned to subject)  
**Response:**
```json
{
  "subject_id": 1,
  "subject_name": "Advanced Mathematics",
  "total_assignments": 5,
  "total_students": 25,
  "average_class_score": 87.3,
  "assignments": [
    {
      "assignment_id": 1,
      "assignment_title": "Chapter 5 Quiz",
      "total_submissions": 23,
      "graded_submissions": 23,
      "average_score": 85.2
    }
  ]
}
```

### 16. Update Grade
```http
PUT /study-area/academic/grades/{grade_id}
```
**Purpose:** Update an existing grade  
**Authentication:** Teacher role required (must be grade creator)  
**Body:**
```json
{
  "points_earned": 90,
  "feedback": "Improved work! Great job on the corrections."
}
```

### 17. Delete Grade
```http
DELETE /study-area/academic/grades/{grade_id}
```
**Purpose:** Delete a grade  
**Authentication:** Teacher role required (must be grade creator)  
**Response:**
```json
{
  "message": "Grade deleted successfully"
}
```

---

## 👥 Student Management in Subjects

### 18. Get Student Grades in Subject
```http
GET /study-area/academic/grades/student/{student_id}/subject/{subject_id}
```
**Purpose:** Get all grades for a specific student in a specific subject  
**Authentication:** Teacher role required (must be assigned to subject)  
**Response:**
```json
{
  "student_id": 789,
  "student_name": "Jane Doe",
  "subject_id": 1,
  "subject_name": "Advanced Mathematics",
  "grades": [
    {
      "assignment_id": 1,
      "assignment_title": "Chapter 5 Quiz",
      "points_earned": 85,
      "total_points": 100,
      "percentage": 85.0,
      "graded_date": "2024-01-25T14:30:00Z",
      "feedback": "Good work!"
    }
  ],
  "overall_average": 87.5,
  "total_assignments": 5,
  "completed_assignments": 4
}
```

---

## 📊 Teacher Status & Information

### 19. Get User Status
```http
GET /study-area/user/status
```
**Purpose:** Get comprehensive status of current teacher  
**Authentication:** Teacher role required  
**Response:**
```json
{
  "user_id": 456,
  "username": "teacher_user",
  "email": "teacher@example.com",
  "roles": ["teacher"],
  "teacher_info": {
    "schools": [
      {
        "school_id": 1,
        "school_name": "Springfield Elementary",
        "teacher_id": 789
      }
    ]
  }
}
```

### 20. Check Join Eligibility
```http
GET /study-area/invitations/check-eligibility/{school_id}
```
**Purpose:** Check if teacher can join a specific school  
**Authentication:** Teacher role required  
**Response:**
```json
{
  "can_join": true,
  "invitation_exists": true,
  "invitation_id": 123,
  "message": "You have a pending invitation to join this school"
}
```

---

## 🎯 Teacher Workflow Summary

### Getting Started Flow
```
1. Receive Email Invitation → 2. Check Available Invitations → 
3. Join School → 4. Access Teacher Dashboard
```

### Daily Teaching Flow
```
1. Login to School → 2. View Assigned Subjects → 
3. Create/Manage Assignments → 4. Grade Student Work
```

### Assignment Management Flow
```
1. Create Assignment → 2. Students Submit Work → 
3. Grade Submissions → 4. Provide Feedback
```

### Progress Monitoring Flow
```
1. View Subject Summary → 2. Analyze Student Performance → 
3. Identify Struggling Students → 4. Adjust Teaching Strategy
```

---

## 🔒 Teacher Permissions Summary

| Action | Permission Level |
|--------|------------------|
| Join Schools | ✅ Via Invitation Only |
| Create Assignments | ✅ Assigned Subjects Only |
| Grade Students | ✅ Own Assignments Only |
| View Student Grades | ✅ Own Subjects Only |
| Manage Subjects | ❌ Principal Only |
| Invite Students | ❌ Principal Only |
| School Analytics | ❌ Principal Only |
| Create Subjects | ❌ Principal Only |

---

## ⚠️ Important Notes

1. **School Access:** Teachers can only join schools via email invitations from principals
2. **Subject Assignment:** Teachers must be assigned to subjects by principals before they can teach
3. **Grading Authority:** Teachers can only grade assignments they've created
4. **Student Privacy:** Teachers can only view grades for their own subjects
5. **Multi-School Support:** Teachers can work at multiple schools simultaneously
6. **Assignment Ownership:** Only assignment creators can modify or delete assignments

---

## 📈 Academic Management Best Practices

### Assignment Creation
- **Clear Instructions:** Provide detailed assignment descriptions
- **Realistic Deadlines:** Set appropriate due dates
- **Point Distribution:** Use consistent grading scales
- **Regular Assignments:** Maintain steady assessment schedule

### Grading Workflow
- **Timely Feedback:** Grade assignments promptly
- **Constructive Comments:** Provide helpful feedback
- **Consistent Rubrics:** Apply grading standards fairly
- **Progress Tracking:** Monitor student improvement

### Student Engagement
- **Subject Variety:** Create diverse assignment types
- **Difficulty Progression:** Gradually increase complexity
- **Individual Support:** Address struggling students
- **Performance Analytics:** Use data to improve teaching

---

## 🚀 Getting Started as Teacher

1. **Receive Invitation:** Principal sends email invitation
2. **Check Invitations:** Use `/invitations/available` endpoint
3. **Join School:** Use `/join-school/teacher` endpoint
4. **Get Assigned:** Principal assigns you to subjects
5. **View Subjects:** Use `/teachers/my-subjects` endpoint
6. **Create Assignments:** Start teaching with assignments
7. **Grade Students:** Provide feedback and grades
8. **Monitor Progress:** Track student performance
