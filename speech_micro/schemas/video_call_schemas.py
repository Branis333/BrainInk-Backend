from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

# Request Schemas
class CreateRoomRequest(BaseModel):
    room_name: Optional[str] = Field(None, min_length=1, max_length=255)
    room_id: Optional[str] = None
    max_participants: int = Field(10, ge=2, le=50)
    room_settings: Optional[Dict[str, Any]] = None

class JoinRoomRequest(BaseModel):
    room_id: str
    participant_settings: Optional[Dict[str, Any]] = None

class StartTranscriptionRequest(BaseModel):
    session_name: str = Field(..., min_length=1, max_length=255)
    language: str = Field("auto", max_length=10)
    session_settings: Optional[Dict[str, Any]] = None

class TranscriptionDataRequest(BaseModel):
    transcribed_text: str
    confidence_score: Optional[int] = Field(None, ge=0, le=100)
    start_time_seconds: Optional[int] = None
    duration_seconds: Optional[int] = None
    is_final: bool = True
    original_language: Optional[str] = None

class UpdateTranscriptionRequest(BaseModel):
    transcribed_text: Optional[str] = None
    sentiment: Optional[str] = None
    contains_question: Optional[bool] = None

class LeaveRoomRequest(BaseModel):
    room_id: str

class EndTranscriptionRequest(BaseModel):
    session_id: int

class AnalyzeSessionRequest(BaseModel):
    analysis_type: str = "full"
    include_sentiment: bool = True
    include_topics: bool = True

# Response Schemas
class UserInfoResponse(BaseModel):
    id: int
    username: str
    
    class Config:
        from_attributes = True

class VideoCallParticipantResponse(BaseModel):
    id: int
    user_id: int
    username: str
    joined_at: datetime
    left_at: Optional[datetime] = None
    is_currently_in_call: bool
    participant_settings: Optional[Dict[str, Any]] = None
    
    class Config:
        from_attributes = True

class VideoCallRoomResponse(BaseModel):
    id: int
    room_id: str
    room_name: str
    created_by: int
    creator_username: str
    created_at: datetime
    ended_at: Optional[datetime] = None
    is_active: bool
    max_participants: int
    current_participant_count: int
    room_settings: Optional[Dict[str, Any]] = None
    participants: List[VideoCallParticipantResponse] = []
    
    class Config:
        from_attributes = True

class TranscriptionDataResponse(BaseModel):
    id: int
    session_id: int
    user_id: int
    username: str
    transcribed_text: str
    original_language: Optional[str] = None
    confidence_score: Optional[int] = None
    timestamp: datetime
    start_time_seconds: Optional[int] = None
    duration_seconds: Optional[int] = None
    is_final: bool
    speaker_name: Optional[str] = None
    sentiment: Optional[str] = None
    word_count: int
    contains_question: bool
    
    class Config:
        from_attributes = True

class TranscriptionSessionResponse(BaseModel):
    id: int
    room_id: int
    session_name: str
    started_by: int
    started_by_username: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    is_active: bool
    language: str
    total_duration_minutes: int
    total_words: int
    participant_count: int
    session_summary: Optional[str] = None
    key_topics: Optional[List[str]] = None
    transcription_count: int = 0
    
    class Config:
        from_attributes = True

class FullTranscriptResponse(BaseModel):
    session: TranscriptionSessionResponse
    transcriptions: List[TranscriptionDataResponse]
    room_info: VideoCallRoomResponse
    
    class Config:
        from_attributes = True

class CallAnalyticsResponse(BaseModel):
    id: int
    room_id: int
    session_id: Optional[int] = None
    total_call_duration_minutes: int
    total_participants: int
    total_words_spoken: int
    most_active_speaker_id: Optional[int] = None
    most_active_speaker_username: Optional[str] = None
    speaking_time_distribution: Optional[Dict[str, Any]] = None
    question_count: int
    main_topics: Optional[List[str]] = None
    key_phrases: Optional[List[str]] = None
    overall_sentiment: Optional[str] = None
    meeting_summary: Optional[str] = None
    action_items: Optional[List[str]] = None
    discussion_highlights: Optional[List[str]] = None
    analysis_generated_at: datetime
    
    class Config:
        from_attributes = True

class SessionAnalysisResponse(BaseModel):
    session_info: TranscriptionSessionResponse
    analytics: CallAnalyticsResponse
    participant_stats: Dict[str, Any]
    timeline: List[TranscriptionDataResponse]
    insights: Dict[str, Any]
    
    class Config:
        from_attributes = True

# WebSocket Message Schemas
class WebSocketMessage(BaseModel):
    type: str
    data: Optional[Dict[str, Any]] = None
    user_id: Optional[str] = None
    user_name: Optional[str] = None
    timestamp: Optional[str] = None

class TranscriptionWebSocketData(BaseModel):
    transcribed_text: str
    confidence_score: Optional[int] = None
    is_final: bool = True
    language: Optional[str] = None

class ChatMessageData(BaseModel):
    message: str
    timestamp: Optional[str] = None

# List Response Schemas
class RoomListResponse(BaseModel):
    rooms: List[VideoCallRoomResponse]
    total: int
    active_count: int
    
class TranscriptionSessionListResponse(BaseModel):
    sessions: List[TranscriptionSessionResponse]
    total: int
    active_count: int

class UserTranscriptionHistoryResponse(BaseModel):
    user_sessions: List[TranscriptionSessionResponse]
    user_rooms: List[VideoCallRoomResponse]
    total_sessions: int
    total_words_transcribed: int
    total_call_time_minutes: int
