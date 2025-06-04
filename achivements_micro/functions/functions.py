from sqlalchemy.orm import Session
from models.models import Rank, Achievement, UserProgress, UserAchievement, XPTransaction
from models.other_models import User
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy import text

class GamificationService:
    def __init__(self, db: Session):
        self.db = db
    
    def initialize_ranks(self) -> bool:
        """Initialize all ranks in the database"""
        ranks_data = [
            # Starter Ranks
            {"name": "Novice III", "tier": "Starter", "level": 3, "required_xp": 0, "emoji": "🔰"},
            {"name": "Novice II", "tier": "Starter", "level": 2, "required_xp": 500, "emoji": "🔰"},
            {"name": "Novice I", "tier": "Starter", "level": 1, "required_xp": 1500, "emoji": "🔰"},
            {"name": "Apprentice III", "tier": "Starter", "level": 3, "required_xp": 3500, "emoji": "🔰"},
            {"name": "Apprentice II", "tier": "Starter", "level": 2, "required_xp": 6000, "emoji": "🔰"},
            {"name": "Apprentice I", "tier": "Starter", "level": 1, "required_xp": 9000, "emoji": "🔰"},
            {"name": "Scholar III", "tier": "Starter", "level": 3, "required_xp": 13000, "emoji": "🔰"},
            {"name": "Scholar II", "tier": "Starter", "level": 2, "required_xp": 18000, "emoji": "🔰"},
            {"name": "Scholar I", "tier": "Starter", "level": 1, "required_xp": 24000, "emoji": "🔰"},
            
            # Intermediate Ranks
            {"name": "Strategist III", "tier": "Intermediate", "level": 3, "required_xp": 32000, "emoji": "⚔"},
            {"name": "Strategist II", "tier": "Intermediate", "level": 2, "required_xp": 41000, "emoji": "⚔"},
            {"name": "Strategist I", "tier": "Intermediate", "level": 1, "required_xp": 51000, "emoji": "⚔"},
            {"name": "Mentor III", "tier": "Intermediate", "level": 3, "required_xp": 63000, "emoji": "⚔"},
            {"name": "Mentor II", "tier": "Intermediate", "level": 2, "required_xp": 76000, "emoji": "⚔"},
            {"name": "Mentor I", "tier": "Intermediate", "level": 1, "required_xp": 90000, "emoji": "⚔"},
            {"name": "Trailblazer III", "tier": "Intermediate", "level": 3, "required_xp": 110000, "emoji": "⚔"},
            {"name": "Trailblazer II", "tier": "Intermediate", "level": 2, "required_xp": 135000, "emoji": "⚔"},
            {"name": "Trailblazer I", "tier": "Intermediate", "level": 1, "required_xp": 165000, "emoji": "⚔"},
            
            # Advanced Ranks
            {"name": "Sage III", "tier": "Advanced", "level": 3, "required_xp": 200000, "emoji": "🛡"},
            {"name": "Sage II", "tier": "Advanced", "level": 2, "required_xp": 250000, "emoji": "🛡"},
            {"name": "Sage I", "tier": "Advanced", "level": 1, "required_xp": 310000, "emoji": "🛡"},
            {"name": "Commander III", "tier": "Advanced", "level": 3, "required_xp": 380000, "emoji": "🛡"},
            {"name": "Commander II", "tier": "Advanced", "level": 2, "required_xp": 460000, "emoji": "🛡"},
            {"name": "Commander I", "tier": "Advanced", "level": 1, "required_xp": 550000, "emoji": "🛡"},
            {"name": "Elite III", "tier": "Advanced", "level": 3, "required_xp": 660000, "emoji": "🛡"},
            {"name": "Elite II", "tier": "Advanced", "level": 2, "required_xp": 800000, "emoji": "🛡"},
            {"name": "Elite I", "tier": "Advanced", "level": 1, "required_xp": 1000000, "emoji": "🛡"},
            
            # Epic Ranks
            {"name": "Warden III", "tier": "Epic", "level": 3, "required_xp": 1300000, "emoji": "🐉"},
            {"name": "Warden II", "tier": "Epic", "level": 2, "required_xp": 1700000, "emoji": "🐉"},
            {"name": "Warden I", "tier": "Epic", "level": 1, "required_xp": 2200000, "emoji": "🐉"},
            {"name": "Gladiator III", "tier": "Epic", "level": 3, "required_xp": 2800000, "emoji": "🐉"},
            {"name": "Gladiator II", "tier": "Epic", "level": 2, "required_xp": 3500000, "emoji": "🐉"},
            {"name": "Gladiator I", "tier": "Epic", "level": 1, "required_xp": 4300000, "emoji": "🐉"},
            {"name": "Champion III", "tier": "Epic", "level": 3, "required_xp": 5200000, "emoji": "🐉"},
            {"name": "Champion II", "tier": "Epic", "level": 2, "required_xp": 6500000, "emoji": "🐉"},
            {"name": "Champion I", "tier": "Epic", "level": 1, "required_xp": 8000000, "emoji": "🐉"},
            
            # Mythic Ranks
            {"name": "Ascendant III", "tier": "Mythic", "level": 3, "required_xp": 10000000, "emoji": "🌌"},
            {"name": "Ascendant II", "tier": "Mythic", "level": 2, "required_xp": 13000000, "emoji": "🌌"},
            {"name": "Ascendant I", "tier": "Mythic", "level": 1, "required_xp": 16000000, "emoji": "🌌"},
            {"name": "Luminary III", "tier": "Mythic", "level": 3, "required_xp": 20000000, "emoji": "🌌"},
            {"name": "Luminary II", "tier": "Mythic", "level": 2, "required_xp": 26000000, "emoji": "🌌"},
            {"name": "Luminary I", "tier": "Mythic", "level": 1, "required_xp": 33000000, "emoji": "🌌"},
            {"name": "Celestial III", "tier": "Mythic", "level": 3, "required_xp": 45000000, "emoji": "🌌"},
            {"name": "Celestial II", "tier": "Mythic", "level": 2, "required_xp": 65000000, "emoji": "🌌"},
            {"name": "Celestial I", "tier": "Mythic", "level": 1, "required_xp": 100000000, "emoji": "🌌"},
        ]
        
        try:
            for rank_data in ranks_data:
                existing_rank = self.db.query(Rank).filter(Rank.name == rank_data["name"]).first()
                if not existing_rank:
                    rank = Rank(**rank_data)
                    self.db.add(rank)
            
            self.db.commit()
            return True
        except Exception as e:
            self.db.rollback()
            raise e
    
    def initialize_achievements(self) -> bool:
        """Initialize all achievements in the database"""
        achievements_data = [
            # Quiz & Learning
            {"name": "First Spark", "description": "Complete your first quiz", "category": "Quiz", "badge_icon": "🔥", "xp_reward": 500},
            {"name": "Knowledge Seeker", "description": "Finish 10 quizzes", "category": "Quiz", "badge_icon": "📜", "xp_reward": 1000},
            {"name": "Quiz Marathoner", "description": "Complete 50 quizzes in a week", "category": "Quiz", "badge_icon": "⏱️", "xp_reward": 2500},
            {"name": "Subject Conqueror", "description": "Master all quizzes in one subject", "category": "Quiz", "badge_icon": "👑", "xp_reward": 3000},
            {"name": "Nationwide Explorer", "description": "Complete quizzes from 5+ countries", "category": "Quiz", "badge_icon": "🌍", "xp_reward": 2000},
            
            # Tournaments & Challenges
            {"name": "First Blood", "description": "Enter your first tournament", "category": "Tournament", "badge_icon": "🛡️", "xp_reward": 500},
            {"name": "Clash Champion", "description": "Win a tournament", "category": "Tournament", "badge_icon": "🏆", "xp_reward": 3500},
            {"name": "Streak Breaker", "description": "Win 3 tournaments in a row", "category": "Tournament", "badge_icon": "🔥", "xp_reward": 5000},
            {"name": "Underdog Victory", "description": "Win after entering as lowest rank", "category": "Tournament", "badge_icon": "🔥", "xp_reward": 4000},
            {"name": "Tournament Organizer", "description": "Host your own event", "category": "Tournament", "badge_icon": "📜", "xp_reward": 2500},
            
            # Gamified Learning
            {"name": "Quest Initiate", "description": "Complete 1 daily quest", "category": "Quest", "badge_icon": "📋", "xp_reward": 500},
            {"name": "Relentless Adventurer", "description": "Complete 50 daily quests", "category": "Quest", "badge_icon": "👢", "xp_reward": 2500},
            {"name": "Perfect Week", "description": "Complete all daily quests 7 days straight", "category": "Quest", "badge_icon": "📅", "xp_reward": 3000},
            {"name": "Time Traveler", "description": "Log in 100 different days", "category": "Dedication", "badge_icon": "⏳", "xp_reward": 2000},
            {"name": "XP Grinder", "description": "Earn 1 million XP in a month", "category": "Dedication", "badge_icon": "⚡", "xp_reward": 3000},
            
            # Social & Squad
            {"name": "Friend Requester", "description": "Add your first friend", "category": "Social", "badge_icon": "❤️", "xp_reward": 500},
            {"name": "Squad Goals", "description": "Join or form a squad", "category": "Social", "badge_icon": "👥", "xp_reward": 1000},
            {"name": "Debate Star", "description": "Participate in 10 debates", "category": "Social", "badge_icon": "🎤", "xp_reward": 2500},
            {"name": "Squad Slayer", "description": "Win a team tournament", "category": "Social", "badge_icon": "⚔️", "xp_reward": 3000},
            {"name": "Social Butterfly", "description": "Chat with 50 different users", "category": "Social", "badge_icon": "💬", "xp_reward": 2000},
            
            # Hidden/Rare
            {"name": "Night Owl", "description": "Log in after 2am local time", "category": "Hidden", "badge_icon": "🌙", "xp_reward": 1000, "is_hidden": True},
            {"name": "Lucky Streak", "description": "Win 5 random draws", "category": "Hidden", "badge_icon": "🍀", "xp_reward": 1500, "is_hidden": True},
            {"name": "Friendly Fire", "description": "Beat a friend in a quiz", "category": "Hidden", "badge_icon": "⚔️", "xp_reward": 1000, "is_hidden": True},
        ]
        
        try:
            for achievement_data in achievements_data:
                existing_achievement = self.db.query(Achievement).filter(Achievement.name == achievement_data["name"]).first()
                if not existing_achievement:
                    achievement = Achievement(**achievement_data)
                    self.db.add(achievement)
            
            self.db.commit()
            return True
        except Exception as e:
            self.db.rollback()
            raise e
    
    def get_user_progress(self, user_id: int) -> UserProgress:
        """Get or create user progress"""
        progress = self.db.query(UserProgress).filter(UserProgress.user_id == user_id).first()
        if not progress:
            # Get starting rank (Novice III)
            starting_rank = self.db.query(Rank).filter(Rank.required_xp == 0).first()
            progress = UserProgress(
                user_id=user_id,
                current_rank_id=starting_rank.id if starting_rank else None
            )
            self.db.add(progress)
            self.db.commit()
            self.db.refresh(progress)
        return progress
    
    def add_xp(self, user_id: int, amount: int, source: str, description: str = None) -> UserProgress:
        """Add XP to user and check for rank up"""
        progress = self.get_user_progress(user_id)
        old_xp = progress.total_xp
        progress.total_xp += amount
        
        # Log XP transaction
        xp_transaction = XPTransaction(
            user_id=user_id,
            amount=amount,
            source=source,
            description=description
        )
        self.db.add(xp_transaction)
        
        # Check for rank up
        new_rank = self.check_rank_up(progress.total_xp)
        if new_rank and (not progress.current_rank_id or new_rank.id != progress.current_rank_id):
            old_rank = progress.current_rank_id
            progress.current_rank_id = new_rank.id
            
        self.db.commit()
        return progress
    
    def check_rank_up(self, total_xp: int) -> Optional[Rank]:
        """Check what rank the user should have based on XP"""
        return self.db.query(Rank).filter(
            Rank.required_xp <= total_xp
        ).order_by(Rank.required_xp.desc()).first()
    
    def award_achievement(self, user_id: int, achievement_name: str) -> bool:
        """Award achievement to user if not already earned"""
        achievement = self.db.query(Achievement).filter(Achievement.name == achievement_name).first()
        if not achievement:
            return False
            
        # Check if user already has this achievement
        existing = self.db.query(UserAchievement).filter(
            UserAchievement.user_id == user_id,
            UserAchievement.achievement_id == achievement.id
        ).first()
        
        if existing:
            return False
            
        # Award achievement
        user_achievement = UserAchievement(
            user_id=user_id,
            achievement_id=achievement.id
        )
        self.db.add(user_achievement)
        
        # Award XP
        if achievement.xp_reward > 0:
            self.add_xp(user_id, achievement.xp_reward, "achievement", f"Earned achievement: {achievement_name}")
            
        self.db.commit()
        return True
    
    def process_action(self, user_id: int, action: str) -> Dict[str, Any]:
        """Process gamification action and return results"""
        progress = self.get_user_progress(user_id)
        xp_added = 0
        achievements_earned = []
        
        # Update progress based on action
        if action == "quiz_completed":
            progress.total_quiz_completed += 1
            xp_added = 100
            self.add_xp(user_id, xp_added, "quiz_completion", "Completed a quiz")
            
            # Check achievements
            if progress.total_quiz_completed == 1:
                if self.award_achievement(user_id, "First Spark"):
                    achievements_earned.append("First Spark")
            elif progress.total_quiz_completed == 10:
                if self.award_achievement(user_id, "Knowledge Seeker"):
                    achievements_earned.append("Knowledge Seeker")
                    
        elif action == "tournament_entered":
            progress.tournaments_entered += 1
            
            # Check achievements
            if progress.tournaments_entered == 1:
                if self.award_achievement(user_id, "First Blood"):
                    achievements_earned.append("First Blood")
                    
        elif action == "tournament_won":
            progress.tournaments_won += 1
            xp_added = 1000
            self.add_xp(user_id, xp_added, "tournament_win", "Won a tournament")
            
            # Check achievements
            if progress.tournaments_won == 1:
                if self.award_achievement(user_id, "Clash Champion"):
                    achievements_earned.append("Clash Champion")
                    
        elif action == "course_completed":
            progress.courses_completed += 1
            xp_added = 500
            self.add_xp(user_id, xp_added, "course_completion", "Completed a course")
            
        elif action == "login":
            # Update last login
            progress.last_login = datetime.utcnow()
            
            # Check for night owl achievement
            current_hour = datetime.now().hour
            if 2 <= current_hour <= 5:
                if self.award_achievement(user_id, "Night Owl"):
                    achievements_earned.append("Night Owl")
        else:
            raise ValueError(f"Unknown action: {action}")
        
        self.db.commit()
        
        return {
            "xp_added": xp_added,
            "achievements_earned": achievements_earned,
            "total_xp": progress.total_xp,
            "current_rank": progress.current_rank
        }
    
    def get_all_ranks(self) -> List[Rank]:
        """Get all ranks ordered by required XP"""
        return self.db.query(Rank).order_by(Rank.required_xp).all()
    
    def get_user_achievements(self, user_id: int) -> List[UserAchievement]:
        """Get all achievements earned by user"""
        return self.db.query(UserAchievement).filter(
            UserAchievement.user_id == user_id
        ).all()
    
    def get_available_achievements(self) -> List[Achievement]:
        """Get all non-hidden achievements"""
        return self.db.query(Achievement).filter(
            Achievement.is_hidden == False
        ).all()
    
    def get_leaderboard(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get leaderboard data using raw SQL to avoid ORM complications"""
        
        # Use raw SQL to join across tables
        result = self.db.execute(
            text("""
                SELECT 
                    up.user_id,
                    up.total_xp,
                    u.username,
                    r.id as rank_id,
                    r.name as rank_name,
                    r.tier as rank_tier,
                    r.level as rank_level,
                    r.required_xp as rank_required_xp,
                    r.emoji as rank_emoji
                FROM user_progress up
                JOIN users u ON up.user_id = u.id
                LEFT JOIN ranks r ON up.current_rank_id = r.id
                ORDER BY up.total_xp DESC
                LIMIT :limit
            """),
            {"limit": limit}
        ).fetchall()
        
        leaderboard_data = []
        for row in result:
            rank_data = None
            if row.rank_id:
                rank_data = {
                    "id": row.rank_id,
                    "name": row.rank_name,
                    "tier": row.rank_tier,
                    "level": row.rank_level,
                    "required_xp": row.rank_required_xp,
                    "emoji": row.rank_emoji
                }
            
            leaderboard_data.append({
                "user_id": row.user_id,
                "username": row.username,
                "total_xp": row.total_xp,
                "current_rank": rank_data
            })
        
        return leaderboard_data