# 🎓 Student Endpoints - Complete Overview

## 🎯 Student Role Summary

Students are the primary learners in the BrainInk education platform. They can join schools through email invitations, access their enrolled subjects, view assignments, and track their academic progress through grades and analytics.

---

## 🏫 School Access & Management

### 1. Join School via Email Invitation
```http
POST /study-area/join-school/student
```
**Purpose:** Join a school using email-based invitation  
**Authentication:** Student role required  
**Body:**
```json
{
  "school_id": 1,
  "email": "student@example.com"
}
```
**Response:**
```json
{
  "success": true,
  "message": "Successfully joined Springfield Elementary as a student",
  "school_name": "Springfield Elementary",
  "role": "student",
  "school_id": 1
}
```

### 2. Check Available Invitations
```http
GET /study-area/invitations/available
```
**Purpose:** Check if there are pending school invitations for the student  
**Authentication:** Any authenticated user  
**Response:**
```json
[
  {
    "id": 123,
    "school_name": "Springfield Elementary",
    "invitation_type": "student",
    "invited_date": "2024-01-15T10:30:00Z"
  }
]
```

### 3. Get Available Schools
```http
GET /study-area/schools/available
```
**Purpose:** Get list of all schools with student's role indicator  
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
    "user_role": "student"
  }
]
```

---

## 📚 Subject Management Endpoints

### 4. Get My Enrolled Subjects
```http
GET /study-area/academic/students/my-subjects
```
**Purpose:** Get all subjects the student is enrolled in  
**Authentication:** Student role required  
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
    "student_count": 25,
    "teachers": [
      {
        "teacher_id": 456,
        "name": "John Smith",
        "email": "john.smith@example.com"
      }
    ]
  }
]
```

### 5. Get Subject Details
```http
GET /study-area/academic/subjects/{subject_id}
```
**Purpose:** Get detailed information about a specific enrolled subject  
**Authentication:** Student role required (must be enrolled in subject)  
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
      "name": "John Smith",
      "email": "john.smith@example.com"
    }
  ],
  "total_assignments": 5,
  "completed_assignments": 3,
  "average_grade": 87.5
}
```

---

## 📝 Assignment & Grade Management Endpoints

### 6. Get Subject Assignments
```http
GET /study-area/academic/assignments/subject/{subject_id}
```
**Purpose:** Get all assignments for a specific enrolled subject  
**Authentication:** Student role required (must be enrolled in subject)  
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
    "student_submission_status": "completed",
    "student_grade": 85
  }
]
```

### 7. Get My Grades (All Subjects)
```http
GET /study-area/grades/grades-management/my-grades
```
**Purpose:** Get all grades for the student across all subjects  
**Authentication:** Student role required  
**Response:**
```json
[
  {
    "assignment_id": 1,
    "assignment_title": "Chapter 5 Quiz",
    "subject_id": 1,
    "subject_name": "Advanced Mathematics",
    "teacher_name": "John Smith",
    "points_earned": 85,
    "total_points": 100,
    "percentage": 85.0,
    "feedback": "Good work! Review problems 7-9 for next time.",
    "graded_date": "2024-01-25T14:30:00Z",
    "due_date": "2024-02-15T23:59:59Z"
  }
]
```

### 8. Get Grades for Specific Subject
```http
GET /study-area/grades/grades-management/student/{student_id}/subject/{subject_id}
```
**Purpose:** Get all grades for the student in a specific subject  
**Authentication:** Student role required (must be own grades)  
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

## 📊 Academic Progress & Analytics

