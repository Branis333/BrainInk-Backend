"""
Database Migration Script for After School System
Fix missing columns in courses and ai_submissions tables
"""

import os
import sys
from datetime import datetime
from sqlalchemy import create_engine, text, MetaData, inspect
from sqlalchemy.orm import sessionmaker

# Add the parent directory to sys.path to import db modules
sys.path.append(os.path.join(os.path.dirname(__file__)))

try:
    from users_micro.db.database import engine, SessionLocal
    print("✅ Using existing database configuration")
except ImportError:
    # Fallback database configuration
    DATABASE_URL = os.getenv(
        "DATABASE_URL", 
        "postgresql://postgres:password@localhost:5432/brainink"
    )
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    print("⚠️ Using fallback database configuration")

def get_db_session():
    """Get database session using SQLAlchemy"""
    try:
        session = SessionLocal()
        return session
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return None

def check_column_exists(session, table_name, column_name):
    """Check if a column exists in a table"""
    result = session.execute(text("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = :table_name AND column_name = :column_name
        );
    """), {"table_name": table_name, "column_name": column_name})
    return result.scalar()

def add_missing_course_columns(session):
    """Add missing columns to as_courses table"""
    print("🔧 Checking as_courses table...")
    
    columns_to_add = [
        ("total_weeks", "INTEGER NOT NULL DEFAULT 8"),
        ("blocks_per_week", "INTEGER NOT NULL DEFAULT 2"), 
        ("textbook_source", "TEXT"),
        ("textbook_content", "TEXT"),
        ("generated_by_ai", "BOOLEAN NOT NULL DEFAULT FALSE")
    ]
    
    for column_name, column_definition in columns_to_add:
        if not check_column_exists(session, 'as_courses', column_name):
            try:
                session.execute(text(f"ALTER TABLE as_courses ADD COLUMN {column_name} {column_definition};"))
                print(f"✅ Added column: as_courses.{column_name}")
            except Exception as e:
                print(f"❌ Error adding {column_name}: {e}")
        else:
            print(f"ℹ️ Column as_courses.{column_name} already exists")

def add_missing_ai_submissions_columns(session):
    """Add missing columns to as_ai_submissions table"""
    print("🔧 Checking as_ai_submissions table...")
    
    columns_to_add = [
        ("block_id", "INTEGER REFERENCES as_course_blocks(id)"),
        ("assignment_id", "INTEGER REFERENCES as_course_assignments(id)")
    ]
    
    for column_name, column_definition in columns_to_add:
        if not check_column_exists(session, 'as_ai_submissions', column_name):
            try:
                session.execute(text(f"ALTER TABLE as_ai_submissions ADD COLUMN {column_name} {column_definition};"))
                print(f"✅ Added column: as_ai_submissions.{column_name}")
            except Exception as e:
                print(f"❌ Error adding {column_name}: {e}")
        else:
            print(f"ℹ️ Column as_ai_submissions.{column_name} already exists")

def update_existing_course_data(session):
    """Update existing courses with default values"""
    print("📊 Updating existing course data...")
    
    try:
        # Update courses that have NULL values for the new columns
        session.execute(text("""
            UPDATE as_courses 
            SET total_weeks = 8 
            WHERE total_weeks IS NULL;
        """))
        
        session.execute(text("""
            UPDATE as_courses 
            SET blocks_per_week = 2 
            WHERE blocks_per_week IS NULL;
        """))
        
        session.execute(text("""
            UPDATE as_courses 
            SET generated_by_ai = FALSE 
            WHERE generated_by_ai IS NULL;
        """))
        
        print("✅ Updated existing course data with default values")
        
    except Exception as e:
        print(f"❌ Error updating course data: {e}")

def create_missing_tables(session):
    """Create any missing tables"""
    print("🏗️ Checking for missing tables...")
    
    # Check if as_course_blocks table exists
    result = session.execute(text("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables 
            WHERE table_name = 'as_course_blocks'
        );
    """))
    
    if not result.scalar():
        print("📦 Creating as_course_blocks table...")
        session.execute(text("""
            CREATE TABLE as_course_blocks (
                id SERIAL PRIMARY KEY,
                course_id INTEGER NOT NULL REFERENCES as_courses(id) ON DELETE CASCADE,
                week INTEGER NOT NULL,
                block_number INTEGER NOT NULL,
                title VARCHAR(200) NOT NULL,
                description TEXT,
                learning_objectives JSON,
                content TEXT,
                duration_minutes INTEGER NOT NULL DEFAULT 45,
                resources JSON,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(course_id, week, block_number)
            );
        """))
        print("✅ Created as_course_blocks table")
    
    # Check if as_course_assignments table exists
    result = session.execute(text("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables 
            WHERE table_name = 'as_course_assignments'
        );
    """))
    
    if not result.scalar():
        print("📦 Creating as_course_assignments table...")
        session.execute(text("""
            CREATE TABLE as_course_assignments (
                id SERIAL PRIMARY KEY,
                course_id INTEGER NOT NULL REFERENCES as_courses(id) ON DELETE CASCADE,
                title VARCHAR(200) NOT NULL,
                description TEXT NOT NULL,
                assignment_type VARCHAR(50) NOT NULL,
                instructions TEXT,
                duration_minutes INTEGER NOT NULL DEFAULT 30,
                points INTEGER NOT NULL DEFAULT 100,
                rubric TEXT,
                week_assigned INTEGER,
                block_id INTEGER REFERENCES as_course_blocks(id),
                due_days_after_assignment INTEGER NOT NULL DEFAULT 7,
                submission_format VARCHAR(100),
                learning_outcomes JSON,
                generated_by_ai BOOLEAN DEFAULT FALSE,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """))
        print("✅ Created as_course_assignments table")
    
    # Check if as_student_assignments table exists
    result = session.execute(text("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables 
            WHERE table_name = 'as_student_assignments'
        );
    """))
    
    if not result.scalar():
        print("📦 Creating as_student_assignments table...")
        session.execute(text("""
            CREATE TABLE as_student_assignments (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                assignment_id INTEGER NOT NULL REFERENCES as_course_assignments(id) ON DELETE CASCADE,
                course_id INTEGER NOT NULL REFERENCES as_courses(id),
                assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                due_date TIMESTAMP NOT NULL,
                submitted_at TIMESTAMP,
                status VARCHAR(20) NOT NULL DEFAULT 'assigned',
                submission_file_path VARCHAR(500),
                submission_content TEXT,
                grade FLOAT,
                ai_grade FLOAT,
                manual_grade FLOAT,
                feedback TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, assignment_id)
            );
        """))
        print("✅ Created as_student_assignments table")

def main():
    """Main migration function"""
    print("🚀 Starting After School Database Migration...")
    print(f"📅 Migration Date: {datetime.now()}")
    
    session = get_db_session()
    if not session:
        print("❌ Cannot connect to database. Migration failed.")
        return False
    
    try:
        # Create missing tables first
        create_missing_tables(session)
        
        # Add missing columns to existing tables
        add_missing_course_columns(session)
        add_missing_ai_submissions_columns(session)
        
        # Update existing data
        update_existing_course_data(session)
        
        # Commit all changes
        session.commit()
        print("✅ Migration completed successfully!")
        
        return True
        
    except Exception as e:
        session.rollback()
        print(f"❌ Migration failed: {e}")
        return False
        
    finally:
        session.close()

if __name__ == "__main__":
    success = main()
    if success:
        print("🎉 Database migration completed successfully!")
        print("📋 Summary of changes:")
        print("  - Added missing columns to as_courses table")
        print("  - Added missing columns to as_ai_submissions table")
        print("  - Created missing tables (blocks, assignments)")
        print("  - Updated existing data with default values")
    else:
        print("💥 Database migration failed!")
        print("Please check the error messages above and fix any issues.")