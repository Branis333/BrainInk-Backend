-- SQL commands to migrate from single role to multiple roles
-- Run these commands in your PostgreSQL database

-- 1. Create the user_roles junction table
CREATE TABLE user_roles (
  user_id INTEGER NOT NULL
  , role_id INTEGER NOT NULL
  , PRIMARY KEY (user_id, role_id)
  , FOREIGN KEY (user_id) REFERENCES users(id)
  ON DELETE CASCADE
  , FOREIGN KEY (role_id) REFERENCES roles(id)
  ON DELETE CASCADE
);

-- 2. Migrate existing role_id data to user_roles table (if role_id column exists)
-- Insert existing user-role relationships into the junction table
INSERT INTO
  user_roles (user_id, role_id)
SELECT
  id
  , role_id
FROM
  users
WHERE
  role_id IS NOT NULL;

-- 3. (Optional) Add users without roles to have normal_user role
-- First, get the normal_user role id
-- Then insert for users who don't have any roles
INSERT INTO
  user_roles (user_id, role_id)
SELECT
  u.id
  , r.id
FROM
  users u
  CROSS JOIN roles r
WHERE
  r.name = 'normal_user'
  AND u.id NOT IN (
    SELECT
      user_id
    FROM
      user_roles
  );

-- 4. (Optional) Remove the old role_id column from users table
-- WARNING: Only do this after confirming the migration worked correctly
-- ALTER TABLE users DROP COLUMN role_id;

-- 5. Create indexes for better performance
CREATE INDEX idx_user_roles_user_id
ON user_roles(user_id);
CREATE INDEX idx_user_roles_role_id
ON user_roles(role_id);