#!/usr/bin/env python3
"""
Comprehensive Migration Script for Backend-Frontend Compatibility
Updates database tables to ensure compatibility with the updated API interfaces
"""

import os
import sys
from pathlib import Path
from datetime import datetime
import psycopg2
from psycopg2 import sql
from urllib.parse import urlparse
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def get_database_connection():
    """Get database connection from environment"""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL environment variable not set")
    
    # Parse DATABASE_URL
    parsed = urlparse(database_url)
    
    conn = psycopg2.connect(
        host=parsed.hostname,
        port=parsed.port or 5432,
        database=parsed.path[1:],  # Remove leading slash
        user=parsed.username,
        password=parsed.password,
        sslmode='require'
    )
    return conn

def check_table_exists(cursor, table_name):
    """Check if a table exists"""
    cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = %s
        );
    """, (table_name,))
    return cursor.fetchone()[0]

def check_column_exists(cursor, table_name, column_name):
    """Check if a column exists in a table"""
    cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.columns 
            WHERE table_name = %s AND column_name = %s
        );
    """, (table_name, column_name))
    return cursor.fetchone()[0]

def get_table_columns(cursor, table_name):
    """Get all columns for a table with their properties"""
    cursor.execute("""
        SELECT column_name, data_type, is_nullable, column_default, character_maximum_length
        FROM information_schema.columns 
        WHERE table_name = %s
        ORDER BY ordinal_position
    """, (table_name,))
    return cursor.fetchall()

def add_column_if_missing(cursor, table_name, column_name, column_definition, description=""):
    """Add a column if it doesn't exist"""
    if not check_column_exists(cursor, table_name, column_name):
        print(f"➕ Adding {table_name}.{column_name} - {description}")
        alter_query = sql.SQL("ALTER TABLE {} ADD COLUMN {} {}").format(
            sql.Identifier(table_name),
            sql.Identifier(column_name),
            sql.SQL(column_definition)
        )
        cursor.execute(alter_query)
        print(f"✅ Added {table_name}.{column_name}")
        return True
    else:
        print(f"✅ {table_name}.{column_name} already exists")
        return False

def update_column_if_needed(cursor, table_name, column_name, new_definition, description=""):
    """Update column definition if needed"""
    print(f"🔄 Checking {table_name}.{column_name} - {description}")
    # Note: This is a basic implementation. In production, you'd want more sophisticated type checking
    return False

