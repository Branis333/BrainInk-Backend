# BrainInk Invitation System - Complete Overview

## 🎯 System Overview

The BrainInk backend has been completely refactored to use a modern **email-based invitation system** instead of access codes. This system provides a secure, intuitive way for principals to invite teachers and students to their schools.

## 🏗️ Core Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   FastAPI       │    │   Database      │
│   (React/Vue)   │◄──►│   Backend       │◄──►│   (Supabase)    │
│                 │    │                 │    │                 │
│ - Login Forms   │    │ - Auth System   │    │ - Users         │
│ - Dashboards    │    │ - Invitations   │    │ - Schools       │
│ - Invitations   │    │ - Academic Mgmt │    │ - Invitations   │
│ - Role-based UI │    │ - Grades        │    │ - Subjects      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 👥 User Roles & Permissions

### 🎓 Principal
- **School Creation**: Request and manage school creation
- **Invitation Management**: Send email invitations to teachers and students
- **Academic Oversight**: Create subjects, assign teachers
- **Analytics**: View school statistics and reports

### 👨‍🏫 Teacher
- **Subject Management**: Manage assigned subjects
- **Assignment Creation**: Create and grade assignments
- **Student Interaction**: Add students to subjects, grade work
- **Class Analytics**: View subject-specific data

### 👨‍🎓 Student
- **School Joining**: Join schools through email invitations
- **Academic Access**: View subjects, assignments, and grades
- **Progress Tracking**: Monitor academic performance

### 🔧 Admin
- **System Oversight**: Approve school creation requests
- **User Management**: Assign roles and manage system users

## 🔄 Complete User Workflows

### 1. New User Onboarding
```
Registration → Login → Role Assignment → Dashboard Access
     ↓
┌─ Register with email/password
├─ Receive JWT token upon login
├─ Check user status (/user/status)
└─ Route to appropriate dashboard
```

### 2. Principal School Setup
```
School Request → Admin Approval → Invitation Management
     ↓
┌─ Submit school creation request
├─ Admin reviews and approves
├─ Principal role automatically assigned
├─ Access to school management features
└─ Can send invitations to teachers/students
```

### 3. Invitation Flow (Teachers/Students)
```
Principal Sends Invitation → Email Received → User Joins School
     ↓
┌─ Principal enters email + role type
├─ Invitation stored in database
├─ User receives invitation details
├─ User joins school using email verification
└─ Role automatically assigned upon joining
```

## 📧 Invitation System Details

### Key Features
- **Email-based**: All invitations tied to specific email addresses
- **Role-specific**: Separate invitation types for teachers and students
- **Security**: Only invited emails can join schools
- **Bulk Operations**: Send multiple invitations at once
- **Management**: Track, cancel, and manage all invitations

### Invitation States
- **Active**: Invitation sent, waiting for user to join
- **Used**: User has successfully joined the school
- **Cancelled**: Principal has deactivated the invitation

## 🔐 Security Model

### Authentication
- JWT-based authentication for all endpoints
- Role-based access control (RBAC)
- Email verification for school joining

### Authorization Layers
1. **Endpoint Level**: Role requirements for each API endpoint
2. **Data Level**: Users can only access their school's data
3. **Invitation Level**: Email matching required for school joining

## 📱 Frontend Integration Points

### Essential Endpoints for Frontend
1. **Authentication**: `/register`, `/login`, `/users/me`
2. **User Status**: `/user/status` (determine user's current state)
3. **School Management**: `/schools/my-school`, school requests
4. **School Discovery**: `/schools/available` (all schools with user's role)
5. **Invitations**: Create, bulk create, manage invitations
6. **Academic**: Subjects, assignments, grades management
7. **Login Selection**: Principal/teacher login flows

### State Management Requirements
- User authentication state (JWT token)
- Current user roles and permissions
- School affiliation and status
- Invitation management state
- Academic data (subjects, assignments, grades)

## 🎨 UI/UX Considerations

### Dashboard Routing
- **Onboarding Flow**: Guide new users through role selection
- **Role-based Dashboards**: Different interfaces for each role
- **Dynamic Navigation**: Show/hide features based on permissions

### Invitation Management UI
- **Bulk Invitation Forms**: Easy multi-user invitation
- **Invitation Status Tracking**: Visual indicators for invitation states
- **Email Validation**: Real-time email format validation
- **Success/Error Handling**: Clear feedback for invitation operations

## 📊 Data Flow Examples

### Principal Inviting a Teacher
```
1. Principal logs in → Dashboard
2. Navigate to "Invite Teachers" 
3. Enter teacher email → POST /invitations/create
4. System creates invitation record
5. Teacher receives invitation details
6. Teacher joins → POST /join-school/teacher
7. System assigns teacher role automatically
```

### Student Joining School
```
1. Student receives invitation email
2. Student logs into platform
3. Navigate to "Join School"
4. Enter school name + email verification
5. POST /join-school/student
6. System verifies invitation and assigns role
7. Student gains access to school features
```

## 🚀 Next Steps for Frontend Development

1. **Setup Authentication Service** with JWT handling
2. **Implement Role-based Routing** for different user types
3. **Create Invitation Management Interface** for principals
4. **Build Join School Forms** for teachers/students
5. **Develop Academic Management UI** for subjects/assignments
6. **Add Real-time Updates** for invitation status changes

This system eliminates the complexity of access codes while providing a more intuitive and secure way to manage school membership through email-based invitations.
