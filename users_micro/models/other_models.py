from sqlalchemy import Table, MetaData
from users_micro.db.database import engine

# Reflect the existing tables
metadata = MetaData()

# Import gamification tables to use in this micro service
Rank = Table('ranks', metadata, autoload_with=engine)
Achievement = Table('achievements', metadata, autoload_with=engine)
UserProgress = Table('user_progress', metadata, autoload_with=engine)
UserAchievement = Table('user_achievements', metadata, autoload_with=engine)
XPTransaction = Table('xp_transactions', metadata, autoload_with=engine)

# Export all tables
__all__ = [
    'User', 'Rank', 'Achievement', 'UserProgress', 
    'UserAchievement', 'XPTransaction', 'metadata'
]