def migrate_courses_table(cursor):
    """Ensure as_courses table has all required columns for Course model"""
    print("\n📋 MIGRATING AS_COURSES TABLE")
    print("=" * 50)
    
    if not check_table_exists(cursor, 'as_courses'):
        print("❌ as_courses table does not exist!")
        return False
    
    changes_made = False
    
    # Core course fields (should already exist)
    core_columns = [
        ('title', 'VARCHAR(200) NOT NULL', 'Course title'),
        ('subject', 'VARCHAR(100) NOT NULL', 'Subject area'),
        ('description', 'TEXT', 'Course description'),
        ('age_min', 'INTEGER NOT NULL DEFAULT 3', 'Minimum age'),
        ('age_max', 'INTEGER NOT NULL DEFAULT 16', 'Maximum age'),
        ('difficulty_level', 'VARCHAR(20) NOT NULL DEFAULT \'beginner\'', 'Difficulty level'),
        ('created_by', 'INTEGER NOT NULL', 'Creator user ID'),
        ('is_active', 'BOOLEAN DEFAULT TRUE', 'Active status'),
        ('created_at', 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP', 'Creation timestamp'),
        ('updated_at', 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP', 'Update timestamp')
    ]
    
    # Enhanced course structure fields (may be missing)
    enhanced_columns = [
        ('total_weeks', 'INTEGER NOT NULL DEFAULT 8', 'Total duration in weeks'),
        ('blocks_per_week', 'INTEGER NOT NULL DEFAULT 2', 'Number of blocks per week'),
        ('textbook_source', 'TEXT', 'Source textbook information'),
        ('textbook_content', 'TEXT', 'Original textbook content'),
        ('generated_by_ai', 'BOOLEAN DEFAULT FALSE', 'Whether course was AI-generated')
    ]
    
    # Check and add enhanced columns
    for column_name, definition, description in enhanced_columns:
        if add_column_if_missing(cursor, 'as_courses', column_name, definition, description):
            changes_made = True
    
    return changes_made

def migrate_course_blocks_table(cursor):
    """Ensure as_course_blocks table exists and has required columns"""
    print("\n📋 MIGRATING AS_COURSE_BLOCKS TABLE")
    print("=" * 50)
    
    if not check_table_exists(cursor, 'as_course_blocks'):
        print("❌ as_course_blocks table does not exist!")
        return False
    
    changes_made = False
    
    # Required columns for CourseBlock model
    required_columns = [
        ('course_id', 'INTEGER NOT NULL REFERENCES as_courses(id)', 'Foreign key to course'),
        ('week', 'INTEGER NOT NULL', 'Week number'),
        ('block_number', 'INTEGER NOT NULL', 'Block number within week'),
        ('title', 'VARCHAR(200) NOT NULL', 'Block title'),
        ('description', 'TEXT', 'Block description'),
        ('learning_objectives', 'JSON', 'Learning objectives as JSON'),
        ('content', 'TEXT', 'Detailed lesson content'),
        ('duration_minutes', 'INTEGER NOT NULL DEFAULT 45', 'Duration in minutes'),
        ('resources', 'JSON', 'Links to resources as JSON'),
        ('is_active', 'BOOLEAN DEFAULT TRUE', 'Active status'),
        ('created_at', 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP', 'Creation timestamp'),
        ('updated_at', 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP', 'Update timestamp')
    ]
    
    for column_name, definition, description in required_columns:
        if add_column_if_missing(cursor, 'as_course_blocks', column_name, definition, description):
            changes_made = True
    
    return changes_made

def migrate_study_sessions_table(cursor):
    """Ensure as_study_sessions table supports simplified mark-done workflow"""
    print("\n📋 MIGRATING AS_STUDY_SESSIONS TABLE")
    print("=" * 50)
    
    if not check_table_exists(cursor, 'as_study_sessions'):
        print("❌ as_study_sessions table does not exist!")
        return False
    
    changes_made = False
    
    # Required columns for mark-done workflow
    required_columns = [
        ('user_id', 'INTEGER NOT NULL', 'Student user ID'),
        ('course_id', 'INTEGER NOT NULL REFERENCES as_courses(id)', 'Course foreign key'),
        ('lesson_id', 'INTEGER REFERENCES as_course_lessons(id)', 'Lesson foreign key (nullable)'),
        ('block_id', 'INTEGER REFERENCES as_course_blocks(id)', 'Block foreign key (nullable)'),
        ('started_at', 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP', 'Session start time'),
        ('ended_at', 'TIMESTAMP', 'Session end time'),
        ('duration_minutes', 'INTEGER', 'Session duration'),
        ('ai_score', 'FLOAT', 'AI-generated score (0-100)'),
        ('ai_feedback', 'TEXT', 'AI feedback text'),
        ('ai_recommendations', 'TEXT', 'AI recommendations'),
        ('status', 'VARCHAR(20) NOT NULL DEFAULT \'pending\'', 'Session status: pending, in_progress, completed'),
        ('completion_percentage', 'FLOAT NOT NULL DEFAULT 0.0', 'Completion percentage'),
        ('marked_done_at', 'TIMESTAMP', 'When marked as done'),
        ('created_at', 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP', 'Creation timestamp'),
        ('updated_at', 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP', 'Update timestamp')
    ]
    
    for column_name, definition, description in required_columns:
        if add_column_if_missing(cursor, 'as_study_sessions', column_name, definition, description):
            changes_made = True
    
    return changes_made

def migrate_student_assignments_table(cursor):
    """Ensure as_student_assignments table supports assignment retry system"""
    print("\n📋 MIGRATING AS_STUDENT_ASSIGNMENTS TABLE")
    print("=" * 50)
    
    if not check_table_exists(cursor, 'as_student_assignments'):
        print("❌ as_student_assignments table does not exist!")
        return False
    
    changes_made = False
    
    # Required columns for assignment system with retry support
    required_columns = [
        ('user_id', 'INTEGER NOT NULL', 'Student user ID'),
        ('assignment_id', 'INTEGER NOT NULL REFERENCES as_course_assignments(id)', 'Assignment foreign key'),
        ('course_id', 'INTEGER NOT NULL REFERENCES as_courses(id)', 'Course foreign key'),
        ('assigned_at', 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP', 'Assignment date'),
        ('due_date', 'TIMESTAMP NOT NULL', 'Due date'),
        ('submitted_at', 'TIMESTAMP', 'Submission date'),
        ('status', 'VARCHAR(20) NOT NULL DEFAULT \'assigned\'', 'Status: assigned, submitted, graded, overdue, passed, needs_retry, failed'),
        ('submission_file_path', 'VARCHAR(500)', 'Path to submission file'),
        ('submission_content', 'TEXT', 'Text submission content'),
        ('grade', 'FLOAT', 'Final grade (0-100)'),
        ('ai_grade', 'FLOAT', 'AI-generated grade'),
        ('manual_grade', 'FLOAT', 'Manual override grade'),
        ('feedback', 'TEXT', 'Feedback text'),
        ('created_at', 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP', 'Creation timestamp'),
        ('updated_at', 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP', 'Update timestamp')
    ]
    
    for column_name, definition, description in required_columns:
        if add_column_if_missing(cursor, 'as_student_assignments', column_name, definition, description):
            changes_made = True
    
    return changes_made

def migrate_ai_submissions_table(cursor):
    """Ensure as_ai_submissions table supports assignment retry with 24-hour windows"""
    print("\n📋 MIGRATING AS_AI_SUBMISSIONS TABLE")
    print("=" * 50)
    
    if not check_table_exists(cursor, 'as_ai_submissions'):
        print("❌ as_ai_submissions table does not exist!")
        return False
    
    changes_made = False
    
    # Required columns for AI submissions with assignment retry support
    required_columns = [
        ('user_id', 'INTEGER NOT NULL', 'Student user ID'),
        ('course_id', 'INTEGER NOT NULL REFERENCES as_courses(id)', 'Course foreign key'),
        ('lesson_id', 'INTEGER REFERENCES as_course_lessons(id)', 'Lesson foreign key (nullable)'),
        ('block_id', 'INTEGER REFERENCES as_course_blocks(id)', 'Block foreign key (nullable)'),
        ('session_id', 'INTEGER NOT NULL REFERENCES as_study_sessions(id)', 'Study session foreign key'),
        ('assignment_id', 'INTEGER REFERENCES as_course_assignments(id)', 'Assignment foreign key (nullable)'),
        ('submission_type', 'VARCHAR(50) NOT NULL', 'Type: homework, quiz, practice, assessment'),
        ('original_filename', 'VARCHAR(255)', 'Original uploaded filename'),
        ('file_path', 'VARCHAR(500)', 'Path to uploaded file'),
        ('file_type', 'VARCHAR(50)', 'File type: pdf, image, text'),
        ('ai_processed', 'BOOLEAN DEFAULT FALSE', 'Whether AI processing is complete'),
        ('ai_score', 'FLOAT', 'AI score (0-100)'),
        ('ai_feedback', 'TEXT', 'AI feedback'),
        ('ai_corrections', 'TEXT', 'AI suggested corrections'),
        ('ai_strengths', 'TEXT', 'AI identified strengths'),
        ('ai_improvements', 'TEXT', 'AI suggested improvements'),
        ('requires_review', 'BOOLEAN DEFAULT FALSE', 'Needs manual review'),
        ('reviewed_by', 'INTEGER', 'Reviewer user ID'),
        ('manual_score', 'FLOAT', 'Manual score override'),
        ('manual_feedback', 'TEXT', 'Manual feedback'),
        ('submitted_at', 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP', 'Submission timestamp'),
        ('processed_at', 'TIMESTAMP', 'AI processing completion time'),
        ('reviewed_at', 'TIMESTAMP', 'Manual review timestamp')
    ]
    
    for column_name, definition, description in required_columns:
        if add_column_if_missing(cursor, 'as_ai_submissions', column_name, definition, description):
            changes_made = True
    
    return changes_made

def migrate_course_assignments_table(cursor):
    """Ensure as_course_assignments table exists with proper structure"""
    print("\n📋 MIGRATING AS_COURSE_ASSIGNMENTS TABLE")
    print("=" * 50)
    
    if not check_table_exists(cursor, 'as_course_assignments'):
        print("❌ as_course_assignments table does not exist!")
        return False
    
    changes_made = False
    
    # Required columns for course assignments
    required_columns = [
        ('course_id', 'INTEGER NOT NULL REFERENCES as_courses(id)', 'Course foreign key'),
        ('title', 'VARCHAR(200) NOT NULL', 'Assignment title'),
        ('description', 'TEXT NOT NULL', 'Assignment description'),
        ('assignment_type', 'VARCHAR(50) NOT NULL', 'Type: homework, quiz, project, assessment'),
        ('instructions', 'TEXT', 'Assignment instructions'),
        ('duration_minutes', 'INTEGER NOT NULL DEFAULT 30', 'Expected duration'),
        ('points', 'INTEGER NOT NULL DEFAULT 100', 'Total points possible'),
        ('rubric', 'TEXT', 'Grading rubric'),
        ('week_assigned', 'INTEGER', 'Week to assign'),
        ('block_id', 'INTEGER REFERENCES as_course_blocks(id)', 'Related block'),
        ('due_days_after_assignment', 'INTEGER NOT NULL DEFAULT 7', 'Days until due'),
        ('submission_format', 'VARCHAR(100)', 'Expected submission format'),
        ('learning_outcomes', 'JSON', 'Learning outcomes as JSON'),
        ('generated_by_ai', 'BOOLEAN DEFAULT FALSE', 'AI-generated assignment'),
        ('is_active', 'BOOLEAN DEFAULT TRUE', 'Active status'),
        ('created_at', 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP', 'Creation timestamp'),
        ('updated_at', 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP', 'Update timestamp')
    ]
    
    for column_name, definition, description in required_columns:
        if add_column_if_missing(cursor, 'as_course_assignments', column_name, definition, description):
            changes_made = True
    
    return changes_made

def migrate_student_progress_table(cursor):
    """Ensure as_student_progress table exists for progress tracking"""
    print("\n📋 MIGRATING AS_STUDENT_PROGRESS TABLE")
    print("=" * 50)
    
    if not check_table_exists(cursor, 'as_student_progress'):
        print("❌ as_student_progress table does not exist!")
        return False
    
    changes_made = False
    
    # Required columns for student progress tracking
    required_columns = [
        ('user_id', 'INTEGER NOT NULL', 'Student user ID'),
        ('course_id', 'INTEGER NOT NULL REFERENCES as_courses(id)', 'Course foreign key'),
        ('lessons_completed', 'INTEGER NOT NULL DEFAULT 0', 'Number of lessons completed'),
        ('total_lessons', 'INTEGER NOT NULL DEFAULT 0', 'Total lessons in course'),
        ('completion_percentage', 'FLOAT NOT NULL DEFAULT 0.0', 'Overall completion percentage'),
        ('blocks_completed', 'INTEGER NOT NULL DEFAULT 0', 'Number of blocks completed'),
        ('total_blocks', 'INTEGER NOT NULL DEFAULT 0', 'Total blocks in course'),
        ('average_score', 'FLOAT', 'Average assignment score'),
        ('total_study_time', 'INTEGER NOT NULL DEFAULT 0', 'Total study time in minutes'),
        ('sessions_count', 'INTEGER NOT NULL DEFAULT 0', 'Number of study sessions'),
        ('started_at', 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP', 'Course start date'),
        ('last_activity', 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP', 'Last activity date'),
        ('completed_at', 'TIMESTAMP', 'Course completion date'),
        ('created_at', 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP', 'Creation timestamp'),
        ('updated_at', 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP', 'Update timestamp')
    ]
    
    for column_name, definition, description in required_columns:
        if add_column_if_missing(cursor, 'as_student_progress', column_name, definition, description):
            changes_made = True
    
    return changes_made

def check_indexes_and_constraints(cursor):
    """Check and create necessary indexes and constraints"""
    print("\n📋 CHECKING INDEXES AND CONSTRAINTS")
    print("=" * 50)
    
    indexes_to_create = [
        # Performance indexes for common queries
        ("idx_study_sessions_user_course", "as_study_sessions", ["user_id", "course_id"]),
        ("idx_study_sessions_block", "as_study_sessions", ["block_id"]),
        ("idx_study_sessions_status", "as_study_sessions", ["status"]),
        ("idx_student_assignments_user", "as_student_assignments", ["user_id"]),
        ("idx_student_assignments_course", "as_student_assignments", ["course_id"]),
        ("idx_student_assignments_status", "as_student_assignments", ["status"]),
        ("idx_ai_submissions_user_course", "as_ai_submissions", ["user_id", "course_id"]),
        ("idx_ai_submissions_assignment", "as_ai_submissions", ["assignment_id"]),
        ("idx_ai_submissions_submitted_at", "as_ai_submissions", ["submitted_at"]),
        ("idx_course_blocks_course_week", "as_course_blocks", ["course_id", "week", "block_number"])
    ]
    
    for index_name, table_name, columns in indexes_to_create:
        # Check if index exists
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM pg_indexes 
                WHERE indexname = %s
            );
        """, (index_name,))
        
        if not cursor.fetchone()[0]:
            print(f"➕ Creating index {index_name}")
            columns_str = ", ".join(columns)
            create_index_query = f"""
                CREATE INDEX {index_name} ON {table_name} ({columns_str})
            """
            cursor.execute(create_index_query)
            print(f"✅ Created index {index_name}")
        else:
            print(f"✅ Index {index_name} already exists")

def print_table_summary(cursor):
    """Print summary of all afterschool tables"""
    print("\n📊 AFTERSCHOOL TABLES SUMMARY")
    print("=" * 80)
    
    tables = [
        'as_courses',
        'as_course_blocks', 
        'as_course_lessons',
        'as_course_assignments',
        'as_study_sessions',
        'as_student_assignments',
        'as_ai_submissions',
        'as_student_progress'
    ]
    
    for table_name in tables:
        if check_table_exists(cursor, table_name):
            columns = get_table_columns(cursor, table_name)
            print(f"\n🗃️  {table_name.upper()}: {len(columns)} columns")
            for col_name, data_type, nullable, default, max_length in columns:
                null_str = "NULL" if nullable == "YES" else "NOT NULL"
                length_str = f"({max_length})" if max_length else ""
                default_str = f" DEFAULT {default}" if default else ""
                print(f"   • {col_name}: {data_type}{length_str} {null_str}{default_str}")
        else:
            print(f"\n❌ {table_name.upper()}: TABLE MISSING!")

def main():
    """Main migration function"""
    print("🚀 STARTING COMPREHENSIVE DATABASE MIGRATION")
    print("=" * 80)
    print("📅 Migration Date:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("🎯 Purpose: Ensure backend-frontend compatibility")
    print("=" * 80)
    
    conn = None
    cursor = None
    
    try:
        # Connect to database
        conn = get_database_connection()
        cursor = conn.cursor()
        print("✅ Connected to database successfully")
        
        # Track changes
        total_changes = 0
        
        # Run migrations
        migrations = [
            ("Courses", migrate_courses_table),
            ("Course Blocks", migrate_course_blocks_table),
            ("Course Assignments", migrate_course_assignments_table),
            ("Study Sessions", migrate_study_sessions_table),
            ("Student Assignments", migrate_student_assignments_table),
            ("AI Submissions", migrate_ai_submissions_table),
            ("Student Progress", migrate_student_progress_table)
        ]
        
        for name, migration_func in migrations:
            print(f"\n🔄 Running {name} migration...")
            if migration_func(cursor):
                total_changes += 1
        
        # Create indexes and constraints
        check_indexes_and_constraints(cursor)
        
        # Print summary
        print_table_summary(cursor)
        
        # Commit all changes
        conn.commit()
        
        print(f"\n🎉 MIGRATION COMPLETED SUCCESSFULLY!")
        print(f"✅ Database schema is now compatible with updated API interfaces")
        print(f"📊 Tables checked: {len(migrations)}")
        print(f"🔄 Tables modified: {total_changes}")
        print(f"💾 All changes committed to database")
        
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"\n❌ MIGRATION FAILED: {str(e)}")
        print(f"🔙 All changes have been rolled back")
        raise e
        
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
        print("\n🔐 Database connection closed")

if __name__ == "__main__":
    main()