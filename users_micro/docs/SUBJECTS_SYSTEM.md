# Subjects Management System Documentation

## Overview
The subjects system allows principals to create subjects, assign teachers to them, and enables teachers to enroll students in their assigned subjects.

## System Architecture

### Database Schema
```
subjects
├── id (Primary Key)
├── name (Unique per school)
├── description
├── school_id (Foreign Key to schools)
├── created_by (Foreign Key to users - Principal)
├── created_date
└── is_active

subject_teachers (Many-to-Many)
├── subject_id (Foreign Key to subjects)
└── teacher_id (Foreign Key to teachers)

subject_students (Many-to-Many)
├── subject_id (Foreign Key to subjects)
└── student_id (Foreign Key to students)
```

### Relationships
- **School ↔ Subjects**: One-to-Many (School has many subjects)
- **Subject ↔ Teachers**: Many-to-Many (Teachers can teach multiple subjects, subjects can have multiple teachers)
- **Subject ↔ Students**: Many-to-Many (Students can be in multiple subjects, subjects can have multiple students)

## Workflow

### 1. Principal Creates Subjects
```http
POST /subjects/create
{
    "name": "Mathematics",
    "description": "Advanced mathematics course",
    "school_id": 1
}
```

### 2. Principal Assigns Teachers to Subjects
```http
POST /subjects/assign-teacher
{
    "subject_id": 1,
    "teacher_id": 2
}
```

### 3. Teachers Add Students to Their Subjects
```http
POST /subjects/add-student
{
    "subject_id": 1,
    "student_id": 5
}
```

## API Endpoints

### Principal Endpoints

#### Create Subject
```http
POST /subjects/create
```
**Permissions**: Principals only
**Description**: Create a new subject in their school

#### Get School Subjects
```http
GET /subjects/my-school
```
**Permissions**: Principals only
**Returns**: List of subjects with teacher and student counts

#### Assign Teacher to Subject
```http
POST /subjects/assign-teacher
```
**Permissions**: Principals only
**Description**: Assign a teacher to a subject

#### Remove Teacher from Subject
```http
DELETE /subjects/remove-teacher
```
**Permissions**: Principals only
**Description**: Remove a teacher from a subject

### Teacher Endpoints

#### Get My Subjects
```http
GET /teachers/my-subjects
```
**Permissions**: Teachers only
**Returns**: Subjects assigned to the current teacher

#### Add Student to Subject
```http
POST /subjects/add-student
```
**Permissions**: Teachers (only for their assigned subjects)
**Description**: Enroll a student in the subject

#### Remove Student from Subject
```http
DELETE /subjects/remove-student
```
**Permissions**: Teachers (only for their assigned subjects)
**Description**: Remove a student from the subject

### Shared Endpoints

#### Get Subject Details
```http
GET /subjects/{subject_id}
```
**Permissions**: Principals (for their school) or Teachers (for their subjects)
**Returns**: Subject details with full teacher and student lists

### Student Endpoints

#### Get My Subjects
```http
GET /students/my-subjects
```
**Permissions**: Students only
**Returns**: Subjects the student is enrolled in

## Permission Matrix

| Action | Principal | Teacher | Student |
|--------|-----------|---------|---------|
| Create Subject | ✅ (Own school) | ❌ | ❌ |
| View School Subjects | ✅ (Own school) | ❌ | ❌ |
| Assign Teacher | ✅ (Own school) | ❌ | ❌ |
| Remove Teacher | ✅ (Own school) | ❌ | ❌ |
| View Subject Details | ✅ (Own school) | ✅ (Assigned subjects) | ❌ |
| Add Student | ❌ | ✅ (Assigned subjects) | ❌ |
| Remove Student | ❌ | ✅ (Assigned subjects) | ❌ |
| View My Subjects | ❌ | ✅ | ✅ |

## Data Models

### Subject
```python
{
    "id": 1,
    "name": "Mathematics",
    "description": "Advanced mathematics course",
    "school_id": 1,
    "created_by": 2,
    "created_date": "2025-07-01T10:00:00Z",
    "is_active": true
}
```

### Subject with Details
```python
{
    "id": 1,
    "name": "Mathematics",
    "description": "Advanced mathematics course",
    "school_id": 1,
    "created_by": 2,
    "created_date": "2025-07-01T10:00:00Z",
    "is_active": true,
    "teacher_count": 2,
    "student_count": 25
}
```

### Subject with Members
```python
{
    "id": 1,
    "name": "Mathematics",
    "description": "Advanced mathematics course",
    "school_id": 1,
    "created_by": 2,
    "created_date": "2025-07-01T10:00:00Z",
    "is_active": true,
    "teachers": [
        {
            "id": 1,
            "user_id": 5,
            "name": "John Smith",
            "email": "john.smith@email.com"
        }
    ],
    "students": [
        {
            "id": 1,
            "user_id": 10,
            "name": "Jane Doe",
            "email": "jane.doe@email.com"
        }
    ]
}
```

## Business Rules

### Subject Creation
- Subject names must be unique within a school
- Only principals can create subjects for their school
- Subjects are automatically marked as active

### Teacher Assignment
- Teachers can only be assigned to subjects in their school
- Multiple teachers can be assigned to one subject
- Teachers can be assigned to multiple subjects
- Only principals can assign/remove teachers

### Student Enrollment
- Students can only be enrolled in subjects within their school
- Only assigned teachers can enroll/remove students
- Students can be enrolled in multiple subjects
- Duplicate enrollments are prevented

### Access Control
- Principals: Full control over subjects in their school
- Teachers: Can manage students in their assigned subjects only
- Students: Can view their enrolled subjects only

## Error Handling

### Common Errors
- **403 Forbidden**: User doesn't have permission for the action
- **404 Not Found**: Subject, teacher, or student not found
- **400 Bad Request**: 
  - Duplicate subject name in school
  - Teacher already assigned to subject
  - Student already enrolled in subject
  - Teacher not assigned to subject (when trying to manage students)

### Validation
- Subject names are required and must be unique per school
- All assignments check for valid school membership
- Permission checks ensure proper role-based access

## Migration

Run the migration script to create the necessary tables:

```sql
-- Run migrate_subjects.sql
-- This creates subjects, subject_teachers, and subject_students tables
-- With proper indexes and foreign key constraints
```

## Benefits

1. **Organized Learning**: Clear subject-based organization
2. **Role-Based Control**: Proper separation of responsibilities
3. **Scalability**: Many-to-many relationships support complex scenarios
4. **Security**: Strict permission checking prevents unauthorized access
5. **Flexibility**: Teachers can manage their own student rosters
6. **Tracking**: Full audit trail of who created what and when
