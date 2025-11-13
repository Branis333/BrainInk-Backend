"""
Migration script to add new fields for direct school joining
Run this to update the SchoolRequest table with new fields
"""

from sqlalchemy import text
from db.connection import engine

def migrate_school_requests():
    """Add new fields to school_requests table"""
    
    migration_sql = """
    -- Add new columns to school_requests table
    ALTER TABLE school_requests 
    ADD COLUMN IF NOT EXISTS request_type VARCHAR DEFAULT 'school_creation';
    
    ALTER TABLE school_requests 
    ADD COLUMN IF NOT EXISTS target_school_id INTEGER REFERENCES schools(id);
    
    ALTER TABLE school_requests 
    ADD COLUMN IF NOT EXISTS created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
    
    -- Update existing records to have the default request_type
    UPDATE school_requests 
    SET request_type = 'school_creation' 
    WHERE request_type IS NULL;
    
    -- Update created_date for existing records
    UPDATE school_requests 
    SET created_date = request_date 
    WHERE created_date IS NULL;
    """
    
    try:
        with engine.connect() as connection:
            connection.execute(text(migration_sql))
            connection.commit()
            print("✅ Migration completed successfully!")
            print("   - Added request_type column")
            print("   - Added target_school_id column") 
            print("   - Added created_date column")
            print("   - Updated existing records")
            
    except Exception as e:
        print(f"❌ Migration failed: {str(e)}")

def check_migration_status():
    """Check if migration fields exist"""
    
    check_sql = """
    SELECT column_name 
    FROM information_schema.columns 
    WHERE table_name = 'school_requests' 
    AND column_name IN ('request_type', 'target_school_id', 'created_date');
    """
    
    try:
        with engine.connect() as connection:
            result = connection.execute(text(check_sql))
            columns = [row[0] for row in result.fetchall()]
            
            print("📊 Current school_requests table structure:")
            print(f"   - request_type: {'✅' if 'request_type' in columns else '❌'}")
            print(f"   - target_school_id: {'✅' if 'target_school_id' in columns else '❌'}")
            print(f"   - created_date: {'✅' if 'created_date' in columns else '❌'}")
            
            return len(columns) == 3
            
    except Exception as e:
        print(f"❌ Status check failed: {str(e)}")
        return False

if __name__ == "__main__":
    print("🔄 Checking migration status...")
    
    if check_migration_status():
        print("✅ Migration already completed!")
    else:
        print("🔄 Running migration...")
        migrate_school_requests()
        
        print("\n🔄 Verifying migration...")
        if check_migration_status():
            print("✅ Migration verified successfully!")
        else:
            print("❌ Migration verification failed!")
