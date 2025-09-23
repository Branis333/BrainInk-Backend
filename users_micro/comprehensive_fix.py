"""
Comprehensive database fix for all NULL values and missing data
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
    DATABASE_URL = os.getenv(
        "DATABASE_URL", 
        "postgresql://postgres:password@localhost:5432/brainink"
    )
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    print("⚠️ Using fallback database configuration")

def comprehensive_fix():
    """Comprehensive fix for all database issues"""
    print("🔧 Starting comprehensive database fix...")
    
    session = SessionLocal()
    
    try:
        # 1. Check current state of courses table
        print("📊 Checking current database state...")
        
        result = session.execute(text("""
            SELECT 
                COUNT(*) as total_courses,
                COUNT(CASE WHEN total_weeks IS NULL THEN 1 END) as null_total_weeks,
                COUNT(CASE WHEN blocks_per_week IS NULL THEN 1 END) as null_blocks_per_week,
                COUNT(CASE WHEN generated_by_ai IS NULL THEN 1 END) as null_generated_by_ai
            FROM as_courses;
        """))
        
        stats = result.fetchone()
        print(f"📈 Database Stats:")
        print(f"   Total Courses: {stats[0]}")
        print(f"   NULL total_weeks: {stats[1]}")
        print(f"   NULL blocks_per_week: {stats[2]}")
        print(f"   NULL generated_by_ai: {stats[3]}")
        
        if stats[1] > 0 or stats[2] > 0 or stats[3] > 0:
            print("⚠️ Found NULL values! Fixing...")
            
            # 2. Force update ALL courses to have proper values
            session.execute(text("""
                UPDATE as_courses 
                SET 
                    total_weeks = COALESCE(total_weeks, 8),
                    blocks_per_week = COALESCE(blocks_per_week, 2),
                    textbook_source = COALESCE(textbook_source, ''),
                    textbook_content = COALESCE(textbook_content, ''),
                    generated_by_ai = COALESCE(generated_by_ai, FALSE);
            """))
            
            print("✅ Updated all courses with default values")
            
            # 3. Ensure NOT NULL constraints are properly set
            print("🔒 Setting NOT NULL constraints...")
            
            # Drop and recreate columns with proper constraints
            session.execute(text("ALTER TABLE as_courses ALTER COLUMN total_weeks SET NOT NULL;"))
            session.execute(text("ALTER TABLE as_courses ALTER COLUMN blocks_per_week SET NOT NULL;"))  
            session.execute(text("ALTER TABLE as_courses ALTER COLUMN generated_by_ai SET NOT NULL;"))
            
            print("✅ NOT NULL constraints applied")
        else:
            print("✅ No NULL values found - database is clean")
        
        # 4. Verify the fix worked
        print("🔍 Verifying fixes...")
        
        result = session.execute(text("""
            SELECT 
                COUNT(*) as total_courses,
                COUNT(CASE WHEN total_weeks IS NULL THEN 1 END) as null_total_weeks,
                COUNT(CASE WHEN blocks_per_week IS NULL THEN 1 END) as null_blocks_per_week,
                COUNT(CASE WHEN generated_by_ai IS NULL THEN 1 END) as null_generated_by_ai
            FROM as_courses;
        """))
        
        final_stats = result.fetchone()
        print(f"📈 Final Database Stats:")
        print(f"   Total Courses: {final_stats[0]}")
        print(f"   NULL total_weeks: {final_stats[1]}")
        print(f"   NULL blocks_per_week: {final_stats[2]}")
        print(f"   NULL generated_by_ai: {final_stats[3]}")
        
        if final_stats[1] == 0 and final_stats[2] == 0 and final_stats[3] == 0:
            print("🎉 All NULL values successfully eliminated!")
        else:
            print("⚠️ Some NULL values still remain - manual intervention needed")
        
        # 5. Show sample of fixed data
        print("📋 Sample of course data after fix:")
        result = session.execute(text("""
            SELECT id, title, total_weeks, blocks_per_week, generated_by_ai 
            FROM as_courses 
            LIMIT 5;
        """))
        
        for row in result:
            print(f"   Course {row[0]}: {row[1]} | weeks={row[2]} | blocks={row[3]} | ai={row[4]}")
        
        # Commit all changes
        session.commit()
        print("✅ All changes committed successfully!")
        
        return True
        
    except Exception as e:
        session.rollback()
        print(f"❌ Error during comprehensive fix: {e}")
        return False
        
    finally:
        session.close()

if __name__ == "__main__":
    print("🚀 Starting Comprehensive Database Fix...")
    print(f"📅 Fix Date: {datetime.now()}")
    
    success = comprehensive_fix()
    
    if success:
        print("🎉 Comprehensive database fix completed successfully!")
        print("📋 Backend should now work without validation errors")
    else:
        print("💥 Comprehensive database fix failed!")