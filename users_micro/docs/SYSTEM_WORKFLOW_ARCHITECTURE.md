# BrainInk Backend - System Workflow & Architecture

## 🏗️ System Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   FastAPI       │    │   Database      │
│   (React/Vue)   │◄──►│   Backend       │◄──►│   (Supabase)    │
│                 │    │                 │    │                 │
│ - Login Forms   │    │ - Auth Module   │    │ - Users         │
│ - Dashboards    │    │ - Study Area    │    │ - Schools       │
│ - Role-based UI │    │ - Grades        │    │ - Subjects      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 👥 User Role Hierarchy

```
Admin (Super User)
├── Can approve/reject school requests
├── Can assign any role to any user
└── Can view all schools and users

Principal
├── Can manage their school
├── Can generate access codes
├── Can create subjects and assign teachers
└── Can view school analytics

Teacher  
├── Can create assignments in assigned subjects
├── Can grade students
├── Can add/remove students from subjects
└── Can view their subjects and students

Student
├── Can join schools with access codes
├── Can view their subjects
├── Can view assignments and grades
└── Can check their academic progress

Normal User (Default)
├── Can request to become principal
├── Can join schools with access codes
└── Limited access until role is assigned
```

## 🔄 Complete User Journey Workflows

### 1. New User Registration & Onboarding

```
┌─ User Registration ─┐
│                     │
│ 1. POST /register   │
│    ├─ username      │
│    ├─ email         │
│    ├─ password      │
│    └─ name          │
│                     │
│ 2. Auto-assigned    │
│    └─ normal_user   │
└─────────────────────┘
           │
           ▼
┌─ Login Process ──────┐
│                     │
│ 1. POST /login      │
│    ├─ username      │
│    └─ password      │
│                     │
│ 2. Receive JWT      │
│    └─ access_token  │
└─────────────────────┘
           │
           ▼
┌─ Get User Status ────┐
│                     │
│ GET /user/status    │
│                     │
│ Returns:            │
│ ├─ User info        │
│ ├─ Current roles    │
│ ├─ School status    │
│ └─ Available actions│
└─────────────────────┘
           │
           ▼
     ┌─────────────┐
     │ Route User  │
     │ Based on    │
     │ Status      │
     └─────────────┘
           │
    ┌──────┼──────┐
    │      │      │
    ▼      ▼      ▼
 [Admin] [Has   [New User]
         School] 
         [Role]  
```

### 2. Principal Workflow (School Creation)

```
┌─ Request School Creation ─┐
│                          │
│ POST /school-requests/   │
│      create              │
│                          │
│ Body:                    │
│ ├─ school_name           │
│ └─ school_address        │
│                          │
│ Status: "pending"        │
└──────────────────────────┘
           │
           ▼
┌─ Admin Review Process ────┐
│                          │
│ Admin gets pending       │
│ requests via:            │
│ GET /school-requests/    │
│     pending              │
│                          │
│ Admin approves/rejects:  │
│ PUT /school-requests/    │
│     {id}/review          │
│                          │
│ If APPROVED:             │
│ ├─ School created        │
│ ├─ Principal role        │
│ │  assigned              │
│ └─ User can manage       │
│    school                │
└──────────────────────────┘
           │
           ▼
┌─ School Management ───────┐
│                          │
│ Principal can now:       │
│                          │
│ 1. View school stats:    │
│    GET /schools/my-school│
│                          │
│ 2. Generate access codes:│
│    POST /access-codes/   │
│         generate         │
│                          │
│ 3. Create subjects:      │
│    POST /subjects/create │
│                          │
│ 4. Assign teachers:      │
│    POST /subjects/       │
│         assign-teacher   │
└──────────────────────────┘
```

### 3. Access Code System Workflow

```
┌─ Principal Generates Code ─┐
│                           │
│ POST /access-codes/       │
│      generate             │
│                           │
│ Body:                     │
│ ├─ school_id              │
│ ├─ email (specific user)  │
│ └─ code_type (student/    │
│    teacher)               │
│                           │
│ System:                   │
│ ├─ Generates unique code  │
│ ├─ Associates with email  │
│ └─ Auto-assigns role if   │
│    user exists            │
└───────────────────────────┘
           │
           ▼
┌─ User Joins School ────────┐
│                           │
│ POST /join-school/student │
│  OR                       │
│ POST /join-school/teacher │
│                           │
│ Body:                     │
│ ├─ school_name            │
│ ├─ email (must match)     │
│ └─ access_code            │
│                           │
│ Validation:               │
│ ├─ Email matches current  │
│ │  user                   │
│ ├─ Code exists & active   │
│ ├─ Code assigned to email │
│ └─ Code type matches      │
│    endpoint               │
│                           │
│ Success:                  │
│ ├─ Role assigned          │
│ ├─ School record created  │
│ └─ Access to school       │
│    features               │
└───────────────────────────┘
```

### 4. Teacher Workflow (Subject & Assignment Management)

```
┌─ Teacher Joins School ─────┐
│                           │
│ Uses access code from     │
│ principal to join as      │
│ teacher                   │
└───────────────────────────┘
           │
           ▼
┌─ Principal Assigns Subjects┐
│                           │
│ POST /subjects/           │
│      assign-teacher       │
│                           │
│ Body:                     │
│ ├─ subject_id             │
│ └─ teacher_id             │
│                           │
│ Teacher can now access    │
│ assigned subjects         │
└───────────────────────────┘
           │
           ▼
┌─ Teacher Manages Classes ──┐
│                           │
│ 1. View assigned subjects:│
│    GET /teachers/         │
│        my-subjects        │
│                           │
│ 2. Add students to        │
│    subjects:              │
│    POST /subjects/        │
│         add-student       │
│                           │
│ 3. Create assignments:    │
│    POST /assignments/     │
│         create            │
│                           │
│ 4. Grade assignments:     │
│    POST /grades/create    │
│     OR                    │
│    POST /grades/          │
│         bulk-create       │
└───────────────────────────┘
```

