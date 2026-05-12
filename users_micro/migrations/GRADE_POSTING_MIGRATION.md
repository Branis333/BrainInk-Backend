# Grade Posting Migration Guide

## Overview
This migration adds two new columns to the `grades` table to support the grade review and posting feature:
- `is_posted` (BOOLEAN DEFAULT FALSE) - Tracks whether a grade has been published to the student
- `posted_date` (TIMESTAMP DEFAULT NULL) - Records when the grade was posted

## Migration File
- **Location**: `migrations/migrate_add_grade_posting_columns.py`
- **Type**: Python migration using psycopg2
- **Compatible with**: PostgreSQL

## Prerequisites
1. Ensure `.env` file is configured with valid `DATABASE_URL`
2. Database connection should be working
3. Existing `grades` table should be present

## How to Run

### Option 1: Direct Python Execution
```bash
cd users_micro

# Run the migration
python migrations/migrate_add_grade_posting_columns.py
```

### Option 2: From Project Root
```bash
cd users_micro
python -m migrations.migrate_add_grade_posting_columns
```

### Option 3: Integrated with App Startup (Recommended)
Add to your app startup sequence in `main.py`:

```python
# In main.py, at the top after imports
import sys
from pathlib import Path

# Add migrations to path
sys.path.append(str(Path(__file__).parent / "migrations"))

# Import and run migration
from migrate_add_grade_posting_columns import add_grade_posting_columns

# Run migration on startup (or in a separate startup event)
@app.on_event("startup")
async def run_migrations():
    try:
        add_grade_posting_columns()
    except Exception as e:
        logger.warning(f"Migration check: {e}")
```

## What the Migration Does

1. **Connects to Database**: Uses `DATABASE_URL` environment variable
2. **Checks Existing Columns**: Verifies if columns already exist (idempotent)
3. **Adds Columns if Missing**:
   - `is_posted BOOLEAN DEFAULT FALSE`
   - `posted_date TIMESTAMP DEFAULT NULL`
4. **Displays Table Structure**: Shows final schema after migration
5. **Error Handling**: Rolls back on failure, proper error messages

## Expected Output

```
🔄 Starting migration to add grade posting columns to grades table...
📋 Existing columns in grades table: [...existing columns...]
➕ Adding column: is_posted - Whether grade has been shared with student
✅ Added column: is_posted
➕ Adding column: posted_date - When grade was posted to student
✅ Added column: posted_date
✅ Migration committed successfully!

📊 Final grades table structure:
   id: integer NOT NULL
   assignment_id: integer NOT NULL REFERENCES assignments(id)
   student_id: integer NOT NULL REFERENCES students(id)
   teacher_id: integer NOT NULL REFERENCES teachers(id)
   points_earned: integer NOT NULL
   feedback: text NULL
   graded_date: timestamp DEFAULT CURRENT_TIMESTAMP
   is_active: boolean NOT NULL DEFAULT true
   ai_generated: boolean DEFAULT false
   ai_confidence: integer NULL
   is_posted: boolean DEFAULT false
   posted_date: timestamp DEFAULT NULL

✨ Grade posting migration completed successfully!
```

## Idempotent Design
The migration is **idempotent**, meaning:
- It can be run multiple times safely
- If columns already exist, they won't be added again
- No data loss or duplication concerns

## Rollback (If Needed)

If you need to rollback, execute this SQL directly:

```sql
-- Connect to your database
ALTER TABLE grades DROP COLUMN IF EXISTS is_posted;
ALTER TABLE grades DROP COLUMN IF EXISTS posted_date;
```

## Data Impact

- **Existing Grades**: All existing grades will have:
  - `is_posted = FALSE` (grades not yet published)
  - `posted_date = NULL` (no posting date)
- **New Grades**: Created with same defaults
- **No Data Loss**: Only new columns added

## Verification

After running the migration, verify the columns exist:

```sql
SELECT column_name, data_type, column_default
FROM information_schema.columns
WHERE table_name = 'grades'
  AND column_name IN ('is_posted', 'posted_date')
ORDER BY ordinal_position;
```

Should return:
```
 column_name |  data_type  |      column_default
-------------+-------------+--------------------
 is_posted   | boolean     | false
 posted_date | timestamp   |
```

## Integration with Application

The new columns are already integrated in:
- **Model**: `models/study_area_models.py` - Grade class
- **Schemas**: `schemas/assignments_schemas.py` - GradeResponse, PostGradesRequest, PostGradesResponse
- **API Endpoint**: `Endpoints/academic_management.py` - POST `/grades/post`
- **Service**: `src/services/gradesAssignmentsService.ts` - postGrades methods
- **Component**: `src/components/teacher/UploadAnalyze.tsx` - handlePostGrades function

No additional configuration needed after running this migration!