### 9. Get Student Dashboard Summary
```http
GET /study-area/analytics/student-dashboard
```
**Purpose:** Get comprehensive academic overview for the student  
**Authentication:** Student role required  
**Response:**
```json
{
  "student_info": {
    "name": "Jane Doe",
    "email": "jane.doe@example.com",
    "school_name": "Springfield Elementary",
    "enrollment_date": "2024-01-10T09:00:00Z"
  },
  "academic_summary": {
    "total_subjects": 6,
    "total_assignments": 28,
    "completed_assignments": 25,
    "overall_average": 87.3,
    "grade_distribution": {
      "A": 15,
      "B": 8,
      "C": 2,
      "D": 0,
      "F": 0
    }
  },
  "recent_grades": [
    {
      "assignment_title": "History Essay",
      "subject_name": "World History",
      "grade": 92,
      "date": "2024-01-28T14:30:00Z"
    }
  ],
  "upcoming_assignments": [
    {
      "assignment_title": "Science Project",
      "subject_name": "Biology",
      "due_date": "2024-02-05T23:59:59Z",
      "days_remaining": 3
    }
  ]
}
```

### 10. Get Subject Performance Analytics
```http
GET /study-area/analytics/student-subject-performance/{subject_id}
```
**Purpose:** Get detailed performance analytics for a specific subject  
**Authentication:** Student role required (must be enrolled in subject)  
**Response:**
```json
{
  "subject_id": 1,
  "subject_name": "Advanced Mathematics",
  "teacher_name": "John Smith",
  "enrollment_date": "2024-01-15T10:30:00Z",
  "performance_metrics": {
    "current_average": 87.5,
    "total_assignments": 5,
    "completed_assignments": 4,
    "missing_assignments": 1,
    "grade_trend": "improving",
    "class_rank": 8,
    "class_average": 82.3
  },
  "assignment_breakdown": [
    {
      "assignment_title": "Chapter 5 Quiz",
      "points_earned": 85,
      "total_points": 100,
      "percentage": 85.0,
      "class_average": 78.5,
      "percentile": 75
    }
  ]
}
```

---

## 👥 School Community & Information

### 11. Get School Information
```http
GET /study-area/schools/my-school
```
**Purpose:** Get information about the student's enrolled school  
**Authentication:** Student role required  
**Response:**
```json
{
  "id": 1,
  "name": "Springfield Elementary School",
  "address": "123 Education Street, Springfield, IL 62701",
  "principal_name": "John Smith",
  "total_students": 300,
  "total_teachers": 15,
  "student_enrollment_date": "2024-01-10T09:00:00Z",
  "academic_year": "2024-2025",
  "semester": "Spring"
}
```

### 12. Get Classmates in Subject
```http
GET /study-area/academic/subjects/{subject_id}/classmates
```
**Purpose:** Get list of other students in the same subject  
**Authentication:** Student role required (must be enrolled in subject)  
**Response:**
```json
[
  {
    "student_id": 790,
    "name": "Alex Johnson",
    "email": "alex.johnson@example.com",
    "enrollment_date": "2024-01-12T09:00:00Z"
  }
]
```

---

## 🔐 User Status & Information

### 13. Get User Status
```http
GET /study-area/user/status
```
**Purpose:** Get current user's status and available actions  
**Authentication:** Any authenticated user  
**Response:**
```json
{
  "user_id": 789,
  "username": "jane_doe",
  "email": "jane.doe@example.com",
  "roles": ["student"],
  "current_schools": [
    {
      "school_id": 1,
      "school_name": "Springfield Elementary",
      "role": "student",
      "enrollment_date": "2024-01-10T09:00:00Z"
    }
  ],
  "available_actions": [
    {
      "action": "view_assignments",
      "description": "View assignments for enrolled subjects",
      "endpoint": "/assignments/subject/{subject_id}"
    },
    {
      "action": "view_grades",
      "description": "View your grades and academic progress",
      "endpoint": "/grades/my-grades"
    }
  ]
}
```

### 14. Check Join Eligibility
```http
GET /study-area/invitations/check-eligibility/{school_id}
```
**Purpose:** Check if student can join a specific school  
**Authentication:** Student role required  
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

## 🎯 Student Workflow Summary

