# Updated Access Code System Documentation

## Overview
The access code system has been updated to provide unique, non-expiring access codes for each student and teacher based on their email address.

## Key Changes

### 1. Email-Based Unique Codes
- Each access code is now tied to a specific email address
- Principals must provide the email address when generating codes
- One code per email per school per role type (student/teacher)

### 2. No Expiration
- Access codes no longer have expiration dates
- Codes remain valid until used or manually deactivated
- No usage count limits

### 3. Reusable Codes
- Each code remains active and can be used multiple times
- Students and teachers can use the same code to sign up repeatedly
- Codes remain valid until manually deactivated by principals

## API Endpoints

### Generate Access Code
```
POST /access-codes/generate
```
**Body:**
```json
{
    "school_id": 1,
    "code_type": "student",  // or "teacher"
    "email": "student@example.com"
}
```

### Get Access Codes by Email
```
GET /access-codes/by-email/{email}
```
Returns all access codes for a specific email in the principal's school.

### Reactivate Access Code
```
PUT /access-codes/{code_id}/reactivate
```
Reactivates a deactivated access code.

### Deactivate Access Code
```
DELETE /access-codes/{code_id}
```
Deactivates an access code.

## Workflow

### For Principals:
1. Generate unique access codes for specific student/teacher emails
2. Share the code with the intended recipient
3. Monitor code usage and reactivate if needed

### For Students/Teachers:
1. Receive access code from principal
2. Use code to join school (code must match your email)
3. Code remains active and can be used again if needed

## Database Schema Changes

### AccessCode Table Updates:
- **Added:** `email` column (required)
- **Removed:** `expires_date`, `usage_count`, `max_usage`
- **Added:** Unique constraint on (school_id, email, code_type)

## Migration

Run the migration script `migrate_access_codes.sql` to update your database schema:

```sql
-- Add email column
ALTER TABLE access_codes ADD COLUMN email VARCHAR;

-- Remove old columns
ALTER TABLE access_codes DROP COLUMN expires_date;
ALTER TABLE access_codes DROP COLUMN usage_count;
ALTER TABLE access_codes DROP COLUMN max_usage;

-- Add unique constraint
ALTER TABLE access_codes ADD CONSTRAINT uq_school_email_type 
UNIQUE (school_id, email, code_type);

-- Make email NOT NULL
ALTER TABLE access_codes ALTER COLUMN email SET NOT NULL;
```

## Benefits

1. **Security:** Codes are tied to specific emails, preventing unauthorized use
2. **Simplicity:** No expiration management needed
3. **Uniqueness:** Each person gets their own code
4. **Reusability:** Codes can be used multiple times by the same person
5. **Flexibility:** Codes can be manually deactivated/reactivated if needed
6. **Tracking:** Easy to see which codes belong to which emails

## Error Handling

- **Duplicate Code Generation:** If a code for the same email/type exists, it will reactivate the existing one
- **Invalid Email:** Code must match the user's account email when joining
- **Already Joined:** Users cannot join the same school twice with the same role
- **Inactive Code:** Deactivated codes cannot be used until reactivated

## Security Considerations

- Access codes are unique and tied to specific emails
- Codes remain active after use and can be reused
- Only principals can generate codes for their schools
- Email validation ensures codes are used by the intended recipient
- Multiple signups with same code are prevented by checking existing school membership
