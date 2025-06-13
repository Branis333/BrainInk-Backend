from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum

class TournamentStatusEnum(str, Enum):
    DRAFT = "draft"
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class TournamentTypeEnum(str, Enum):
    PUBLIC = "public"
    PRIVATE = "private"
    INVITE_ONLY = "invite_only"

class BracketTypeEnum(str, Enum):
    SINGLE_ELIMINATION = "single_elimination"
    DOUBLE_ELIMINATION = "double_elimination"
    ROUND_ROBIN = "round_robin"

class DifficultyLevelEnum(str, Enum):
    ELEMENTARY = "elementary"
    MIDDLE_SCHOOL = "middle_school"
    HIGH_SCHOOL = "high_school"
    UNIVERSITY = "university"
    PROFESSIONAL = "professional"
    MIXED = "mixed"

# Tournament Creation Schemas
class PrizeConfiguration(BaseModel):
    has_prizes: bool = False
    first_place_prize: Optional[str] = None
    second_place_prize: Optional[str] = None
    third_place_prize: Optional[str] = None
    prize_type: Optional[str] = "tokens"  # tokens, xp, badge, custom

class QuestionConfiguration(BaseModel):
    total_questions: int = Field(default=50, ge=10, le=200)
    time_limit_minutes: int = Field(default=60, ge=15, le=180)
    difficulty_level: DifficultyLevelEnum = DifficultyLevelEnum.MIXED
    subject_category: Optional[str] = None
    custom_topics: Optional[List[str]] = None

class CreateTournamentRequest(BaseModel):
    name: str = Field(..., min_length=3, max_length=255)
    description: Optional[str] = None
    max_players: int = Field(..., ge=4, le=1024)
    tournament_type: TournamentTypeEnum = TournamentTypeEnum.PUBLIC
    bracket_type: BracketTypeEnum = BracketTypeEnum.SINGLE_ELIMINATION
    
    # Prize and Question configurations
    prize_config: PrizeConfiguration
    question_config: QuestionConfiguration
    
    # Timing
    registration_end: Optional[datetime] = None
    tournament_start: Optional[datetime] = None
    
    # Invitations (for private/invite-only tournaments)
    invited_users: Optional[List[int]] = None

class UpdateTournamentRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    registration_end: Optional[datetime] = None
    tournament_start: Optional[datetime] = None
    status: Optional[TournamentStatusEnum] = None

# Response Schemas
class TournamentCreatorResponse(BaseModel):
    id: int
    username: str
    
    class Config:
        from_attributes = True

class TournamentParticipantResponse(BaseModel):
    id: int
    user_id: int
    username: str
    seed_number: Optional[int]
    is_eliminated: bool
    final_position: Optional[int]
    total_score: int
    joined_at: datetime
    
    class Config:
        from_attributes = True

class TournamentResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    creator: TournamentCreatorResponse
    max_players: int
    current_players: int
    tournament_type: TournamentTypeEnum
    bracket_type: BracketTypeEnum
    status: TournamentStatusEnum
    
    # Prize info
    has_prizes: bool
    first_place_prize: Optional[str]
    second_place_prize: Optional[str]
    third_place_prize: Optional[str]
    prize_type: Optional[str]
    
    # Question info
    total_questions: int
    time_limit_minutes: int
    difficulty_level: DifficultyLevelEnum
    subject_category: Optional[str]
    
    # Timing
    registration_start: datetime
    registration_end: Optional[datetime]
    tournament_start: Optional[datetime]
    tournament_end: Optional[datetime]
    created_at: datetime
    
    class Config:
        from_attributes = True

class TournamentDetailResponse(TournamentResponse):
    participants: List[TournamentParticipantResponse]
    can_join: bool
    is_participant: bool

# Bracket Schemas
class MatchResponse(BaseModel):
    id: int
    match_number: int
    round_number: int
    player1_id: Optional[int]
    player1_username: Optional[str]
    player2_id: Optional[int]
    player2_username: Optional[str]
    winner_id: Optional[int]
    winner_username: Optional[str]
    player1_score: int
    player2_score: int
    player1_time: int
    player2_time: int
    is_completed: bool
    started_at: Optional[datetime]
    completed_at: Optional[datetime]

class BracketRoundResponse(BaseModel):
    round_number: int
    round_name: str
    total_matches: int
    matches: List[MatchResponse]

class TournamentBracketResponse(BaseModel):
    tournament_id: int
    tournament_name: str
    bracket_type: BracketTypeEnum
    total_rounds: int
    rounds: List[BracketRoundResponse]

# Tournament Actions
class JoinTournamentRequest(BaseModel):
    tournament_id: int

class InvitePlayersRequest(BaseModel):
    user_ids: List[int]
    message: Optional[str] = None

class TournamentInvitationResponse(BaseModel):
    id: int
    tournament_id: int
    tournament_name: str
    inviter_username: str
    status: str
    invited_at: datetime
    
    class Config:
        from_attributes = True

# Question Generation
class GenerateQuestionsRequest(BaseModel):
    topics: List[str]
    difficulty_level: DifficultyLevelEnum
    question_count: int = Field(..., ge=10, le=200)
    subject_category: Optional[str] = None

class TournamentQuestionResponse(BaseModel):
    id: int
    question_text: str
    option_a: str
    option_b: str
    option_c: str
    option_d: str
    category: Optional[str]
    difficulty: str
    points_value: int
    time_limit_seconds: int
    
    class Config:
        from_attributes = True

# Leaderboard and Stats
class TournamentLeaderboardEntry(BaseModel):
    position: int
    user_id: int
    username: str
    total_score: int
    questions_answered: int
    correct_answers: int
    accuracy_percentage: float
    time_spent_seconds: int
    is_eliminated: bool

class TournamentStatsResponse(BaseModel):
    tournament_id: int
    total_participants: int
    matches_completed: int
    total_matches: int
    current_round: int
    tournament_progress_percentage: float
    leaderboard: List[TournamentLeaderboardEntry]