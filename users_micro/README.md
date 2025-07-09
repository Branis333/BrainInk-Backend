# BrainInk Backend - User Microservice

This microservice handles user management, authentication, school management, academic management, and grade management for the BrainInk application.

## Project Structure

The project has been refactored to have a cleaner, more maintainable structure:

### Endpoints

The API is organized into four main modules:

1. **Auth (`auth.py`)**
   - User authentication and management
   - Login, registration, profile management

2. **School Management (`school_management.py`)**
   - School creation and management
   - School requests
   - Classroom management
   - Role assignments
   - Access codes
   - Direct school joining

3. **Academic Management (`academic_management.py`)**
   - Subject management
   - Teacher/student subject assignments
   - Academic status endpoints

4. **Grades (`grades.py`)**
   - Assignment management
   - Grade management
   - Grade reporting and analytics

### Shared Utilities

Common functions used across multiple endpoints are stored in `utils.py`:
- Role checking and verification
- Access code generation
- Role assignment helpers

## API Route Structure

- `/` - Root endpoint
- `/health` - Health check endpoint
- `/auth/...` - Authentication endpoints
- `/study-area/...` - School management endpoints
  - `/study-area/login-school/select-principal` - Login as principal
  - `/study-area/login-school/select-teacher` - Login as teacher
  - `/study-area/schools/available` - Get available schools
- `/study-area/academic/...` - Academic management endpoints
- `/study-area/grades/...` - Grades and assignments endpoints

## Recent Changes

### Fixed Issues:
1. **Pydantic Warnings**: Updated all schema files to use `from_attributes = True` instead of deprecated `orm_mode = True`
2. **Schema Compatibility**: Fixed `JoinRequestResponse` schema to include all required fields
3. **Model Field References**: Fixed `school_address` references to use correct `address` field from School model
4. **Endpoint Updates**: 
   - Removed `/join-school/request-teacher` endpoint
   - Added `/login-school/select-teacher` endpoint for teacher login
   - Updated route prefixes to avoid conflicts between modules

### API Endpoint Organization:
- **School Management** (`/study-area/`): School operations, role management, direct joining
- **Academic Management** (`/study-area/academic/`): Subject management, assignments
- **Grades Management** (`/study-area/grades/`): Grade-specific operations and reporting
- **School Invitations** (`/study-area/`): New email-based invitation system

## New Email-Based Invitation System

### How It Works:
1. **Principals** can invite teachers/students by email using:
   - `/study-area/invitations/create` - Single invitation
   - `/study-area/invitations/bulk-create` - Multiple invitations
   - `/study-area/invitations/my-school` - View all invitations

2. **Teachers/Students** can join schools using:
   - `/study-area/join-school/teacher` - Join as teacher (requires invitation)
   - `/study-area/join-school/student` - Join as student (requires invitation)
   - `/study-area/invitations/check-eligibility/{school_id}` - Check available invitations

### Benefits:
- ✅ No more complex access codes to manage
- ✅ Direct email-based invitations
- ✅ Automatic role assignment
- ✅ Prevention of duplicate memberships
- ✅ Principal control over who can join their school

## Troubleshooting

### Common Issues and Solutions:

1. **Pydantic `orm_mode` Warning**: 
   - ✅ **Fixed**: All schema files updated to use `from_attributes = True`

2. **Schema Validation Errors**:
   - ✅ **Fixed**: Updated `JoinRequestResponse` schema to include all required fields
   - ✅ **Fixed**: Corrected endpoint responses to match schema definitions

3. **Model Attribute Errors**:
   - ✅ **Fixed**: Updated references from `school_address` to `address` in School model

4. **Endpoint Conflicts**:
   - ✅ **Fixed**: Separated route prefixes to avoid duplicate endpoints
   - ✅ **Fixed**: Removed `/join-school/request-teacher` and added `/login-school/select-teacher`

### Development Notes:
- All endpoint modules now import shared utilities from `utils.py`
- Database models are automatically created on startup
- Router loading is verified during startup with endpoint counts
- All schema `Config` classes now use `from_attributes = True` for Pydantic v2 compatibility

## Database Models

- `users_models.py` - User models
- `study_area_models.py` - Study area models (schools, classrooms, roles, etc.)

## Getting Started

1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

2. Start the application:
   ```
   python main.py
   ```
   or use the provided scripts:
   ```
   ./start.sh  # Linux/Mac
   start.bat   # Windows
   ```

## 📚 Documentation

### API Documentation
- **Swagger UI**: Available at `/docs` when server is running
- **OpenAPI JSON**: Available at `/openapi.json`

### Role-Based Guides
- **[Complete Role Overview](COMPLETE_ROLE_BASED_OVERVIEW.md)** - Comprehensive guide for all user roles
- **[Principal Endpoints](PRINCIPAL_ENDPOINTS_OVERVIEW.md)** - Complete principal functionality guide
- **[Teacher Endpoints](TEACHER_ENDPOINTS_OVERVIEW.md)** - Complete teacher functionality guide  
- **[Student Endpoints](STUDENT_ENDPOINTS_OVERVIEW.md)** - Complete student functionality guide

### System Documentation
- **[Frontend Integration](FRONTEND_INTEGRATION_COMPLETE.md)** - Complete frontend integration guide
- **[Invitation System](INVITATION_SYSTEM_OVERVIEW.md)** - Email-based invitation system overview
- **[Quick Migration Guide](QUICK_MIGRATION_GUIDE.md)** - Migration from access codes to invitations
- **[System Architecture](SYSTEM_WORKFLOW_ARCHITECTURE.md)** - Complete system workflow documentation

### Feature Documentation
- **[Assignments & Grades](ASSIGNMENTS_GRADES_COMPLETE.md)** - Complete assignment and grading system
- **[Subjects System](SUBJECTS_COMPLETE.md)** - Subject management system
- **[API Reference](DETAILED_ENDPOINT_REFERENCE.md)** - Detailed endpoint documentation

### Development Guides
- **[Deployment Guide](DEPLOYMENT_GUIDE.md)** - Production deployment instructions
- **[Testing Documentation](API_DOCUMENTATION.md)** - Testing and validation guides