### Getting Started Flow
```
1. Receive Email Invitation → 2. Check Available Invitations → 
3. Join School → 4. Access Student Dashboard
```

### Daily Learning Flow
```
1. View Enrolled Subjects → 2. Check Assignment Deadlines → 
3. Complete Assignments → 4. Review Grades and Feedback
```

### Academic Progress Flow
```
1. View Subject Performance → 2. Analyze Grade Trends → 
3. Identify Areas for Improvement → 4. Track Overall Progress
```

### Assignment Management Flow
```
1. Check Due Assignments → 2. Complete Work → 
3. Submit to Teacher → 4. Receive Grades and Feedback
```

---

## 🔒 Student Permissions Summary

| Action | Permission Level |
|--------|------------------|
| Join Schools | ✅ Via Invitation Only |
| View Assignments | ✅ Enrolled Subjects Only |
| View Grades | ✅ Own Grades Only |
| Access Analytics | ✅ Own Performance Only |
| Create Assignments | ❌ Teachers Only |
| Grade Submissions | ❌ Teachers Only |
| Invite Others | ❌ Principals Only |
| Manage Subjects | ❌ Principals Only |

---

## ⚠️ Important Notes

1. **School Access:** Students can only join schools via email invitations from principals
2. **Subject Enrollment:** Students must be enrolled in subjects by principals or teachers
3. **Data Privacy:** Students can only view their own grades and performance data
4. **Assignment Access:** Students can only view assignments for subjects they're enrolled in
5. **Academic Progress:** Full access to personal analytics and performance tracking
6. **Multi-School Support:** Students can be enrolled in multiple schools simultaneously

---

## 📈 Academic Management Best Practices

### Assignment Tracking
- **Regular Check-ins:** View assignments daily to stay on top of deadlines
- **Time Management:** Use due dates to plan study schedule
- **Progress Monitoring:** Track completion rates across subjects
- **Feedback Review:** Read teacher feedback carefully for improvement

### Grade Management
- **Performance Analysis:** Review grade trends to identify strengths/weaknesses
- **Subject Focus:** Prioritize subjects with lower performance
- **Goal Setting:** Set academic targets based on current performance
- **Progress Tracking:** Monitor improvement over time

### Study Planning
- **Subject Balance:** Allocate time appropriately across all subjects
- **Deadline Management:** Plan ahead for upcoming assignments
- **Performance Goals:** Set realistic academic targets
- **Resource Utilization:** Use teacher feedback to improve

---

## 🚀 Getting Started as Student

1. **Receive Invitation:** Principal sends email invitation to join school
2. **Check Invitations:** Use `/invitations/available` endpoint to see pending invitations
3. **Join School:** Use `/join-school/student` endpoint to join the school
4. **Explore Subjects:** View enrolled subjects using `/students/my-subjects`
5. **Check Assignments:** View assignments for each subject
6. **Track Progress:** Monitor grades and academic performance
7. **Stay Organized:** Use dashboard to manage deadlines and priorities
8. **Engage with Learning:** Complete assignments and review feedback

---

## 📊 Student Dashboard Features

### Academic Overview
- **Current GPA:** Overall grade point average
- **Subject Performance:** Individual subject grades and trends
- **Assignment Status:** Completed vs. pending assignments
- **Upcoming Deadlines:** Next assignments due

### Progress Tracking
- **Grade History:** Track improvement over time
- **Subject Comparison:** Compare performance across subjects
- **Class Ranking:** See position relative to classmates
- **Achievement Badges:** Recognize academic milestones

### Communication
- **Teacher Feedback:** Review assignment comments and suggestions
- **Announcements:** Important updates from teachers and principal
- **Academic Resources:** Study materials and helpful links
- **Support Contacts:** Access to academic counseling and help

---

This comprehensive overview provides students with all the tools they need to succeed academically while maintaining privacy and security through proper role-based access controls.
