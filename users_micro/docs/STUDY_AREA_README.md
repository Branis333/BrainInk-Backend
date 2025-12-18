# BrainInk Backend - Study Area Management System

## Overview

This is a comprehensive school management backend system that allows:

- **School Registration System**: Principals can request to create schools, admins approve/reject
- **Role-Based Access Control**: Users have roles (normal_user, student, teacher, principal, admin)
- **Access Code System**: Unique codes for students and teachers to join schools
- **School Analytics**: Principals can view detailed school statistics
- **User Management**: Complete user and role management system

## Database Models

### User Roles
- `normal_user`: Default role for new users
- `student`: Student role for school students
- `teacher`: Teacher role for school teachers
- `principal`: Principal role for school administrators
- `admin`: System administrator role

### Core Models
- **User**: Base user model with role relationship
- **Role**: User roles (normal_user, student, teacher, principal, admin)
- **SchoolRequest**: Requests from principals to create schools
- **School**: School entities managed by principals
- **Classroom**: Classrooms within schools
- **AccessCode**: Unique codes for joining schools (student/teacher specific)
- **Student**: Student profiles linked to users and schools
- **Teacher**: Teacher profiles linked to users and schools

## API Endpoints

### School Request Management

#### `POST /school-requests/create`
Create a school registration request (principals only)
```json
{
  "school_name": "Greenwood High School",
  "school_address": "123 Education St"
}
```

#### `GET /school-requests/pending`
Get all pending school requests (admins only)

#### `PUT /school-requests/{request_id}/review`
Approve or reject a school request (admins only)
```json
{
  "status": "approved",
  "admin_notes": "Approved after verification"
}
```

### School Management

#### `GET /schools/my-school`
Get school managed by current principal with statistics

#### `GET /schools`
Get all schools (admins only)

### Access Code Management

#### `POST /access-codes/generate`
Generate access code for students or teachers (principals only)
```json
{
  "code_type": "student",
  "school_id": 1,
  "max_usage": 50,
  "expires_date": "2025-12-31T23:59:59"
}
```

#### `GET /access-codes/my-school`
Get all access codes for principal's school

#### `DELETE /access-codes/{code_id}`
Deactivate an access code (principals only)

### School Joining

#### `POST /join-school/student`
Join a school as a student using access code
```json
{
  "school_name": "Greenwood High School",
  "email": "student@example.com",
  "access_code": "ABC123XY"
}
```

#### `POST /join-school/teacher`
Join a school as a teacher using access code
```json
{
  "school_name": "Greenwood High School",
  "email": "teacher@example.com",
  "access_code": "DEF456ZW"
}
```

### Classroom Management

#### `POST /classrooms/create`
Create a new classroom (principals only)
```json
{
  "name": "Grade 10-A",
  "school_id": 1
}
```

#### `GET /classrooms/my-school`
Get all classrooms for principal's school

### Role Management

#### `POST /roles/assign`
Assign a role to a user (admins only)
```json
{
  "user_id": 123,
  "role_name": "principal"
}
```

#### `GET /roles/all`
Get all available roles (admins only)

#### `GET /users/by-role/{role_name}`
Get all users with a specific role (admins only)

### Analytics

#### `GET /analytics/school-overview`
Get comprehensive school analytics for principals
Returns:
- School information
- Total counts (students, teachers, classrooms)
- Active access codes
- Recent activity (30-day enrollments)

## Setup Instructions

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Database Setup
1. Create your database
2. Run database migrations to create tables
3. Initialize roles:
```bash
python initialize_roles.py
```

### 3. Create Admin User
Create the first admin user manually or through your user registration system, then assign admin role.

### 4. Workflow Example

1. **Admin Setup**: Create admin user and initialize roles
2. **Principal Registration**: Principal registers as normal user
3. **Role Assignment**: Admin assigns principal role to user
4. **School Request**: Principal creates school request
5. **Admin Approval**: Admin approves school request (creates school)
6. **Access Codes**: Principal generates access codes for students/teachers
7. **User Joining**: Students/teachers join school using access codes
8. **Management**: Principal manages school through analytics and management endpoints

## Security Features

- Role-based access control for all endpoints
- User verification for school joining (email must match)
- Access code expiration and usage limits
- School ownership verification for principals
- Admin-only sensitive operations

## Error Handling

The API includes comprehensive error handling:
- 400: Bad Request (invalid data, duplicate entries)
- 403: Forbidden (insufficient permissions)
- 404: Not Found (resource doesn't exist)
- 500: Internal Server Error (database/system errors)

## Database Relationships

```
User (1) -> (1) Role
User (1) -> (0..1) Student
User (1) -> (0..1) Teacher
User (1) -> (0..*) School (as principal)
User (1) -> (0..*) SchoolRequest (as principal)

School (1) -> (0..*) Student
School (1) -> (0..*) Teacher
School (1) -> (0..*) Classroom
School (1) -> (0..*) AccessCode

Classroom (1) -> (0..*) Student
Classroom (1) -> (0..1) Teacher (assigned)
```

## Next Steps

Consider implementing:
- Email notifications for school request status
- Bulk access code generation
- Student/teacher performance tracking
- Attendance management
- Grade management system
- Parent portal integration
