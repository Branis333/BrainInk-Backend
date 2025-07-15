# Direct School Joining System - Implementation Guide

## 🎯 Overview

This new system allows logged-in users to join schools as principals or teachers by:
1. **Selecting from available schools** (instead of needing access codes)
2. **Providing their email** (for verification)
3. **Getting automatic or admin-approved access**

## 🆕 New Endpoints

### 1. Get Available Schools
```http
GET /study-area/schools/available
```
**Purpose:** Show all schools users can join
**Authentication:** Any logged-in user
**Response:**
```json
[
  {
    "id": 1,
    "name": "Green Springs High School",
    "address": "123 Education St",
    "principal_name": "John Doe",
    "total_students": 150,
    "total_teachers": 12,
    "is_accepting_applications": true,
    "created_date": "2025-07-02T10:00:00Z"
  }
]
```

### 2. Request to Join as Teacher
```http
POST /study-area/join-school/request-teacher
```
**Purpose:** Join a school as teacher (auto-approved if school has principal)
**Authentication:** Any logged-in user
**Request Body:**
```json
{
  "school_id": 1,
  "email": "teacher@example.com"
}
```
**Success Response:**
```json
{
  "message": "Successfully joined Green Springs High School as teacher",
  "status": "approved",
  "school_name": "Green Springs High School",
  "request_id": null,
  "note": "You can now be assigned to subjects by the principal"
}
```

### 3. Request to Join as Principal
```http
POST /study-area/join-school/request-principal
```
**Purpose:** Request to become principal (requires admin approval)
**Authentication:** Any logged-in user
**Request Body:**
```json
{
  "school_id": 1,
  "email": "principal@example.com"
}
```
**Success Response:**
```json
{
  "message": "Principal request submitted for Green Springs High School",
  "status": "pending_admin_approval",
  "school_name": "Green Springs High School",
  "request_id": 123,
  "note": "An admin will review your request and assign you as principal if approved"
}
```

### 4. Get Pending Principal Requests (Admin Only)
```http
GET /study-area/school-requests/principal-pending
```
**Purpose:** View all pending principal requests
**Authentication:** Admin role required
**Response:**
```json
[
  {
    "id": 123,
    "user_id": 5,
    "username": "john_doe",
    "user_email": "john@example.com",
    "user_name": "John Doe",
    "school_id": 1,
    "school_name": "Green Springs High School",
    "current_principal": false,
    "request_date": "2025-07-02T14:00:00Z",
    "request_type": "principal_join"
  }
]
```

### 5. Approve Principal Request (Admin Only)
```http
PUT /study-area/school-requests/{request_id}/approve-principal
```
**Purpose:** Approve a principal request
**Authentication:** Admin role required
**Success Response:**
```json
{
  "message": "Successfully approved John Doe as principal of Green Springs High School",
  "school_name": "Green Springs High School",
  "principal_name": "John Doe",
  "approved_by": 2
}
```

### 6. Reject Principal Request (Admin Only)
```http
PUT /study-area/school-requests/{request_id}/reject-principal
```
**Purpose:** Reject a principal request
**Authentication:** Admin role required
**Query Parameter:** `rejection_reason` (string)
**Success Response:**
```json
{
  "message": "Principal request rejected",
  "school_name": "Green Springs High School",
  "reason": "School already has sufficient leadership",
  "rejected_by": 2
}
```

## 🔄 Updated User Status Endpoint

The `/study-area/user/status` endpoint now includes new available actions:

```json
{
  "available_actions": [
    {
      "action": "request_teacher_direct",
      "description": "Request to join a school as a teacher by selecting from available schools",
      "endpoint": "/join-school/request-teacher"
    },
    {
      "action": "request_principal_direct", 
      "description": "Request to become principal of an existing school",
      "endpoint": "/join-school/request-principal"
    }
  ]
}
```

## 🎯 User Workflows

### Teacher Joining Workflow
```
1. Login → 2. GET /schools/available → 3. Select School → 
4. POST /join-school/request-teacher → 5. ✅ Auto-approved (if school has principal)
```

### Principal Joining Workflow
```
1. Login → 2. GET /schools/available → 3. Select School → 
4. POST /join-school/request-principal → 5. Wait for Admin Review → 
6. Admin approves → 7. ✅ Becomes Principal
```

### Admin Review Workflow
```
1. GET /school-requests/principal-pending → 2. Review Requests → 
3. PUT /approve-principal OR PUT /reject-principal
```

## 🔧 Validation Rules

### Teacher Join Request:
- ✅ User must be logged in
- ✅ Email must match user's registered email
- ✅ School must exist and have a principal
- ✅ User cannot already be a teacher at that school
- ✅ Auto-assigns teacher role if user doesn't have it

### Principal Join Request:
- ✅ User must be logged in
- ✅ Email must match user's registered email
- ✅ School must exist
- ✅ School must NOT already have a principal
- ✅ User cannot have pending principal request for same school
- ✅ Requires admin approval

### Admin Actions:
- ✅ Only admins can view/approve/reject principal requests
- ✅ Can only approve if school still has no principal
- ✅ Auto-assigns principal role when approved

