from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

class SquadRoleEnum(str, Enum):
    LEADER = "leader"
    MEMBER = "member"
    MODERATOR = "moderator"

class BattleStatusEnum(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class LeagueStatusEnum(str, Enum):
    UPCOMING = "upcoming"
    ACTIVE = "active"
    ENDED = "ended"

# Request schemas
class CreateSquadSchema(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    emoji: str = Field(default="🦄", max_length=10)
    description: Optional[str] = Field(None, max_length=500)
    creator_id: int
    invitedFriends: List[int] = Field(default=[])
    subject_focus: Optional[List[str]] = None
    is_public: bool = True

class UpdateSquadSchema(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    emoji: Optional[str] = Field(None, max_length=10)
    description: Optional[str] = Field(None, max_length=500)
    subject_focus: Optional[List[str]] = None
    is_public: Optional[bool] = None
    max_members: Optional[int] = Field(None, ge=5, le=50)

class DeleteSquadSchema(BaseModel):
    confirm_deletion: bool = Field(..., description="Must be true to confirm deletion")
    transfer_leadership: Optional[int] = Field(None, description="User ID to transfer leadership to (optional)")

class JoinSquadSchema(BaseModel):
    user_id: int

class SendSquadMessageSchema(BaseModel):
    squad_id: str
    sender_id: int
    content: str = Field(..., min_length=1, max_length=1000)
    message_type: str = Field(default="text")
    metadata: Optional[Dict[str, Any]] = None

class ChallengeSquadSchema(BaseModel):
    challenger_squad_id: str
    challenged_squad_id: str
    battle_type: str = "quiz_battle"
    entry_fee: int = 0
    duration_minutes: int = 30
    subject: Optional[str] = None

class JoinLeagueSchema(BaseModel):
    user_id: int

class CreateLeagueSchema(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    subject: str = Field(..., min_length=1, max_length=100)
    max_participants: int = Field(default=1000, ge=10, le=10000)
    entry_fee: int = Field(default=0, ge=0)
    prize_pool: int = Field(default=0, ge=0)
    difficulty: str = Field(default="intermediate", pattern="^(beginner|intermediate|advanced)$")  # Changed regex to pattern
    league_type: str = Field(default="weekly", pattern="^(weekly|monthly|tournament)$")  # Changed regex to pattern
    duration_days: int = Field(default=7, ge=1, le=365)  # Duration instead of explicit dates
    creator_id: int

class UpdateLeagueSchema(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    max_participants: Optional[int] = Field(None, ge=10, le=10000)
    entry_fee: Optional[int] = Field(None, ge=0)
    prize_pool: Optional[int] = Field(None, ge=0)

class LeagueStatsUpdateSchema(BaseModel):
    user_id: int
    questions_answered: int = Field(default=0, ge=0)
    correct_answers: int = Field(default=0, ge=0)
    xp_earned: int = Field(default=0, ge=0)
    time_spent: int = Field(default=0, ge=0)  # in seconds

# Response schemas
class SquadMemberResponse(BaseModel):
    id: int
    username: str
    fname: Optional[str]
    lname: Optional[str]
    avatar: Optional[str]
    role: str
    weekly_xp: int
    total_xp: int
    joined_at: datetime
    last_active: datetime
    is_online: Optional[bool] = False
    
    class Config:
        from_attributes = True

class SquadResponse(BaseModel):
    id: str
    name: str
    emoji: str
    description: Optional[str]
    creator_id: int
    is_public: bool
    max_members: int
    subject_focus: Optional[List[str]]
    weekly_xp: int
    total_xp: int
    rank: int
    members: List[SquadMemberResponse]
    created_at: datetime
    updated_at: datetime
    unread_count: Optional[int] = 0
    last_activity: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class SquadMessageResponse(BaseModel):
    id: str
    squad_id: str
    sender_id: int
    sender_name: str
    sender_avatar: Optional[str]
    content: str
    message_type: str
    metadata: Optional[Dict[str, Any]]
    created_at: datetime
    reactions: Optional[List[Dict[str, Any]]] = []
    
    class Config:
        from_attributes = True

class SquadBattleResponse(BaseModel):
    id: str
    challenger_squad_id: str
    challenged_squad_id: str
    battle_type: str
    status: str
    entry_fee: int
    prize_pool: int
    duration_minutes: int
    subject: Optional[str]
    challenger_score: int
    challenged_score: int
    winner_squad_id: Optional[str]
    created_at: datetime
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    challenger_squad: Optional[Dict[str, Any]] = None
    challenged_squad: Optional[Dict[str, Any]] = None
    
    class Config:
        from_attributes = True

class StudyLeagueResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    subject: str
    participants: int
    max_participants: int
    entry_fee: int
    prize_pool: int
    difficulty: str
    league_type: str
    status: str
    start_date: datetime
    end_date: datetime
    created_at: datetime
    my_rank: Optional[int] = None
    my_score: Optional[int] = None
    
    class Config:
        from_attributes = True

class LeagueParticipantResponse(BaseModel):
    id: int
    username: str
    fname: str
    lname: str
    avatar: Optional[str]
    score: int
    rank: int
    questions_answered: int
    accuracy: float
    xp_earned: int
    
    class Config:
        from_attributes = True

class StudyLeagueDetailResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    subject: str
    participants: int
    max_participants: int
    entry_fee: int
    prize_pool: int
    difficulty: str
    league_type: str
    status: str
    start_date: datetime
    end_date: datetime
    created_at: datetime
    creator_id: int
    my_participation: Optional[Dict[str, Any]] = None
    top_participants: List[LeagueParticipantResponse] = []
    
    class Config:
        from_attributes = True

class PaginatedLeaguesResponse(BaseModel):
    leagues: List[StudyLeagueResponse]
    total_count: int
    page: int
    page_size: int
    has_next: bool

class LeagueLeaderboardResponse(BaseModel):
    league_info: StudyLeagueDetailResponse
    participants: List[LeagueParticipantResponse]
    total_participants: int
    page: int
    page_size: int
    has_next: bool

class NationalLeaderboardResponse(BaseModel):
    id: int
    username: str
    fname: str
    lname: str
    avatar: Optional[str]
    total_xp: int
    rank: int
    school: Optional[str] = None
    region: Optional[str] = None
    
    class Config:
        from_attributes = True

class PaginatedSquadsResponse(BaseModel):
    squads: List[SquadResponse]
    total_count: int
    page: int
    page_size: int
    has_next: bool

class PaginatedMessagesResponse(BaseModel):
    messages: List[SquadMessageResponse]
    total_count: int
    page: int
    page_size: int
    has_next: bool