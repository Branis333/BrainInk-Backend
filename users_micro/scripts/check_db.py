from users_micro.db.connection import engine
from sqlalchemy import text

try:
    with engine.connect() as conn:
        result = conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"))
        tables = [row[0] for row in result]
        print('Existing tables:', tables)
        
        # Check if users table has role_id column
        if 'users' in tables:
            result = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'users' AND table_schema = 'public'"))
            columns = [row[0] for row in result]
            print('Users table columns:', columns)
        
except Exception as e:
    print(f"Error: {e}")