### 5. Student Workflow (Learning & Assessment)

```
┌─ Student Joins School ─────┐
│                           │
│ Uses access code from     │
│ principal to join as      │
│ student                   │
└───────────────────────────┘
           │
           ▼
┌─ Teacher Adds to Subjects ─┐
│                           │
│ Teacher uses:             │
│ POST /subjects/           │
│      add-student          │
│                           │
│ Student gains access to   │
│ subject materials         │
└───────────────────────────┘
           │
           ▼
┌─ Student Academic View ────┐
│                           │
│ 1. View enrolled subjects:│
│    GET /students/         │
│        my-subjects        │
│                           │
│ 2. View assignments in    │
│    each subject:          │
│    GET /assignments/      │
│        subject/{id}       │
│                           │
│ 3. Check grades:          │
│    GET /grades/my-grades  │
│                           │
│ Returns organized by      │
│ subject with:             │
│ ├─ Assignment details     │
│ ├─ Points earned          │
│ ├─ Percentage             │
│ ├─ Teacher feedback       │
│ └─ Overall average        │
└───────────────────────────┘
```

## 🎯 Key API Integration Points

### Authentication Required Endpoints
All endpoints except `/register`, `/login`, and `/health` require:
```
Authorization: Bearer <jwt_token>
```

### Role-Based Access Control

| Endpoint | Admin | Principal | Teacher | Student | Normal User |
|----------|-------|-----------|---------|---------|-------------|
| `/school-requests/create` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `/school-requests/pending` | ✅ | ❌ | ❌ | ❌ | ❌ |
| `/school-requests/{id}/review` | ✅ | ❌ | ❌ | ❌ | ❌ |
| `/access-codes/generate` | ❌ | ✅ | ❌ | ❌ | ❌ |
| `/join-school/student` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `/join-school/teacher` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `/subjects/create` | ❌ | ✅ | ❌ | ❌ | ❌ |
| `/subjects/assign-teacher` | ❌ | ✅ | ❌ | ❌ | ❌ |
| `/subjects/add-student` | ❌ | ❌ | ✅ | ❌ | ❌ |
| `/assignments/create` | ❌ | ❌ | ✅ | ❌ | ❌ |
| `/grades/create` | ❌ | ❌ | ✅ | ❌ | ❌ |
| `/grades/my-grades` | ❌ | ❌ | ❌ | ✅ | ❌ |

### Data Flow Between Modules

```
Auth Module ──► User Authentication ──► Role Assignment
     │                                      │
     ▼                                      ▼
Study Area Module ──► School Management ──► Access Control
     │                      │                    │
     ▼                      ▼                    ▼
Grades Module ──► Assignment Creation ──► Grade Management
```

## 🔍 Database Relationships

```
Users ◄──── has many ────► Roles (many-to-many)
  │
  ├─ manages ─► Schools (one-to-many as principal)
  │
  ├─ member of ─► Students (one-to-many)
  │
  └─ member of ─► Teachers (one-to-many)

Schools
  ├─ has many ─► Students
  ├─ has many ─► Teachers  
  ├─ has many ─► Subjects
  ├─ has many ─► Classrooms
  └─ has many ─► AccessCodes

Subjects ◄──── many-to-many ────► Teachers
    │
    └─ many-to-many ─► Students

Assignments
  ├─ belongs to ─► Subject
  ├─ created by ─► Teacher
  └─ has many ─► Grades

Grades
  ├─ belongs to ─► Assignment
  ├─ belongs to ─► Student
  └─ graded by ─► Teacher
```

## 🚀 Frontend Implementation Strategy

### 1. State Management (Context/Redux)
```javascript
// Global state structure
{
  auth: {
    token: string,
    user: User,
    isAuthenticated: boolean
  },
  app: {
    userStatus: UserStatus,
    currentSchool: School,
    subjects: Subject[],
    assignments: Assignment[],
    grades: Grade[]
  },
  ui: {
    loading: boolean,
    error: string,
    activeTab: string
  }
}
```

### 2. Route Protection
```javascript
// Protected route component
const ProtectedRoute = ({ children, requiredRole }) => {
  const { userStatus } = useContext(AppContext);
  
  if (!userStatus.user_info.roles.includes(requiredRole)) {
    return <AccessDenied />;
  }
  
  return children;
};

// Usage
<Route path="/principal/*" element={
  <ProtectedRoute requiredRole="principal">
    <PrincipalDashboard />
  </ProtectedRoute>
} />
```

### 3. Real-time Updates Pattern
```javascript
// Refresh user status after role changes
const handleJoinSchool = async (joinData) => {
  await studyAreaService.joinSchoolAsStudent(joinData);
  
  // Refresh user status to get updated roles and school info
  const newStatus = await studyAreaService.getUserStatus();
  setUserStatus(newStatus);
  
  // Redirect to appropriate dashboard
  navigate('/dashboard');
};
```

This comprehensive overview should give you everything you need to understand how the backend works and how to integrate it seamlessly with your frontend! The system is designed to be intuitive and follows standard REST API patterns with proper authentication and authorization.
