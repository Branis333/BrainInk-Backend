from sqlalchemy import Table, MetaData
from db.database import engine

# Reflect the existing tables from main user backend
metadata = MetaData()

try:
    # Try to import user table - if it exists in this database
    User = Table('users', metadata, autoload_with=engine)
    USERS_TABLE_EXISTS = True
except Exception as e:
    # Users table doesn't exist in this database
    # We'll handle user lookups via API calls or store usernames directly
    User = None
    USERS_TABLE_EXISTS = False
    print(f"Note: Users table not found in speech_micro database: {e}")
    print("User information will be handled via authentication tokens and API calls.")
