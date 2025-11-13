"""
Create database tables script
"""
from db.connection import engine
from models.users_models import Base as UserBase
from models.study_area_models import Base as StudyBase
from sqlalchemy import text

def create_tables():
    print("Creating database tables...")
    try:
        # Create all tables from both models
        UserBase.metadata.create_all(bind=engine)
        StudyBase.metadata.create_all(bind=engine)
        print("✅ All tables created successfully!")
        
        # Test connection
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1"))
            print("✅ Database connection test passed!")
            
    except Exception as e:
        print(f"❌ Error creating tables: {str(e)}")

if __name__ == "__main__":
    create_tables()
