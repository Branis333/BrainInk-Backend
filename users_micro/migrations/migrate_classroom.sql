-- Migration script to update classroom table without losing data
-- Run this in your PostgreSQL/Supabase SQL editor

-- Step 1: Add new columns to classroom table
ALTER TABLE classrooms ADD COLUMN IF NOT EXISTS description VARCHAR;
ALTER TABLE classrooms ADD COLUMN IF NOT EXISTS capacity INTEGER DEFAULT 30;
ALTER TABLE classrooms ADD COLUMN IF NOT EXISTS location VARCHAR;

-- Step 2: Update existing records to have default capacity if needed
UPDATE classrooms SET capacity = 30 WHERE capacity IS NULL;

-- Step 3: Verify the migration
SELECT 
    column_name, 
    data_type, 
    is_nullable, 
    column_default 
FROM information_schema.columns 
WHERE table_name = 'classrooms' 
ORDER BY ordinal_position;

-- Step 4: Check that data is preserved
SELECT COUNT(*) as total_classrooms FROM classrooms;

-- Step 5: View sample of updated records
SELECT 
    id, 
    name, 
    description, 
    capacity, 
    location, 
    school_id, 
    teacher_id,
    created_date,
    is_active
FROM classrooms 
LIMIT 5;
