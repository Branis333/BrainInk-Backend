from sqlalchemy import Table, MetaData
from db.database import engine

# Reflect the existing tables
metadata = MetaData()

# Import gamification tables to use in this micro service
User = Table('users', metadata, autoload_with=engine)