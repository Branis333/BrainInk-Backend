# Assignments and Grades System Documentation

## Overview

The Assignments and Grades System allows teachers to create assignments for their subjects and grade students' work. Students can view their assignments and grades, while teachers and principals can access grade analytics and reports.

## Features

### For Teachers
- Create assignments for subjects they're assigned to
- Set assignment details (title, description, due date, max points)
- Grade students individually or in bulk
- Update assignments and grades
- View grade statistics and analytics
- Delete assignments and grades (soft delete)

### For Students
- View assignments for subjects they're enrolled in
- View their grades across all subjects
- See grade details including feedback and percentages

### For Principals
- View assignments and grades for subjects in their school
- Access grade analytics and summaries
- Monitor teacher performance and student progress

## Database Schema

### Assignments Table
```sql
CREATE TABLE assignments (
    id SERIAL PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    description TEXT,
    subtopic VARCHAR(100),
    subject_id INTEGER NOT NULL REFERENCES subjects(id),
    teacher_id INTEGER NOT NULL REFERENCES teachers(id),
    max_points INTEGER NOT NULL DEFAULT 100 CHECK (max_points > 0),
    due_date TIMESTAMP,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);
```

### Grades Table
```sql
CREATE TABLE grades (
    id SERIAL PRIMARY KEY,
    assignment_id INTEGER NOT NULL REFERENCES assignments(id),
    student_id INTEGER NOT NULL REFERENCES students(id),
    teacher_id INTEGER NOT NULL REFERENCES teachers(id),
    points_earned INTEGER NOT NULL CHECK (points_earned >= 0),
    feedback TEXT,
    graded_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    CONSTRAINT uq_assignment_student UNIQUE (assignment_id, student_id)
);
```

## API Endpoints

### Assignment Endpoints

#### Create Assignment
- **POST** `/assignments/create`
- **Access**: Teachers only (for their assigned subjects)
- **Body**: `AssignmentCreate`
```json
{
    "title": "Algebra Homework #1",
    "description": "Complete exercises 1-20 from chapter 3",
    "subtopic": "Linear Equations",
    "subject_id": 1,
    "max_points": 100,
    "due_date": "2024-01-15T23:59:59"
}
```

#### Get Teacher's Assignments
- **GET** `/assignments/my-assignments`
- **Access**: Teachers only
- **Returns**: List of assignments with grade statistics

#### Get Subject Assignments
- **GET** `/assignments/subject/{subject_id}`
- **Access**: Teachers and students in the subject, principals
- **Returns**: List of assignments for the subject

#### Update Assignment
- **PUT** `/assignments/{assignment_id}`
- **Access**: Teacher who created the assignment
- **Body**: `AssignmentUpdate`

#### Delete Assignment
- **DELETE** `/assignments/{assignment_id}`
- **Access**: Teacher who created the assignment
- **Note**: Soft delete (sets is_active = false)

### Grade Endpoints

#### Create Grade
- **POST** `/grades/create`
- **Access**: Teachers only (for their assignments)
- **Body**: `GradeCreate`
```json
{
    "assignment_id": 1,
    "student_id": 1,
    "points_earned": 85,
    "feedback": "Good work! Pay attention to showing your work."
}
```

#### Bulk Create Grades
- **POST** `/grades/bulk-create`
- **Access**: Teachers only (for their assignments)
- **Body**: `BulkGradeCreate`
```json
{
    "assignment_id": 1,
    "grades": [
        {"student_id": 1, "points_earned": 95, "feedback": "Excellent!"},
        {"student_id": 2, "points_earned": 78, "feedback": "Good effort"}
    ]
}
```

#### Get Student Grades by Subject
- **GET** `/grades/student/{student_id}/subject/{subject_id}`
- **Access**: Student themselves, teachers in subject, principals
- **Returns**: Complete grade report for student in subject

#### Get My Grades
- **GET** `/grades/my-grades`
- **Access**: Students only
- **Returns**: All grades for the current student across all subjects

#### Get Subject Grades Summary
- **GET** `/grades/subject/{subject_id}/summary`
- **Access**: Teachers in subject, principals
- **Returns**: Complete grade analytics for the subject

#### Update Grade
- **PUT** `/grades/{grade_id}`
- **Access**: Teacher who created the grade
- **Body**: `GradeUpdate`

#### Delete Grade
- **DELETE** `/grades/{grade_id}`
- **Access**: Teacher who created the grade
- **Note**: Soft delete (sets is_active = false)

## Permission System

### Teacher Permissions
- Can create assignments only for subjects they're assigned to
- Can grade only their own assignments
- Can grade only students enrolled in the subject
- Can update/delete only their own assignments and grades

### Student Permissions
- Can view assignments for subjects they're enrolled in
- Can view only their own grades
- Cannot create, update, or delete assignments or grades

### Principal Permissions
- Can view all assignments and grades in their school
- Cannot create, update, or delete assignments or grades
- Can access analytics and reports

## Data Validation

### Assignment Validation
- Title: Required, 1-200 characters
- Max points: Must be greater than 0, maximum 1000
- Subject: Must exist and teacher must be assigned to it
- Due date: Optional, must be in the future (recommended)

