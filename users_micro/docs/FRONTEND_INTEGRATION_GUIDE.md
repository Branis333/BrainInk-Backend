# Frontend Integration Guide for BrainInk Backend

## 🎯 Quick Setup Checklist

### 1. Server Setup
- **Server URL:** `http://localhost:8000`
- **Start Server:** Run `uvicorn main:app --reload` or use `start.bat`
- **API Docs:** Visit `http://localhost:8000/docs` for interactive testing

### 2. Frontend Configuration
```javascript
// config.js
export const API_BASE_URL = 'http://localhost:8000';
export const ENDPOINTS = {
  auth: {
    register: '/register',
    login: '/login',
    me: '/users/me'
  },
  studyArea: {
    userStatus: '/study-area/user/status',
    schoolRequest: '/study-area/school-requests/create',
    generateCode: '/study-area/access-codes/generate',
    joinStudent: '/study-area/join-school/student',
    joinTeacher: '/study-area/join-school/teacher',
    mySchool: '/study-area/schools/my-school',
    subjects: '/study-area/subjects/my-school'
  },
  grades: {
    createAssignment: '/grades/assignments/create',
    myAssignments: '/grades/assignments/my-assignments',
    myGrades: '/grades/grades/my-grades',
    createGrade: '/grades/grades/create'
  }
};
```

## 🔐 Authentication Service

```javascript
// authService.js
class AuthService {
  constructor() {
    this.token = localStorage.getItem('token');
    this.user = JSON.parse(localStorage.getItem('user') || 'null');
  }

  async register(userData) {
    const response = await fetch(`${API_BASE_URL}/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(userData)
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail);
    }
    
    return await response.json();
  }

  async login(username, password) {
    const response = await fetch(`${API_BASE_URL}/login`, {
      method: 'POST', 
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password })
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail);
    }

    const data = await response.json();
    this.token = data.access_token;
    this.user = data.user_info;
    
    localStorage.setItem('token', this.token);
    localStorage.setItem('user', JSON.stringify(this.user));
    
    return data;
  }

  logout() {
    this.token = null;
    this.user = null;
    localStorage.removeItem('token');
    localStorage.removeItem('user');
  }

  getAuthHeaders() {
    return {
      'Authorization': `Bearer ${this.token}`,
      'Content-Type': 'application/json'
    };
  }

  isAuthenticated() {
    return !!this.token;
  }
}

export const authService = new AuthService();
```

## 🏫 Study Area Service

```javascript
// studyAreaService.js
class StudyAreaService {
  async getUserStatus() {
    const response = await fetch(`${API_BASE_URL}/study-area/user/status`, {
      headers: authService.getAuthHeaders()
    });
    
    if (!response.ok) throw new Error('Failed to get user status');
    return await response.json();
  }

  async createSchoolRequest(schoolData) {
    const response = await fetch(`${API_BASE_URL}/study-area/school-requests/create`, {
      method: 'POST',
      headers: authService.getAuthHeaders(),
      body: JSON.stringify(schoolData)
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail);
    }
    
    return await response.json();
  }

  async generateAccessCode(codeData) {
    const response = await fetch(`${API_BASE_URL}/study-area/access-codes/generate`, {
      method: 'POST',
      headers: authService.getAuthHeaders(),
      body: JSON.stringify(codeData)
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail);
    }
    
    return await response.json();
  }

  async joinSchoolAsStudent(joinData) {
    const response = await fetch(`${API_BASE_URL}/study-area/join-school/student`, {
      method: 'POST',
      headers: authService.getAuthHeaders(),
      body: JSON.stringify(joinData)
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail);
    }
    
    return await response.json();
  }

  async getMySchool() {
    const response = await fetch(`${API_BASE_URL}/study-area/schools/my-school`, {
      headers: authService.getAuthHeaders()
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail);
    }
    
    return await response.json();
  }

  async getSchoolSubjects() {
    const response = await fetch(`${API_BASE_URL}/study-area/subjects/my-school`, {
      headers: authService.getAuthHeaders()
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail);
    }
    
    return await response.json();
  }
}

export const studyAreaService = new StudyAreaService();
```

## 📝 Grades Service

```javascript
// gradesService.js
class GradesService {
  async createAssignment(assignmentData) {
    const response = await fetch(`${API_BASE_URL}/grades/assignments/create`, {
      method: 'POST',
      headers: authService.getAuthHeaders(),
      body: JSON.stringify(assignmentData)
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail);
    }
    
    return await response.json();
  }

  async getMyAssignments() {
    const response = await fetch(`${API_BASE_URL}/grades/assignments/my-assignments`, {
      headers: authService.getAuthHeaders()
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail);
    }
    
    return await response.json();
  }

  async getMyGrades() {
    const response = await fetch(`${API_BASE_URL}/grades/grades/my-grades`, {
      headers: authService.getAuthHeaders()
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail);
    }
    
    return await response.json();
  }

  async createGrade(gradeData) {
    const response = await fetch(`${API_BASE_URL}/grades/grades/create`, {
      method: 'POST',
      headers: authService.getAuthHeaders(),
      body: JSON.stringify(gradeData)
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail);
    }
    
    return await response.json();
  }

