#!/usr/bin/env python3
"""
Database fix script to update assignments with missing rubric values
"""

import sys
import os

# Add the parent directory to the path to import models
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker
    import os
    from dotenv import load_dotenv

    load_dotenv()

    # Database connection
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/brainink_db")
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def fix_missing_rubrics():
        """Fix assignments with missing or empty rubric values and too-long descriptions"""
        db = SessionLocal()
        try:
            print("🔍 Checking for assignments with missing rubric values...")
            
            # Update assignments with NULL or empty rubric
            result = db.execute(text("""
                UPDATE assignments 
                SET rubric = 'Grading rubric not provided - please update this assignment with detailed grading criteria.'
                WHERE rubric IS NULL OR rubric = '' OR LENGTH(TRIM(rubric)) = 0
            """))
            
            print(f"✅ Updated {result.rowcount} assignments with missing rubric values")
            
            # Update assignments with too-short descriptions
            result2 = db.execute(text("""
                UPDATE assignments 
                SET description = 'Assignment description not provided - please update this assignment with detailed instructions.'
                WHERE description IS NULL OR description = '' OR LENGTH(TRIM(description)) < 10
            """))
            
            print(f"✅ Updated {result2.rowcount} assignments with too-short descriptions")
            
            # Update assignments with too-long descriptions (truncate to 997 chars + "...")
            result3 = db.execute(text("""
                UPDATE assignments 
                SET description = LEFT(description, 997) || '...'
                WHERE LENGTH(description) > 1000
            """))
            
            print(f"✅ Updated {result3.rowcount} assignments with too-long descriptions")
            
            db.commit()
            
            # Verify the fix
            check_result = db.execute(text("""
                SELECT COUNT(*) as count FROM assignments 
                WHERE rubric IS NULL OR rubric = '' OR LENGTH(TRIM(rubric)) = 0
                   OR description IS NULL OR description = '' OR LENGTH(TRIM(description)) < 10
                   OR LENGTH(description) > 1000
            """))
            
            remaining_count = check_result.fetchone()[0]
            if remaining_count == 0:
                print("✅ All assignments now have valid rubric and description values")
            else:
                print(f"⚠️  Still {remaining_count} assignments with validation issues")
                
        except Exception as e:
            print(f"❌ Error fixing rubrics: {str(e)}")
            db.rollback()
        finally:
            db.close()

    if __name__ == "__main__":
        fix_missing_rubrics()

except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Please make sure you're running this from the backend directory with the virtual environment activated.")
except Exception as e:
    print(f"❌ Error: {e}")
