# 🚀 Quick Migration Guide: Access Codes → Email Invitations

## Summary of Changes

The BrainInk backend has been completely refactored to replace the legacy access code system with a modern email-based invitation system. This guide helps frontend developers quickly understand what needs to be changed.

## ⚡ Quick Reference

### ❌ Old System (Remove These)
```javascript
// OLD - Remove these API calls
POST /study-area/join-school-by-code
POST /study-area/generate-access-code  
POST /study-area/verify-access-code

// OLD - Remove these UI components
<AccessCodeInput />
<GenerateCodeButton />
<CodeVerificationForm />
```

### ✅ New System (Add These)
```javascript
// NEW - Use these API calls instead
POST /study-area/invitations/create          // Single invitation
POST /study-area/invitations/bulk-create     // Bulk invitations
POST /study-area/join-school-by-email        // Join school
GET  /study-area/invitations/available       // Check invitations

// NEW - Add these UI components
<InvitationManager />
<BulkInviteUpload />
<EmailJoinForm />
<AvailableInvitations />
```

## 🔄 API Endpoint Mapping

| Old Endpoint | New Endpoint | Notes |
|--------------|--------------|-------|
| `POST /study-area/join-school-by-code` | `POST /study-area/join-school-by-email` | Now uses email instead of code |
| `POST /study-area/generate-access-code` | `POST /study-area/invitations/create` | Principals invite by email |
| `GET /study-area/verify-access-code` | `GET /study-area/invitations/available` | Users check their invitations |
| N/A | `POST /study-area/invitations/bulk-create` | New bulk invitation feature |
| N/A | `GET /study-area/invitations/school/{id}` | New invitation management |

## 📱 UI Component Updates

### 1. Principal Dashboard
```jsx
// OLD
function PrincipalDashboard() {
  return (
    <div>
      <GenerateAccessCodeButton />
      <ShareCodeInstructions />
    </div>
  );
}

// NEW  
function PrincipalDashboard() {
  return (
    <div>
      <InviteTeacherForm />
      <InviteStudentForm />
      <BulkInviteUpload />
      <InvitationsList />
    </div>
  );
}
```

### 2. Teacher/Student Joining
```jsx
// OLD
function JoinSchool() {
  const [accessCode, setAccessCode] = useState('');
  
  const handleJoin = async () => {
    await api.joinByCode(accessCode);
  };
  
  return (
    <input 
      value={accessCode}
      onChange={(e) => setAccessCode(e.target.value)}
      placeholder="Enter access code"
    />
  );
}

// NEW
function JoinSchool() {
  const [invitations, setInvitations] = useState([]);
  
  useEffect(() => {
    loadAvailableInvitations();
  }, []);
  
  const loadAvailableInvitations = async () => {
    const invites = await api.getAvailableInvitations();
    setInvitations(invites);
  };
  
  const handleJoin = async (userEmail) => {
    await api.joinByEmail(userEmail);
  };
  
  return (
    <div>
      <h3>Available Invitations</h3>
      {invitations.map(invite => (
        <InvitationCard key={invite.id} invitation={invite} onJoin={handleJoin} />
      ))}
    </div>
  );
}
```

## 🔧 Required Frontend Changes

### 1. Remove Access Code Logic
- [ ] Delete access code input forms
- [ ] Remove code generation buttons
- [ ] Remove code sharing instructions
- [ ] Remove code validation logic

### 2. Add Invitation Management
- [ ] Create invitation forms for principals
- [ ] Add bulk invitation upload (CSV/email list)
- [ ] Add invitation status tracking
- [ ] Add invitation cancellation

### 3. Update User Flows
- [ ] Replace "Enter Code" with "Check Invitations"
- [ ] Add email-based joining workflow
- [ ] Update onboarding instructions
- [ ] Update error messages

### 4. Update State Management
```javascript
// OLD - Remove these state variables
const [accessCode, setAccessCode] = useState('');
const [isCodeValid, setIsCodeValid] = useState(false);

// NEW - Add these state variables  
const [availableInvitations, setAvailableInvitations] = useState([]);
const [invitationEmails, setInvitationEmails] = useState([]);
const [bulkInviteFile, setBulkInviteFile] = useState(null);
```

## 🎯 New Features to Implement

### 1. Invitation Management Dashboard (Principals)
```jsx
function InvitationDashboard({ schoolId }) {
  const [invitations, setInvitations] = useState([]);
  const [newEmail, setNewEmail] = useState('');
  const [inviteType, setInviteType] = useState('teacher');
  
  const sendInvitation = async () => {
    await api.createInvitation(newEmail, inviteType, schoolId);
    loadInvitations(); // Refresh list
  };
  
  const cancelInvitation = async (invitationId) => {
    await api.cancelInvitation(invitationId);
    loadInvitations(); // Refresh list
  };
  
  return (
    <div>
      <form onSubmit={sendInvitation}>
        <input
          type="email"
          value={newEmail}
          onChange={(e) => setNewEmail(e.target.value)}
          placeholder="Email address"
          required
        />
        <select value={inviteType} onChange={(e) => setInviteType(e.target.value)}>
          <option value="teacher">Teacher</option>
          <option value="student">Student</option>
        </select>
        <button type="submit">Send Invitation</button>
      </form>
      
      <InvitationsList 
        invitations={invitations}
        onCancel={cancelInvitation}
      />
    </div>
  );
}
```