  async bulkCreateGrades(bulkGradeData) {
    const response = await fetch(`${API_BASE_URL}/grades/grades/bulk-create`, {
      method: 'POST',
      headers: authService.getAuthHeaders(),
      body: JSON.stringify(bulkGradeData)
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail);
    }
    
    return await response.json();
  }
}

export const gradesService = new GradesService();
```

## 🎨 React Component Examples

### 1. Login Component
```jsx
// LoginForm.jsx
import React, { useState } from 'react';
import { authService } from '../services/authService';

const LoginForm = ({ onLogin }) => {
  const [formData, setFormData] = useState({ username: '', password: '' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const result = await authService.login(formData.username, formData.password);
      onLogin(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="login-form">
      <h2>Login to BrainInk</h2>
      
      {error && <div className="error">{error}</div>}
      
      <input
        type="text"
        placeholder="Username"
        value={formData.username}
        onChange={(e) => setFormData({...formData, username: e.target.value})}
        required
      />
      
      <input
        type="password" 
        placeholder="Password"
        value={formData.password}
        onChange={(e) => setFormData({...formData, password: e.target.value})}
        required
      />
      
      <button type="submit" disabled={loading}>
        {loading ? 'Logging in...' : 'Login'}
      </button>
    </form>
  );
};

export default LoginForm;
```

### 2. User Dashboard Routing
```jsx
// Dashboard.jsx
import React, { useState, useEffect } from 'react';
import { studyAreaService } from '../services/studyAreaService';
import PrincipalDashboard from './PrincipalDashboard';
import TeacherDashboard from './TeacherDashboard';
import StudentDashboard from './StudentDashboard';
import OnboardingFlow from './OnboardingFlow';

const Dashboard = () => {
  const [userStatus, setUserStatus] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadUserStatus();
  }, []);

  const loadUserStatus = async () => {
    try {
      const status = await studyAreaService.getUserStatus();
      setUserStatus(status);
    } catch (error) {
      console.error('Failed to load user status:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <div>Loading...</div>;

  const roles = userStatus?.user_info?.roles || [];

  // Route to appropriate dashboard based on roles
  if (roles.includes('principal')) {
    return <PrincipalDashboard userStatus={userStatus} />;
  } else if (roles.includes('teacher')) {
    return <TeacherDashboard userStatus={userStatus} />;
  } else if (roles.includes('student')) {
    return <StudentDashboard userStatus={userStatus} />;
  } else {
    return <OnboardingFlow userStatus={userStatus} onUpdate={loadUserStatus} />;
  }
};

export default Dashboard;
```

### 3. Access Code Generator (Principal)
```jsx
// AccessCodeGenerator.jsx
import React, { useState } from 'react';
import { studyAreaService } from '../services/studyAreaService';

const AccessCodeGenerator = ({ schoolId }) => {
  const [formData, setFormData] = useState({
    email: '',
    code_type: 'student'
  });
  const [generatedCode, setGeneratedCode] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const codeData = {
        school_id: schoolId,
        email: formData.email,
        code_type: formData.code_type
      };

      const result = await studyAreaService.generateAccessCode(codeData);
      setGeneratedCode(result);
      setFormData({ email: '', code_type: 'student' }); // Reset form
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="access-code-generator">
      <h3>Generate Access Code</h3>
      
      <form onSubmit={handleSubmit}>
        <input
          type="email"
          placeholder="Student/Teacher Email"
          value={formData.email}
          onChange={(e) => setFormData({...formData, email: e.target.value})}
          required
        />
        
        <select
          value={formData.code_type}
          onChange={(e) => setFormData({...formData, code_type: e.target.value})}
        >
          <option value="student">Student</option>
          <option value="teacher">Teacher</option>
        </select>
        
        <button type="submit" disabled={loading}>
          {loading ? 'Generating...' : 'Generate Code'}
        </button>
      </form>

      {error && <div className="error">{error}</div>}
      
      {generatedCode && (
        <div className="generated-code">
          <h4>Code Generated Successfully!</h4>
          <p><strong>Code:</strong> {generatedCode.code}</p>
          <p><strong>For:</strong> {generatedCode.email}</p>
          <p><strong>Type:</strong> {generatedCode.code_type}</p>
          <p>Share this code with the user to join your school.</p>
        </div>
      )}
    </div>
  );
};

export default AccessCodeGenerator;
```

### 4. Join School Form
```jsx
// JoinSchoolForm.jsx
import React, { useState } from 'react';
import { studyAreaService } from '../services/studyAreaService';

const JoinSchoolForm = ({ userEmail, onSuccess }) => {
  const [formData, setFormData] = useState({
    school_name: '',
    access_code: '',
    user_type: 'student'
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const joinData = {
        school_name: formData.school_name,
        email: userEmail,
        access_code: formData.access_code
      };

      let result;
      if (formData.user_type === 'student') {
        result = await studyAreaService.joinSchoolAsStudent(joinData);
      } else {
        result = await studyAreaService.joinSchoolAsTeacher(joinData);
      }

      onSuccess(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="join-school-form">
      <h3>Join a School</h3>
      
      <form onSubmit={handleSubmit}>
        <input
          type="text"
          placeholder="School Name"
          value={formData.school_name}
          onChange={(e) => setFormData({...formData, school_name: e.target.value})}
          required
        />
        
        <input
          type="text"
          placeholder="Access Code"
          value={formData.access_code}
          onChange={(e) => setFormData({...formData, access_code: e.target.value.toUpperCase()})}
          required
        />
        
        <select
          value={formData.user_type}
          onChange={(e) => setFormData({...formData, user_type: e.target.value})}
        >
          <option value="student">Join as Student</option>
          <option value="teacher">Join as Teacher</option>
        </select>
        
        <button type="submit" disabled={loading}>
          {loading ? 'Joining...' : 'Join School'}
        </button>
      </form>

      {error && <div className="error">{error}</div>}
    </div>
  );
};

export default JoinSchoolForm;
```

### 5. Assignment Creator (Teacher)
```jsx
// AssignmentCreator.jsx
import React, { useState, useEffect } from 'react';
import { gradesService } from '../services/gradesService';
import { studyAreaService } from '../services/studyAreaService';

const AssignmentCreator = ({ onSuccess }) => {
  const [subjects, setSubjects] = useState([]);
  const [formData, setFormData] = useState({
    title: '',
    description: '',
    subtopic: '',
    max_points: 100,
    due_date: '',
    subject_id: ''
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    loadSubjects();
  }, []);

  const loadSubjects = async () => {
    try {
      // For teachers, this gets subjects they're assigned to
      const subjectsData = await studyAreaService.getTeacherSubjects();
      setSubjects(subjectsData);
    } catch (err) {
      console.error('Failed to load subjects:', err);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const assignmentData = {
        ...formData,
        subject_id: parseInt(formData.subject_id),
        max_points: parseInt(formData.max_points),
        due_date: formData.due_date ? new Date(formData.due_date).toISOString() : null
      };

      const result = await gradesService.createAssignment(assignmentData);
      onSuccess(result);
      
      // Reset form
      setFormData({
        title: '',
        description: '',
        subtopic: '',
        max_points: 100,
        due_date: '',
        subject_id: ''
      });
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="assignment-creator">
      <h3>Create New Assignment</h3>
      
      <form onSubmit={handleSubmit}>
        <input
          type="text"
          placeholder="Assignment Title"
          value={formData.title}
          onChange={(e) => setFormData({...formData, title: e.target.value})}
          required
        />
        
        <textarea
          placeholder="Description"
          value={formData.description}
          onChange={(e) => setFormData({...formData, description: e.target.value})}
          rows="3"
        />
        
        <input
          type="text"
          placeholder="Subtopic (optional)"
          value={formData.subtopic}
          onChange={(e) => setFormData({...formData, subtopic: e.target.value})}
        />
        
        <input
          type="number"
          placeholder="Max Points"
          value={formData.max_points}
          onChange={(e) => setFormData({...formData, max_points: e.target.value})}
          min="1"
          max="1000"
          required
        />
        
        <input
          type="datetime-local"
          placeholder="Due Date"
          value={formData.due_date}
          onChange={(e) => setFormData({...formData, due_date: e.target.value})}
        />
        
        <select
          value={formData.subject_id}
          onChange={(e) => setFormData({...formData, subject_id: e.target.value})}
          required
        >
          <option value="">Select Subject</option>
          {subjects.map(subject => (
            <option key={subject.id} value={subject.id}>
              {subject.name}
            </option>
          ))}
        </select>
        
        <button type="submit" disabled={loading}>
          {loading ? 'Creating...' : 'Create Assignment'}
        </button>
      </form>

      {error && <div className="error">{error}</div>}
    </div>
  );
};

export default AssignmentCreator;
```

## 🔄 Error Handling Pattern

```javascript
// errorHandler.js
export const handleApiError = (error) => {
  console.error('API Error:', error);
  
  if (error.message.includes('credentials')) {
    // Token expired or invalid
    authService.logout();
    window.location.href = '/login';
  } else if (error.message.includes('Forbidden')) {
    // User doesn't have required role
    return 'You do not have permission to perform this action.';
  } else if (error.message.includes('Not Found')) {
    // Resource not found
    return 'The requested resource was not found.';
  } else {
    // Generic error
    return error.message || 'An unexpected error occurred.';
  }
};
```

## 🎯 Frontend Workflow Summary

### 1. User Registration/Login Flow
```
Register → Login → Get User Status → Route to Dashboard
```

### 2. Principal Workflow
```
Login → Check School Status → Create School (if needed) → 
Generate Access Codes → Manage Subjects → Assign Teachers
```

### 3. Teacher Workflow  
```
Login → Join School (if needed) → View Subjects → 
Create Assignments → Grade Students
```

### 4. Student Workflow
```
Login → Join School (if needed) → View Subjects → 
View Assignments → Check Grades
```

This setup provides a complete foundation for integrating your frontend with the BrainInk backend. Each service handles API communication, authentication, and error handling, while the React components provide reusable UI patterns for common operations.
