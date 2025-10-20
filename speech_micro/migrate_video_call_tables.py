"""
Database migration for video call and transcription tables
Run this script to create the necessary tables in your database
"""

from sqlalchemy import create_engine
from models.video_call_models import Base
import os
from dotenv import load_dotenv

load_dotenv()

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("ERROR: DATABASE_URL not found in environment variables")
    print("Please set your database URL in the .env file")
    exit(1)

def create_tables():
    """Create all video call and transcription tables"""
    try:
        engine = create_engine(DATABASE_URL)
        
        print("Creating video call and transcription tables...")
        print("Note: User references are stored as integer IDs without foreign key constraints")
        Base.metadata.create_all(bind=engine)
        print("✅ Tables created successfully!")
        
        print("\nCreated tables:")
        print("- video_call_rooms (stores room information)")
        print("- video_call_participants (tracks user participation)")
        print("- transcription_sessions (manages transcription sessions)")
        print("- transcription_data (stores transcribed text)")
        print("- call_analytics (session analysis and insights)")
        
        print("\n📝 Important Notes:")
        print("- User IDs are stored as integers without foreign key constraints")
        print("- User information is fetched via authentication tokens")
        print("- This allows the speech_micro to work independently of the user database")
        
    except Exception as e:
        print(f"❌ Error creating tables: {e}")
        return False
    
    return True

if __name__ == "__main__":
    print("Video Call & Transcription Database Migration")
    print("=" * 50)
    
    success = create_tables()
    
    if success:
        print("\n🎉 Migration completed successfully!")
        print("You can now use the video call and transcription features.")
    else:
        print("\n💥 Migration failed!")
        print("Please check your database connection and try again.")