### Grade Validation
- Points earned: Must be >= 0 and <= assignment max_points
- Student: Must be enrolled in the assignment's subject
- Assignment: Must exist and be active
- Unique constraint: One grade per student per assignment

## Error Handling

### Common Error Scenarios
1. **403 Forbidden**: User lacks permission for the operation
2. **404 Not Found**: Assignment, grade, student, or subject not found
3. **400 Bad Request**: Validation errors (points exceed max, student not in subject, etc.)
4. **500 Internal Server Error**: Database or server errors

### Specific Validations
- Teachers can only grade students in their assigned subjects
- Points earned cannot exceed assignment max points
- Existing grades cannot be exceeded when reducing assignment max points
- Students must be enrolled in subject to receive grades

## Usage Examples

### Creating an Assignment
```python
# Teacher creates an assignment
assignment_data = {
    "title": "Chapter 5 Quiz",
    "description": "Quiz covering sections 5.1-5.3",
    "subject_id": 1,
    "max_points": 50,
    "due_date": "2024-02-01T14:00:00"
}

response = requests.post(
    "/assignments/create",
    json=assignment_data,
    headers={"Authorization": f"Bearer {teacher_token}"}
)
```

### Grading Students
```python
# Individual grade
grade_data = {
    "assignment_id": 1,
    "student_id": 5,
    "points_earned": 47,
    "feedback": "Excellent work on problems 1-8. Review quadratic formula for #9."
}

# Bulk grading
bulk_data = {
    "assignment_id": 1,
    "grades": [
        {"student_id": 1, "points_earned": 45, "feedback": "Good job!"},
        {"student_id": 2, "points_earned": 38, "feedback": "Study section 5.2"},
        {"student_id": 3, "points_earned": 50, "feedback": "Perfect score!"}
    ]
}
```

### Viewing Grades
```python
# Student views their grades
my_grades = requests.get(
    "/grades/my-grades",
    headers={"Authorization": f"Bearer {student_token}"}
)

# Teacher views subject summary
subject_summary = requests.get(
    "/grades/subject/1/summary",
    headers={"Authorization": f"Bearer {teacher_token}"}
)
```

## Analytics and Reporting

### Assignment Statistics
- Total students in subject
- Number of students graded
- Average score as percentage
- Grade distribution

### Student Reports
- Completed vs. total assignments
- Average percentage across all grades
- Individual grade details with feedback
- Progress tracking by subject

### Subject Summaries
- Class-wide statistics
- Assignment-by-assignment breakdown
- Teacher performance metrics
- Grade distribution analysis

## Migration Guide

To add the assignments and grades system to your existing database:

1. **Run the migration script**:
   ```bash
   psql -d your_database -f migrate_assignments_grades.sql
   ```

2. **Update your application**:
   - Add the new models to your SQLAlchemy setup
   - Import the new schemas and endpoints
   - Update your router to include the assignments/grades endpoints

3. **Test the system**:
   - Use the provided test script `test_assignments_grades.py`
   - Verify permissions and data validation
   - Test all CRUD operations

## Best Practices

### For Teachers
1. **Clear Assignment Descriptions**: Provide detailed instructions and expectations
2. **Reasonable Due Dates**: Allow adequate time for completion
3. **Consistent Grading**: Use rubrics and provide meaningful feedback
4. **Timely Grading**: Grade assignments promptly to provide quick feedback

### For Administrators
1. **Regular Monitoring**: Review grade distributions and teacher performance
2. **Data Backup**: Ensure regular backups of grade data
3. **Access Control**: Regularly audit user permissions and access logs
4. **Performance Monitoring**: Monitor database performance with grade queries

### For Developers
1. **Input Validation**: Always validate user input on both client and server
2. **Permission Checks**: Verify permissions for every operation
3. **Error Handling**: Provide clear, helpful error messages
4. **Database Indexes**: Ensure proper indexing for performance
5. **Audit Logging**: Log all grade changes for accountability

## Security Considerations

1. **Data Privacy**: Grade data is sensitive - ensure proper access controls
2. **Audit Trail**: Log all grade modifications with timestamps and user IDs
3. **Input Sanitization**: Prevent SQL injection and XSS attacks
4. **Rate Limiting**: Implement rate limiting for bulk operations
5. **Data Encryption**: Encrypt sensitive data in transit and at rest

## Troubleshooting

### Common Issues
1. **Permission Denied**: Verify user roles and subject assignments
2. **Grade Validation Errors**: Check points vs. max points constraints
3. **Student Not Found**: Ensure student is enrolled in the subject
4. **Database Constraints**: Check unique constraints and foreign keys

### Performance Optimization
1. **Query Optimization**: Use appropriate indexes and query patterns
2. **Bulk Operations**: Use bulk endpoints for multiple grades
3. **Caching**: Consider caching frequently accessed grade summaries
4. **Pagination**: Implement pagination for large result sets

This comprehensive system provides a robust foundation for academic grade management while maintaining security, data integrity, and user experience.