## 🎨 Frontend Integration Examples

### React Component for School Selection
```jsx
const SchoolSelector = ({ onSchoolSelect, userEmail }) => {
  const [schools, setSchools] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchAvailableSchools();
  }, []);

  const fetchAvailableSchools = async () => {
    try {
      const response = await fetch('/study-area/schools/available', {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const schoolsData = await response.json();
      setSchools(schoolsData);
    } catch (error) {
      console.error('Failed to fetch schools:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleJoinAsTeacher = async (schoolId) => {
    try {
      const response = await fetch('/study-area/join-school/request-teacher', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          school_id: schoolId,
          email: userEmail
        })
      });
      
      const result = await response.json();
      if (response.ok) {
        alert(`Success: ${result.message}`);
        onSchoolSelect(result);
      } else {
        alert(`Error: ${result.detail}`);
      }
    } catch (error) {
      alert('Failed to join school');
    }
  };

  const handleRequestPrincipal = async (schoolId) => {
    try {
      const response = await fetch('/study-area/join-school/request-principal', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          school_id: schoolId,
          email: userEmail
        })
      });
      
      const result = await response.json();
      if (response.ok) {
        alert(`Success: ${result.message}`);
        onSchoolSelect(result);
      } else {
        alert(`Error: ${result.detail}`);
      }
    } catch (error) {
      alert('Failed to request principal role');
    }
  };

  if (loading) return <div>Loading schools...</div>;

  return (
    <div className="school-selector">
      <h3>Available Schools</h3>
      {schools.map(school => (
        <div key={school.id} className="school-card">
          <h4>{school.name}</h4>
          <p>{school.address}</p>
          <p>Principal: {school.principal_name}</p>
          <p>Students: {school.total_students} | Teachers: {school.total_teachers}</p>
          
          <div className="actions">
            {school.principal_name !== "No Principal Assigned" ? (
              <button onClick={() => handleJoinAsTeacher(school.id)}>
                Join as Teacher
              </button>
            ) : (
              <button onClick={() => handleRequestPrincipal(school.id)}>
                Request to be Principal
              </button>
            )}
          </div>
        </div>
      ))}
    </div>
  );
};
```

### Admin Principal Approval Component
```jsx
const PrincipalApprovalPanel = () => {
  const [pendingRequests, setPendingRequests] = useState([]);

  useEffect(() => {
    fetchPendingRequests();
  }, []);

  const fetchPendingRequests = async () => {
    try {
      const response = await fetch('/study-area/school-requests/principal-pending', {
        headers: { 'Authorization': `Bearer ${adminToken}` }
      });
      const requests = await response.json();
      setPendingRequests(requests);
    } catch (error) {
      console.error('Failed to fetch requests:', error);
    }
  };

  const approveRequest = async (requestId) => {
    try {
      const response = await fetch(`/study-area/school-requests/${requestId}/approve-principal`, {
        method: 'PUT',
        headers: { 'Authorization': `Bearer ${adminToken}` }
      });
      
      if (response.ok) {
        alert('Principal request approved!');
        fetchPendingRequests(); // Refresh list
      }
    } catch (error) {
      alert('Failed to approve request');
    }
  };

  const rejectRequest = async (requestId) => {
    const reason = prompt('Enter rejection reason:');
    if (!reason) return;

    try {
      const response = await fetch(`/study-area/school-requests/${requestId}/reject-principal?rejection_reason=${encodeURIComponent(reason)}`, {
        method: 'PUT',
        headers: { 'Authorization': `Bearer ${adminToken}` }
      });
      
      if (response.ok) {
        alert('Principal request rejected');
        fetchPendingRequests(); // Refresh list
      }
    } catch (error) {
      alert('Failed to reject request');
    }
  };

  return (
    <div className="principal-approval-panel">
      <h3>Pending Principal Requests</h3>
      {pendingRequests.map(request => (
        <div key={request.id} className="request-card">
          <h4>{request.user_name} ({request.user_email})</h4>
          <p>Wants to be principal of: {request.school_name}</p>
          <p>Requested: {new Date(request.request_date).toLocaleDateString()}</p>
          
          <div className="actions">
            <button onClick={() => approveRequest(request.id)} className="approve">
              Approve
            </button>
            <button onClick={() => rejectRequest(request.id)} className="reject">
              Reject
            </button>
          </div>
        </div>
      ))}
    </div>
  );
};
```

## 📊 Database Changes

The system adds new fields to the `school_requests` table:
- `request_type`: "school_creation", "principal_join", "teacher_join"
- `target_school_id`: ID of existing school (for join requests)
- `created_date`: Timestamp of request creation

Run the migration script to update your database:
```bash
python migrate_direct_joining.py
```

## 🎯 Benefits of This System

1. **User-Friendly**: No need to remember/share access codes
2. **Self-Service**: Users can browse and select schools themselves
3. **Flexible**: Supports both access codes and direct joining
4. **Secure**: Email verification ensures users can only join with their registered email
5. **Admin Control**: Principal assignments still require admin approval
6. **Automatic**: Teacher joining is instant if school has principal

This system provides a much more intuitive way for users to join schools while maintaining proper security and approval workflows!
