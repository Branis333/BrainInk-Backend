from db.database import test_connection, SessionLocal
from models.models import User

def test_supabase_connection():
    print("Testing Supabase connection...")
    
    # Test basic connection
    if not test_connection():
        print("❌ Basic connection failed")
        return False
    
    # Test SQLAlchemy session
    try:
        db = SessionLocal()
        # Try a simple query
        users = db.query(User).limit(1).all()
        print("✅ SQLAlchemy session works!")
        db.close()
        return True
    except Exception as e:
        print(f"❌ SQLAlchemy session failed: {e}")
        return False

if __name__ == "__main__":
    test_supabase_connection()