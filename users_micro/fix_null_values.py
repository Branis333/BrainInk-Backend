"""
Additional script to fix any remaining NULL values in database
"""

import os
import sys
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add the parent directory to sys.path to import db modules
sys.path.append(os.path.join(os.path.dirname(__file__)))

try:
    from db.database import engine, SessionLocal
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

def fix_null_values():
    """Fix any remaining NULL values in critical columns"""
    print("🔧 Fixing NULL values in database...")
    
    session = SessionLocal()
    
    try:
        # Fix NULL values in courses table
        print("📊 Updating NULL values in as_courses table...")
        
        # Check for courses with NULL values
        result = session.execute(text("""
            SELECT COUNT(*) FROM as_courses 
            WHERE total_weeks IS NULL OR blocks_per_week IS NULL OR generated_by_ai IS NULL;
        """))
        
        null_count = result.scalar()
        if null_count > 0:
            print(f"Found {null_count} courses with NULL values. Fixing...")
            
            # Update all NULL values at once
            session.execute(text("""
                UPDATE as_courses 
                SET 
                    total_weeks = COALESCE(total_weeks, 8),
                    blocks_per_week = COALESCE(blocks_per_week, 2),
                    generated_by_ai = COALESCE(generated_by_ai, FALSE)
                WHERE total_weeks IS NULL OR blocks_per_week IS NULL OR generated_by_ai IS NULL;
            """))
            
            print("✅ Fixed NULL values in courses")
        else:
            print("✅ No NULL values found in courses")
        
        # Also make sure the columns have proper NOT NULL constraints
        print("🔧 Ensuring NOT NULL constraints...")
        
        try:
            # Add NOT NULL constraints if they don't exist
            session.execute(text("ALTER TABLE as_courses ALTER COLUMN total_weeks SET NOT NULL;"))
        except Exception:
            pass  # Constraint might already exist
            
        try:
            session.execute(text("ALTER TABLE as_courses ALTER COLUMN blocks_per_week SET NOT NULL;"))
        except Exception:
            pass
            
        try:
            session.execute(text("ALTER TABLE as_courses ALTER COLUMN generated_by_ai SET NOT NULL;"))
        except Exception:
            pass
        
        print("✅ NOT NULL constraints ensured")
        
        # Commit changes
        session.commit()
        print("✅ All NULL value fixes committed successfully!")
        
        return True
        
    except Exception as e:
        session.rollback()
        print(f"❌ Error fixing NULL values: {e}")
        return False
        
    finally:
        session.close()

if __name__ == "__main__":
    print("🚀 Starting NULL value fix...")
    print(f"📅 Fix Date: {datetime.now()}")
    
    success = fix_null_values()
    
    if success:
        print("🎉 NULL value fix completed successfully!")
    else:
        print("💥 NULL value fix failed!")