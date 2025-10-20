import os
from typing import Optional

class Config:
    """Configuration settings for the application"""
    
    # Kana AI Configuration (compatible with your React component)
    KANA_AI_API_URL: str = os.getenv("KANA_AI_API_URL", "http://localhost:10000/api/generate-quiz")
    KANA_AI_ENABLED: bool = os.getenv("KANA_AI_ENABLED", "true").lower() == "true"
    
    # Legacy Chainlink configuration (for backward compatibility)
    CHAINLINK_API_URL: str = os.getenv("CHAINLINK_API_URL", "http://localhost:3000/api/generate-questions")
    CHAINLINK_ENABLED: bool = os.getenv("CHAINLINK_ENABLED", "true").lower() == "true"
    
    # Tournament defaults
    DEFAULT_QUESTION_COUNT: int = int(os.getenv("DEFAULT_QUESTION_COUNT", "50"))
    DEFAULT_TIME_LIMIT_MINUTES: int = int(os.getenv("DEFAULT_TIME_LIMIT_MINUTES", "60"))
    DEFAULT_DIFFICULTY: str = os.getenv("DEFAULT_DIFFICULTY", "middle_school")
    
    # Fallback configuration
    USE_FALLBACK_QUESTIONS: bool = os.getenv("USE_FALLBACK_QUESTIONS", "true").lower() == "true"
    FALLBACK_ON_ERROR: bool = os.getenv("FALLBACK_ON_ERROR", "true").lower() == "true"
    
    # Daily challenge settings (for React component compatibility)
    DAILY_CHALLENGE_XP_REWARD: int = int(os.getenv("DAILY_CHALLENGE_XP_REWARD", "50"))
    CHALLENGE_REFRESH_INTERVAL_HOURS: int = int(os.getenv("CHALLENGE_REFRESH_INTERVAL_HOURS", "24"))

# Global config instance
config = Config()
