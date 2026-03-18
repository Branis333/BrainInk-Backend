-- Migration script to update access_codes table for unique email-based codes
-- Run this script to update the database schema

-- First, drop the existing table if you want to start fresh (optional)
-- DROP TABLE IF EXISTS access_codes;

-- Or if you want to keep existing data, run these migration commands:

-- Add the new email column
ALTER TABLE access_codes
ADD COLUMN email VARCHAR;

-- Remove the old columns that are no longer needed
ALTER TABLE access_codes
DROP COLUMN expires_date;
ALTER TABLE access_codes
DROP COLUMN usage_count;
ALTER TABLE access_codes
DROP COLUMN max_usage;

-- Add the unique constraint for school_id, email, and code_type
ALTER TABLE access_codes
ADD CONSTRAINT uq_school_email_type UNIQUE (school_id, email, code_type);

-- Update any existing records (if needed)
-- UPDATE access_codes SET email = 'placeholder@example.com' WHERE email IS NULL;

-- Make email column NOT NULL
ALTER TABLE access_codes
ALTER COLUMN email
SET NOT NULL;

-- Optional: If you want to clean up and start fresh with access codes
-- TRUNCATE TABLE access_codes;

COMMIT;