from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from db.connection import db_dependency
from db.verify_token import user_dependency
from functions.functions import GamificationService
from pydantic import BaseModel

router = APIRouter(tags=["Gamification"])

class RankResponse(BaseModel):
    id: int
    name: str
    tier: str
    level: int
    required_xp: int
    emoji: Optional[str]
    
    class Config:
        from_attributes = True

class AchievementResponse(BaseModel):
    id: int
    name: str
    description: str
    category: str
    badge_icon: Optional[str]
    xp_reward: int
    earned_at: Optional[str] = None
    
    class Config:
        from_attributes = True

class UserProgressResponse(BaseModel):
    total_xp: int
    current_rank: Optional[RankResponse]
    login_streak: int
    total_quiz_completed: int
    tournaments_won: int
    tournaments_entered: int
    courses_completed: int
    time_spent_hours: int
    
    class Config:
        from_attributes = True

class LeaderboardEntry(BaseModel):
    user_id: int
    username: str
    total_xp: int
    current_rank: Optional[RankResponse]

class ActionResult(BaseModel):
    message: str
    xp_added: int
    achievements_earned: List[str]
    total_xp: int

@router.get("/initialize")
async def initialize_gamification(db: db_dependency, current_user: user_dependency):
    """Initialize ranks and achievements (admin only)"""
    try:
        service = GamificationService(db)
        
        # Initialize ranks
        ranks_success = service.initialize_ranks()
        if not ranks_success:
            raise HTTPException(status_code=500, detail="Failed to initialize ranks")
        
        # Initialize achievements
        achievements_success = service.initialize_achievements()
        if not achievements_success:
            raise HTTPException(status_code=500, detail="Failed to initialize achievements")
        
        return {"message": "Gamification system initialized successfully"}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Initialization failed: {str(e)}")

@router.get("/progress", response_model=UserProgressResponse)
async def get_user_progress(db: db_dependency, current_user: user_dependency):
    """Get current user's progress and rank"""
    try:
        service = GamificationService(db)
        progress = service.get_user_progress(current_user["user_id"])
        
        return UserProgressResponse(
            total_xp=progress.total_xp,
            current_rank=progress.current_rank,
            login_streak=progress.login_streak,
            total_quiz_completed=progress.total_quiz_completed,
            tournaments_won=progress.tournaments_won,
            tournaments_entered=progress.tournaments_entered,
            courses_completed=progress.courses_completed,
            time_spent_hours=progress.time_spent_hours
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get progress: {str(e)}")

@router.get("/ranks", response_model=List[RankResponse])
async def get_all_ranks(db: db_dependency):
    """Get all available ranks"""
    try:
        service = GamificationService(db)
        ranks = service.get_all_ranks()
        return ranks
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get ranks: {str(e)}")

@router.get("/achievements", response_model=List[AchievementResponse])
async def get_user_achievements(db: db_dependency, current_user: user_dependency):
    """Get user's earned achievements"""
    try:
        service = GamificationService(db)
        user_achievements = service.get_user_achievements(current_user["user_id"])
        
        achieved_list = []
        for ua in user_achievements:
            achievement_data = AchievementResponse(
                id=ua.achievement.id,
                name=ua.achievement.name,
                description=ua.achievement.description,
                category=ua.achievement.category,
                badge_icon=ua.achievement.badge_icon,
                xp_reward=ua.achievement.xp_reward,
                earned_at=ua.earned_at.isoformat()
            )
            achieved_list.append(achievement_data)
        
        return achieved_list
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get achievements: {str(e)}")

@router.get("/achievements/available", response_model=List[AchievementResponse])
async def get_available_achievements(db: db_dependency):
    """Get all available achievements (excluding hidden ones)"""
    try:
        service = GamificationService(db)
        achievements = service.get_available_achievements()
        return achievements
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get available achievements: {str(e)}")

@router.post("/xp/add")
async def add_xp(
    db: db_dependency, 
    current_user: user_dependency,
    amount: int,
    source: str,
    description: str = None
):
    """Add XP to current user (for testing or admin use)"""
    try:
        if amount <= 0:
            raise HTTPException(status_code=400, detail="XP amount must be positive")
        
        service = GamificationService(db)
        progress = service.add_xp(current_user["user_id"], amount, source, description)
        
        return {
            "message": f"Added {amount} XP", 
            "total_xp": progress.total_xp,
            "current_rank": progress.current_rank.name if progress.current_rank else None
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add XP: {str(e)}")

# ... existing imports and code ...

# ... existing imports and code ...

@router.get("/leaderboard", response_model=List[LeaderboardEntry])
async def get_leaderboard(db: db_dependency, limit: int = 50):
    """Get XP leaderboard"""
    try:
        if limit <= 0 or limit > 100:
            raise HTTPException(status_code=400, detail="Limit must be between 1 and 100")
        
        service = GamificationService(db)
        leaderboard_data = service.get_leaderboard(limit)
        
        result = []
        for entry_data in leaderboard_data:
            current_rank = None
            if entry_data["current_rank"]:
                current_rank = RankResponse(**entry_data["current_rank"])
            
            entry = LeaderboardEntry(
                user_id=entry_data["user_id"],
                username=entry_data["username"],
                total_xp=entry_data["total_xp"],
                current_rank=current_rank
            )
            result.append(entry)
        
        return result
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get leaderboard: {str(e)}")


@router.post("/actions/{action}", response_model=ActionResult)
async def trigger_action(
    db: db_dependency,
    current_user: user_dependency,
    action: str
):
    """Trigger a gamification action (quiz completed, tournament entered, etc.)"""
    try:
        valid_actions = [
            "quiz_completed", 
            "tournament_entered", 
            "tournament_won", 
            "course_completed", 
            "login"
        ]
        
        if action not in valid_actions:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid action. Valid actions: {', '.join(valid_actions)}"
            )
        
        service = GamificationService(db)
        result = service.process_action(current_user["user_id"], action)
        
        return ActionResult(
            message=f"Action '{action}' processed successfully",
            xp_added=result["xp_added"],
            achievements_earned=result["achievements_earned"],
            total_xp=result["total_xp"]
        )
    
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process action: {str(e)}")

# Additional endpoint for user statistics
@router.get("/stats")
async def get_user_stats(db: db_dependency, current_user: user_dependency):
    """Get comprehensive user statistics"""
    try:
        service = GamificationService(db)
        progress = service.get_user_progress(current_user["user_id"])
        achievements = service.get_user_achievements(current_user["user_id"])
        
        return {
            "user_id": current_user["user_id"],
            "username": current_user["username"],
            "total_xp": progress.total_xp,
            "current_rank": progress.current_rank.name if progress.current_rank else "Unranked",
            "achievements_count": len(achievements),
            "stats": {
                "login_streak": progress.login_streak,
                "total_quiz_completed": progress.total_quiz_completed,
                "tournaments_won": progress.tournaments_won,
                "tournaments_entered": progress.tournaments_entered,
                "courses_completed": progress.courses_completed,
                "time_spent_hours": progress.time_spent_hours
            }
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")