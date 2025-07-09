# BrainInk Backend - Multiple Roles System

## Overview

The system now supports **multiple roles per user**. Users can have any combination of roles simultaneously:
- normal_user
- student  
- teacher
- principal
- admin

## Database Changes

### New Structure
- **user_roles** junction table for many-to-many relationship
- Users can have multiple roles at once
- Role checking is now more flexible

### Migration Required
Run the SQL commands in `migrate_to_multiple_roles.sql` to update your database.

## Updated API Endpoints

### Role Management
- `POST /study-area/roles/assign` - Add a role to user (keeps existing roles)
- `DELETE /study-area/roles/remove` - Remove a specific role from user  
- `GET /study-area/users/{user_id}/roles` - Get all roles for a user
- `GET /study-area/roles/all` - Get all available roles
- `GET /study-area/users/by-role/{role_name}` - Get users with specific role

### Role Checking
The system now uses more flexible role checking:
- Users can have multiple roles simultaneously
- Endpoints check for specific required roles
- When joining schools, roles are **added** (not replaced)

## User Model Methods

```python
# Check if user has a role
user.has_role("admin")  # Returns True/False

# Add a role to user
user.add_role(role_object)

# Remove a role from user  
user.remove_role(role_object)

# Get all role names as strings
user.get_role_names()  # Returns ["admin", "teacher", etc.]
```

## Example Workflows

### 1. User becomes both Teacher and Principal
```python
# User starts as normal_user
# Admin assigns teacher role
POST /study-area/roles/assign?user_id=123&role_name=teacher

# Later, admin assigns principal role (user keeps teacher role)
POST /study-area/roles/assign?user_id=123&role_name=principal

# User now has: ["normal_user", "teacher", "principal"]
```

### 2. Student joins school, later becomes teacher
```python
# User joins as student
POST /study-area/join-school/student
# User now has: ["normal_user", "student"]

# Admin assigns teacher role
POST /study-area/roles/assign?user_id=123&role_name=teacher  
# User now has: ["normal_user", "student", "teacher"]
```

### 3. Remove specific role
```python
# Remove student role but keep teacher role
DELETE /study-area/roles/remove?user_id=123&role_name=student
# User now has: ["normal_user", "teacher"]
```

## Endpoint Access Control

### Flexible Role Checking
Some endpoints now accept users with **any** of multiple roles:

```python
# Example: Classroom creation
# Allows users with principal OR teacher role
ensure_user_has_any_role(db, user_id, [UserRole.principal, UserRole.teacher])
```

### Strict Role Checking  
Critical operations still require specific roles:

```python
# Only admins can assign roles
ensure_user_role(db, user_id, UserRole.admin)

# Only principals can generate access codes
ensure_user_role(db, user_id, UserRole.principal)
```

## Migration Steps

1. **Backup your database**
2. **Run migration SQL:**
   ```sql
   -- Run all commands in migrate_to_multiple_roles.sql
   ```
3. **Restart your server** to use updated models
4. **Test role assignments:**
   ```bash
   # Test the new endpoints
   python test_multiple_roles.py
   ```

## Benefits

✅ **Flexible Role Management**: Users can have multiple roles simultaneously  
✅ **Gradual Role Assignment**: Add roles without losing existing ones  
✅ **Real-world Scenarios**: Teachers can become principals, students can become teachers  
✅ **Backwards Compatible**: Existing single-role logic still works  
✅ **Enhanced Security**: More granular permission control  

## Example Use Cases

1. **Teacher-Principal**: User manages classrooms AND oversees school
2. **Student-Teacher**: Graduate student who teaches while studying  
3. **Admin-Principal**: System admin who also manages a school
4. **Multi-school Teacher**: Teacher at multiple schools (via multiple teacher roles)

The system is now much more flexible and mirrors real-world educational hierarchies!
