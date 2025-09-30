"""
PRODUCTION DATABASE SETUP SCRIPT
Run this to create reading assistant tables in production
"""

import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Production database setup
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("❌ DATABASE_URL environment variable not set!")
    sys.exit(1)

# Handle postgres:// vs postgresql:// URL format
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

print(f"🔧 Setting up production database...")
print(f"🌐 Database URL: {DATABASE_URL[:50]}...")

try:
    # Create engine and session
    engine = create_engine(DATABASE_URL)
    
    # Test connection
    with engine.connect() as connection:
        result = connection.execute(text("SELECT 1")).fetchone()
        print("✅ Production database connection successful!")
    
    # Import all models to register them
    from models.users_models import Base as UserBase
    from models.study_area_models import Base as StudyBase
    from models.reading_assistant_models import Base as ReadingBase
    
    # Create all tables
    print("🔧 Creating reading assistant tables...")
    ReadingBase.metadata.create_all(bind=engine)
    print("✅ Reading assistant tables created!")
    
    # Verify tables were created
    with engine.connect() as connection:
        tables_result = connection.execute(text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_name LIKE '%reading%'
            ORDER BY table_name
        """))
        
        reading_tables = [row[0] for row in tables_result.fetchall()]
        print(f"\n📋 Reading assistant tables in production:")
        for table in reading_tables:
            print(f"   ✅ {table}")
        
        if len(reading_tables) >= 6:
            print(f"\n🎉 SUCCESS: All {len(reading_tables)} reading assistant tables created!")
            
            # Test progress table specifically
            progress_count = connection.execute(text(
                "SELECT COUNT(*) FROM reading_progress"
            )).fetchone()[0]
            print(f"📊 Progress records: {progress_count}")
            
        else:
            print(f"\n⚠️  Only {len(reading_tables)} reading tables found (expected 6+)")

except Exception as e:
    print(f"❌ Production setup failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print(f"\n✅ Production database setup completed!")
print(f"💡 Now test the progress endpoint again")