### 2. Bulk Invitation Upload
```jsx
function BulkInviteUpload({ schoolId, inviteType }) {
  const [emails, setEmails] = useState('');
  
  const handleBulkInvite = async () => {
    const emailList = emails.split('\n').filter(email => email.trim());
    const result = await api.createBulkInvitations(emailList, inviteType, schoolId);
    
    // Show results
    console.log(`Sent: ${result.total_sent}, Failed: ${result.total_failed}`);
  };
  
  return (
    <div>
      <textarea
        value={emails}
        onChange={(e) => setEmails(e.target.value)}
        placeholder="Enter email addresses (one per line)"
        rows={10}
      />
      <button onClick={handleBulkInvite}>Send Bulk Invitations</button>
    </div>
  );
}
```

### 3. Available Invitations Check
```jsx
function AvailableInvitations() {
  const [invitations, setInvitations] = useState([]);
  const [loading, setLoading] = useState(true);
  
  useEffect(() => {
    loadInvitations();
  }, []);
  
  const loadInvitations = async () => {
    try {
      const data = await api.getAvailableInvitations();
      setInvitations(data);
    } catch (error) {
      console.error('Failed to load invitations:', error);
    } finally {
      setLoading(false);
    }
  };
  
  const joinSchool = async (email) => {
    try {
      await api.joinSchoolByEmail(email);
      // Refresh invitations after joining
      loadInvitations();
    } catch (error) {
      console.error('Failed to join school:', error);
    }
  };
  
  if (loading) return <div>Loading invitations...</div>;
  
  if (invitations.length === 0) {
    return <div>No pending invitations found.</div>;
  }
  
  return (
    <div>
      <h3>Your Invitations</h3>
      {invitations.map(invitation => (
        <div key={invitation.id} className="invitation-card">
          <h4>{invitation.school_name}</h4>
          <p>Role: {invitation.invitation_type}</p>
          <p>Invited: {new Date(invitation.invited_date).toLocaleDateString()}</p>
          <button onClick={() => joinSchool(invitation.email)}>
            Join as {invitation.invitation_type}
          </button>
        </div>
      ))}
    </div>
  );
}
```

## 🧪 Testing Strategy

### 1. Unit Tests
```javascript
// Test invitation API calls
describe('Invitation API', () => {
  test('should create single invitation', async () => {
    const result = await api.createInvitation('test@example.com', 'teacher', 1);
    expect(result.email).toBe('test@example.com');
  });
  
  test('should handle bulk invitations', async () => {
    const emails = ['teacher1@test.com', 'teacher2@test.com'];
    const result = await api.createBulkInvitations(emails, 'teacher', 1);
    expect(result.total_sent).toBeGreaterThan(0);
  });
});
```

### 2. Integration Tests
```javascript
// Test complete workflow
describe('Invitation Workflow', () => {
  test('principal can invite and user can join', async () => {
    // Principal creates invitation
    await api.principalLogin('principal@test.com', 'password');
    const invitation = await api.createInvitation('teacher@test.com', 'teacher', 1);
    
    // Teacher joins school
    await api.teacherLogin('teacher@test.com', 'password');
    const result = await api.joinSchoolByEmail('teacher@test.com');
    
    expect(result.role_assigned).toBe('teacher');
  });
});
```

## 📋 Deployment Checklist

- [ ] Remove all access code related components
- [ ] Implement invitation management UI
- [ ] Add bulk invitation functionality
- [ ] Update user onboarding flow
- [ ] Test principal invitation workflow
- [ ] Test teacher/student joining workflow
- [ ] Update error handling
- [ ] Update user documentation
- [ ] Test with real email addresses
- [ ] Deploy to staging environment
- [ ] User acceptance testing
- [ ] Deploy to production

## 🚨 Breaking Changes Alert

### Immediate Action Required
1. **API Endpoints:** All access code endpoints are removed
2. **User Flow:** Users can no longer join with codes
3. **Principal Workflow:** Principals must use email invitations
4. **Authentication:** Separate login endpoints for principals/teachers

### Backward Compatibility
❌ **No backward compatibility** - this is a complete system replacement

### Migration Timeline
1. **Phase 1:** Update backend (✅ Complete)
2. **Phase 2:** Update frontend (📍 You are here)
3. **Phase 3:** User training and documentation
4. **Phase 4:** Go live with new system

## 📞 Need Help?

- Review `FRONTEND_INTEGRATION_COMPLETE.md` for detailed API documentation
- Check backend logs for debugging
- Test endpoints using the provided examples
- Refer to the React/TypeScript examples in the complete guide

The new system is more secure, user-friendly, and provides better management capabilities. The email-based workflow eliminates manual code sharing and provides proper audit trails for school membership.
