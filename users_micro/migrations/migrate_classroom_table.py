"""
Migration script to update classroom table with new columns
This will add description, capacity, and location columns without deleting existing data
"""

from sqlalchemy import text
from users_micro.db.connection import engine
import sys

def migrate_classroom_table():
    """Add new columns to classroom table without losing existing data"""
    
    migration_queries = [
        # Add description column (nullable)
        "ALTER TABLE classrooms ADD COLUMN IF NOT EXISTS description VARCHAR;",
        
        # Add capacity column with default value of 30
        "ALTER TABLE classrooms ADD COLUMN IF NOT EXISTS capacity INTEGER DEFAULT 30;",
        
        # Add location column (nullable)
        "ALTER TABLE classrooms ADD COLUMN IF NOT EXISTS location VARCHAR;",
        
        # Update existing rows to have default capacity if null
        "UPDATE classrooms SET capacity = 30 WHERE capacity IS NULL;",
    ]
    
    try:
        with engine.connect() as connection:
            print("🔄 Starting classroom table migration...")
            
            # Check current table structure
            result = connection.execute(text("""
                SELECT column_name, data_type, is_nullable, column_default 
                FROM information_schema.columns 
                WHERE table_name = 'classrooms' 
                ORDER BY ordinal_position;
            """))
            
            existing_columns = [row[0] for row in result.fetchall()]
            print(f"📋 Current columns: {existing_columns}")
            
            # Execute migration queries
            for i, query in enumerate(migration_queries, 1):
                print(f"🔧 Executing migration step {i}/4...")
                connection.execute(text(query))
                connection.commit()
                print(f"✅ Step {i} completed")
            
            # Verify the migration
            print("\n🔍 Verifying migration...")
            result = connection.execute(text("""
                SELECT column_name, data_type, is_nullable, column_default 
                FROM information_schema.columns 
                WHERE table_name = 'classrooms' 
                ORDER BY ordinal_position;
            """))
            
            print("📋 Updated table structure:")
            for row in result.fetchall():
                print(f"  - {row[0]}: {row[1]} ({'NULL' if row[2] == 'YES' else 'NOT NULL'}) {f'DEFAULT {row[3]}' if row[3] else ''}")
            
            # Count existing records
            result = connection.execute(text("SELECT COUNT(*) FROM classrooms;"))
            record_count = result.scalar()
            print(f"\n📊 Total classroom records preserved: {record_count}")
            
            if record_count > 0:
                # Show sample of migrated data
                result = connection.execute(text("""
                    SELECT id, name, description, capacity, location, school_id 
                    FROM classrooms 
                    LIMIT 3;
                """))
                print("\n📄 Sample migrated records:")
                for row in result.fetchall():
                    print(f"  ID: {row[0]}, Name: {row[1]}, Description: {row[2]}, Capacity: {row[3]}, Location: {row[4]}, School: {row[5]}")
            
            print("\n🎉 Classroom table migration completed successfully!")
            print("✅ All existing data has been preserved")
            print("✅ New columns added: description, capacity, location")
            
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        print("🔄 Rolling back changes...")
        
        # Rollback queries (remove added columns)
        rollback_queries = [
            "ALTER TABLE classrooms DROP COLUMN IF EXISTS description;",
            "ALTER TABLE classrooms DROP COLUMN IF EXISTS capacity;", 
            "ALTER TABLE classrooms DROP COLUMN IF EXISTS location;",
        ]
        
        try:
            with engine.connect() as connection:
                for query in rollback_queries:
                    connection.execute(text(query))
                    connection.commit()
                print("🔄 Rollback completed")
        except Exception as rollback_error:
            print(f"❌ Rollback failed: {rollback_error}")
        
        sys.exit(1)

def verify_migration():
    """Verify that the migration was successful"""
    try:
        with engine.connect() as connection:
            # Check if all new columns exist
            result = connection.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'classrooms' 
                AND column_name IN ('description', 'capacity', 'location');
            """))
            
            new_columns = [row[0] for row in result.fetchall()]
            expected_columns = ['description', 'capacity', 'location']
            
            if set(new_columns) == set(expected_columns):
                print("✅ Migration verification successful - all new columns present")
                return True
            else:
                missing = set(expected_columns) - set(new_columns)
                print(f"❌ Migration verification failed - missing columns: {missing}")
                return False
                
    except Exception as e:
        print(f"❌ Migration verification error: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Classroom Table Migration Tool")
    print("=" * 50)
    
    # Ask for confirmation
    response = input("This will update the classroom table structure. Continue? (y/N): ").lower()
    
    if response == 'y' or response == 'yes':
        migrate_classroom_table()
        verify_migration()
    else:
        print("Migration cancelled.")
