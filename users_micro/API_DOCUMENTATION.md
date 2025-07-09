# BrainInk Education Platform API Documentation

## Overview
The BrainInk Education Platform consists of two main endpoint modules:

1. **Study Area Management** (`study_area.py`) - Handles schools, users, subjects, and role management
2. **Assignments & Grades** (`grades.py`) - Handles assignments, grading, and academic progress tracking

## File Structure

### study_area.py
**Tags**: ["Study Area", "Schools", "Subjects", "Roles"]

Contains endpoints for:
- School request management (creation, approval/rejection)
- School management (for principals)
- Access code generation and management
- Student/teacher school enrollment
- Classroom management
- Subject creation and management
- Role assignment and management
- User status checking
- Analytics and reporting

### grades.py
**Tags**: ["Assignments", "Grades"]

Contains endpoints for:
- Assignment creation, updating, and deletion
- Grade creation, updating, and deletion
- Bulk grading operations
- Student grade reports
- Subject grade summaries
- Academic progress tracking

## User Roles and Permissions

### Normal User (default)
- Can create school requests to become principal
- Can join schools as student/teacher with access codes
- Can view their own status and available actions

### Student
- Can view their own grades and assignments
- Can view subjects they're enrolled in
- Can see assignment details for their subjects

### Teacher
- Can create and manage assignments for their assigned subjects
- Can grade student work
- Can add/remove students from their subjects
- Can view grade summaries for their subjects

### Principal
- Can manage their school (view statistics, manage classrooms)
- Can generate access codes for students and teachers
- Can create and assign subjects
- Can assign teachers to subjects
- Can view all school-related analytics

### Admin
- Can approve/reject school requests
- Can assign roles to any user
- Can view all schools and users
- Full system access

## Key Workflows

### 1. School Setup Workflow
1. User creates school request (`POST /school-requests/create`)
2. Admin reviews and approves request (`PUT /school-requests/{id}/review`)
3. Upon approval, school is created and user becomes principal
4. Principal can now manage school and generate access codes

### 2. Student/Teacher Enrollment
1. Principal generates access code for specific email (`POST /access-codes/generate`)
2. User with that email joins school using code (`POST /join-school/student` or `/teacher`)
3. User automatically gets appropriate role and can access school features

### 3. Academic Management
1. Principal creates subjects (`POST /subjects/create`)
2. Principal assigns teachers to subjects (`POST /subjects/assign-teacher`)
3. Teachers add students to their subjects (`POST /subjects/add-student`)
4. Teachers create assignments (`POST /assignments/create`)
5. Teachers grade student work (`POST /grades/create` or `/bulk-create`)

## API Endpoints Summary

### Study Area Endpoints
- `GET /user/status` - Get current user status and available actions
- `POST /school-requests/create` - Create school request
- `GET /school-requests/pending` - Get pending requests (admins)
- `PUT /school-requests/{id}/review` - Approve/reject request (admins)
- `GET /schools/my-school` - Get principal's school with stats
- `POST /access-codes/generate` - Generate access codes (principals)
- `POST /join-school/student` - Join school as student
- `POST /join-school/teacher` - Join school as teacher
- `POST /subjects/create` - Create subject (principals)
- `GET /subjects/my-school` - Get school subjects (principals)
- `POST /subjects/assign-teacher` - Assign teacher to subject
- `GET /teachers/my-subjects` - Get teacher's assigned subjects
- `GET /students/my-subjects` - Get student's enrolled subjects

### Grades Endpoints
- `POST /assignments/create` - Create assignment (teachers)
- `GET /assignments/my-assignments` - Get teacher's assignments
- `GET /assignments/subject/{id}` - Get subject assignments
- `PUT /assignments/{id}` - Update assignment (teachers)
- `DELETE /assignments/{id}` - Delete assignment (teachers)
- `POST /grades/create` - Create single grade (teachers)
- `POST /grades/bulk-create` - Create multiple grades (teachers)
- `GET /grades/student/{id}/subject/{id}` - Get student grades by subject
- `GET /grades/my-grades` - Get student's own grades
- `GET /grades/subject/{id}/summary` - Get subject grade summary
- `PUT /grades/{id}` - Update grade (teachers)
- `DELETE /grades/{id}` - Delete grade (teachers)

## Security Features
- Role-based access control for all endpoints
- Email-based access code system for school enrollment
- Automatic role assignment upon code usage
- Principal ownership validation for school operations
- Teacher assignment validation for grading operations

## Database Integration
Both modules use:
- SQLAlchemy ORM for database operations
- Dependency injection for database sessions
- Transaction management with rollback on errors
- Soft deletion for maintaining data integrity

## Error Handling
Comprehensive error handling including:
- Role permission validation
- Resource ownership verification
- Data validation and constraints
- Proper HTTP status codes and error messages
- Database transaction rollback on failures

## Usage Examples

### For New Users
1. Check status: `GET /user/status`
2. Create school request: `POST /school-requests/create`
3. Wait for admin approval
4. Once approved, start managing school

### For Principals
1. Generate access codes: `POST /access-codes/generate`
2. Create subjects: `POST /subjects/create`
3. Assign teachers: `POST /subjects/assign-teacher`
4. Monitor with analytics:
   - `GET /analytics/school-overview` - Complete school overview with metrics
   - `GET /analytics/subject-performance` - Performance by subject with trends
   - `GET /analytics/grade-distribution` - Grade distribution (A/B/C/D/F)
   - `GET /analytics/completion-rate` - Assignment completion statistics
   - `GET /analytics/daily-active` - Daily active student counts
   - `GET /analytics/session-time` - Average session time metrics

### For Teachers
1. View assigned subjects: `GET /teachers/my-subjects`
2. Create assignments: `POST /assignments/create`
3. Add students to subjects: `POST /subjects/add-student`
4. Grade assignments: `POST /grades/create`

### For Students
1. View enrolled subjects: `GET /students/my-subjects`
2. View assignments: `GET /assignments/subject/{id}`
3. Check grades: `GET /grades/my-grades`
