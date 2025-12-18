from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Depends, Query, status
from typing import Dict, List, Optional
from pydantic import BaseModel
import uuid
import json
import asyncio
from datetime import datetime, timedelta
import logging
import os
import base64
import tempfile
import wave
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc
# Import database and auth dependencies
from db.connection import db_dependency
from db.verify_token import user_dependency
from models.video_call_models import VideoCallRoom, VideoCallParticipant, TranscriptionSession, TranscriptionData, CallAnalytics
from models.other_models import User, USERS_TABLE_EXISTS
from schemas.video_call_schemas import *

def get_user_info(db: Session, user_id: int, fallback_username: str = "Unknown") -> dict:
    """Get user info from the users table or fallback to user_id."""
    user = None
    try:
        user = db.query(User).filter(User.c.id == user_id).first()
    except Exception:
        pass
    if user:
        return {"user_id": user_id, "username": getattr(user, "username", fallback_username)}
    return {"user_id": user_id, "username": fallback_username}

def get_multiple_users_info(db: Session, user_ids: list, fallback_prefix: str = "User") -> dict:
    """Get multiple users info at once"""
    users_info = {}
    
    if USERS_TABLE_EXISTS and User is not None:
        try:
            users = db.query(User).filter(User.c.id.in_(user_ids)).all()
            for user in users:
                users_info[user.id] = {"id": user.id, "username": user.username}
        except Exception as e:
            logger.warning(f"Error fetching users {user_ids}: {e}")
    
    # Fill in missing users with fallback
    for user_id in user_ids:
        if user_id not in users_info:
            users_info[user_id] = {"id": user_id, "username": f"{fallback_prefix}_{user_id}"}
    
    return users_info

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/video-call", tags=["Video Calls"])

# Store active WebSocket connections
call_connections: Dict[str, Dict[str, WebSocket]] = {}

class VideoCallManager:
    def __init__(self):
        self.connections = call_connections
        self.user_room_mapping: Dict[str, str] = {}  # Maps user_id (as str) to room_id

    def create_call_room(self, db: Session, user_id: int, room_data: CreateRoomRequest) -> VideoCallRoom:
        """Create a new video call room in database"""
        room_id = room_data.room_id or str(uuid.uuid4())
        
        # Check if room_id already exists
        existing_room = db.query(VideoCallRoom).filter(VideoCallRoom.room_id == room_id).first()
        if existing_room:
            if existing_room.is_active:
                raise HTTPException(status_code=400, detail="Room ID already exists and is active")
            else:
                # Reactivate the room
                existing_room.is_active = True
                existing_room.ended_at = None
                db.commit()
                db.refresh(existing_room)
                return existing_room
        
        # Create new room
        new_room = VideoCallRoom(
            room_id=room_id,
            room_name=room_data.room_name or f"Room {room_id[:8]}",
            created_by=user_id,
            max_participants=room_data.max_participants,
            room_settings=room_data.room_settings
        )
        
        db.add(new_room)
        db.commit()
        db.refresh(new_room)
        
        # Initialize connections dict for this room
        self.connections[room_id] = {}
        
        logger.info(f"Created new video call room: {room_id} by user {user_id}")
        return new_room

    def join_call(self, db: Session, room_id: str, user_id: int, websocket: WebSocket) -> VideoCallParticipant:
        """Add a participant to a video call"""
        # Get room from database
        room = db.query(VideoCallRoom).filter(
            VideoCallRoom.room_id == room_id,
            VideoCallRoom.is_active == True
        ).first()
        
        if not room:
            raise HTTPException(status_code=404, detail="Room not found or inactive")
        
        # Check if user is already a participant
        existing_participant = db.query(VideoCallParticipant).filter(
            and_(
                VideoCallParticipant.room_id == room.id,
                VideoCallParticipant.user_id == user_id,
                VideoCallParticipant.is_currently_in_call == True
            )
        ).first()
        
        if existing_participant:
            # Update existing participant
            existing_participant.is_currently_in_call = True
            existing_participant.left_at = None
            participant = existing_participant
        else:
            # Create new participant
            participant = VideoCallParticipant(
                room_id=room.id,
                user_id=user_id,
                is_currently_in_call=True
            )
            db.add(participant)
        
        db.commit()
        db.refresh(participant)
        
        # Store WebSocket connection
        if room_id not in self.connections:
            self.connections[room_id] = {}
        self.connections[room_id][str(user_id)] = websocket
        
        # Update user room mapping
        self.user_room_mapping[str(user_id)] = room_id
        
        logger.info(f"User {user_id} joined call {room_id}")
        return participant

    def leave_call(self, db: Session, room_id: str, user_id: int):
        """Remove a participant from a video call"""
        # Update participant in database
        room = db.query(VideoCallRoom).filter(VideoCallRoom.room_id == room_id).first()
        if room:
            participant = db.query(VideoCallParticipant).filter(
                and_(
                    VideoCallParticipant.room_id == room.id,
                    VideoCallParticipant.user_id == user_id,
                    VideoCallParticipant.is_currently_in_call == True
                )
            ).first()
            
            if participant:
                participant.is_currently_in_call = False
                participant.left_at = datetime.utcnow()
                db.commit()
        
        # Remove WebSocket connection
        if room_id in self.connections and str(user_id) in self.connections[room_id]:
            del self.connections[room_id][str(user_id)]
        
        # Remove from user room mapping
        if str(user_id) in self.user_room_mapping:
            del self.user_room_mapping[str(user_id)]
            
            # Clean up empty rooms
            if room_id in self.connections and not self.connections[room_id]:
                del self.connections[room_id]
                # Mark room as inactive if no active participants
                if room:
                    active_participants = db.query(VideoCallParticipant).filter(
                        and_(
                            VideoCallParticipant.room_id == room.id,
                            VideoCallParticipant.is_currently_in_call == True
                        )
                    ).count()
                    
                    if active_participants == 0:
                        room.is_active = False
                        room.ended_at = datetime.utcnow()
                        db.commit()
                        logger.info(f"Marked room {room_id} as inactive")
        
        logger.info(f"User {user_id} left call {room_id}")

    async def broadcast_to_room(self, room_id: str, message: dict, exclude_user: str = None):
        """Broadcast a message to all participants in a room"""
        if room_id not in self.connections:
            return

        disconnected_users = []
        for user_id, websocket in self.connections[room_id].items():
            if exclude_user and user_id == exclude_user:
                continue
            
            try:
                await websocket.send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Failed to send message to user {user_id}: {e}")
                disconnected_users.append(user_id)

        # Note: We don't clean up disconnected users here as it will be handled by WebSocket disconnect

# Global video call manager
call_manager = VideoCallManager()

@router.post("/create-room", response_model=VideoCallRoomResponse)
async def create_room(
    request: CreateRoomRequest,
    db: db_dependency,
    current_user: user_dependency
):
    """Create a new video call room"""
    try:
        room = call_manager.create_call_room(db, current_user["user_id"], request)
        
        # Get creator username
        creator_info = get_user_info(db, current_user["user_id"], current_user["username"])
        
        return VideoCallRoomResponse(
            id=room.id,
            room_id=room.room_id,
            room_name=room.room_name,
            created_by=room.created_by,
            creator_username=creator_info["username"],
            created_at=room.created_at,
            ended_at=room.ended_at,
            is_active=room.is_active,
            max_participants=room.max_participants,
            current_participant_count=0,
            room_settings=room.room_settings,
            participants=[]
        )
    except Exception as e:
        logger.error(f"Error creating room: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/room/{room_id}", response_model=VideoCallRoomResponse)
async def get_room_info(
    room_id: str,
    db: db_dependency,
    current_user: user_dependency
):
    """Get information about a specific room"""
    room = db.query(VideoCallRoom).filter(
        VideoCallRoom.room_id == room_id,
        VideoCallRoom.is_active == True
    ).first()
    
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    # Get participants
    participants = db.query(VideoCallParticipant).filter(
        and_(
            VideoCallParticipant.room_id == room.id,
            VideoCallParticipant.is_currently_in_call == True
        )
    ).all()
    
    participant_responses = []
    for participant in participants:
        user_info = get_user_info(db, participant.user_id, "Unknown")
        participant_responses.append(VideoCallParticipantResponse(
            id=participant.id,
            user_id=participant.user_id,
            username=user_info["username"],
            joined_at=participant.joined_at,
            left_at=participant.left_at,
            is_currently_in_call=participant.is_currently_in_call,
            participant_settings=participant.participant_settings
        ))
    
    # Get creator username
    creator_info = get_user_info(db, room.created_by, "Unknown")
    
    return VideoCallRoomResponse(
        id=room.id,
        room_id=room.room_id,
        room_name=room.room_name,
        created_by=room.created_by,
        creator_username=creator_info["username"],
        created_at=room.created_at,
        ended_at=room.ended_at,
        is_active=room.is_active,
        max_participants=room.max_participants,
        current_participant_count=len(participant_responses),
        room_settings=room.room_settings,
        participants=participant_responses
    )

@router.get("/my-rooms", response_model=RoomListResponse)
async def get_my_rooms(
    db: db_dependency,
    current_user: user_dependency,
    include_inactive: bool = Query(False, description="Include inactive rooms")
):
    """Get rooms created by or participated in by the current user"""
    
    # Get rooms created by user
    created_rooms_query = db.query(VideoCallRoom).filter(VideoCallRoom.created_by == current_user["user_id"])
    if not include_inactive:
        created_rooms_query = created_rooms_query.filter(VideoCallRoom.is_active == True)
    created_rooms = created_rooms_query.all()
    
    # Get rooms user participated in
    participated_room_ids = db.query(VideoCallParticipant.room_id).filter(
        VideoCallParticipant.user_id == current_user["user_id"]
    ).distinct().all()
    
    participated_rooms = []
    if participated_room_ids:
        room_ids = [r[0] for r in participated_room_ids]
        participated_rooms_query = db.query(VideoCallRoom).filter(VideoCallRoom.id.in_(room_ids))
        if not include_inactive:
            participated_rooms_query = participated_rooms_query.filter(VideoCallRoom.is_active == True)
        participated_rooms = participated_rooms_query.all()
    
    # Combine and deduplicate rooms
    all_rooms = {room.id: room for room in created_rooms + participated_rooms}
    rooms = list(all_rooms.values())
    
    # Convert to response format
    room_responses = []
    for room in rooms:
        creator = db.query(User).filter(User.c.id == room.created_by).first()
        active_participants = db.query(VideoCallParticipant).filter(
            and_(
                VideoCallParticipant.room_id == room.id,
                VideoCallParticipant.is_currently_in_call == True
            )
        ).count()
        
        room_responses.append(VideoCallRoomResponse(
            id=room.id,
            room_id=room.room_id,
            room_name=room.room_name,
            created_by=room.created_by,
            creator_username=creator.username if creator else "Unknown",
            created_at=room.created_at,
            ended_at=room.ended_at,
            is_active=room.is_active,
            max_participants=room.max_participants,
            current_participant_count=active_participants,
            room_settings=room.room_settings,
            participants=[]  # Don't include detailed participants in list view
        ))
    
    active_count = sum(1 for room in room_responses if room.is_active)
    
    return RoomListResponse(
        rooms=room_responses,
        total=len(room_responses),
        active_count=active_count
    )

@router.get("/active-rooms", response_model=RoomListResponse)
async def list_active_rooms(
    db: db_dependency,
    current_user: user_dependency,
    limit: int = Query(50, ge=1, le=100)
):
    """List all active video call rooms"""
    rooms = db.query(VideoCallRoom).filter(
        VideoCallRoom.is_active == True
    ).order_by(desc(VideoCallRoom.created_at)).limit(limit).all()
    
    room_responses = []
    for room in rooms:
        creator = db.query(User).filter(User.c.id == room.created_by).first()
        active_participants = db.query(VideoCallParticipant).filter(
            and_(
                VideoCallParticipant.room_id == room.id,
                VideoCallParticipant.is_currently_in_call == True
            )
        ).count()
        
        room_responses.append(VideoCallRoomResponse(
            id=room.id,
            room_id=room.room_id,
            room_name=room.room_name,
            created_by=room.created_by,
            creator_username=creator.username if creator else "Unknown",
            created_at=room.created_at,
            ended_at=room.ended_at,
            is_active=room.is_active,
            max_participants=room.max_participants,
            current_participant_count=active_participants,
            room_settings=room.room_settings,
            participants=[]
        ))
    
    return RoomListResponse(
        rooms=room_responses,
        total=len(room_responses),
        active_count=len(room_responses)
    )

@router.websocket("/room/{room_id}/ws")
async def video_call_websocket(
    websocket: WebSocket, 
    room_id: str, 
    token: str = Query(...),  # Require authentication token
):
    """WebSocket endpoint for video call participants with authentication"""
    
    # Get database session
    from db.connection import get_db
    db = next(get_db())
    
    # Authenticate user from token
    try:
        from jose import jwt, JWTError
        import os
        SECRET_KEY = os.getenv("SECRET_KEY")
        ALGORITHM = os.getenv("ALGORITHM")
        
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("uname")
        user_id: int = payload.get("id")
        
        if username is None or user_id is None:
            await websocket.close(code=1008, reason="Authentication required")
            return
            
    except (JWTError, ImportError) as e:
        logger.error(f"Authentication error: {e}")
        await websocket.close(code=1008, reason="Invalid token")
        return
    
    await websocket.accept()
    
    try:
        # Join the call in database
        participant = call_manager.join_call(db, room_id, user_id, websocket)
        
        # Get user info
        user = db.query(User).filter(User.c.id == user_id).first()
        user_name = user.username if user else username
        
        # Get current participants for welcome message
        room = db.query(VideoCallRoom).filter(VideoCallRoom.room_id == room_id).first()
        current_participants = db.query(VideoCallParticipant).filter(
            and_(
                VideoCallParticipant.room_id == room.id,
                VideoCallParticipant.is_currently_in_call == True
            )
        ).all()
        
        participant_list = {}
        for p in current_participants:
            p_user = db.query(User).filter(User.c.id == p.user_id).first()
            participant_list[str(p.user_id)] = {
                "id": p.user_id,
                "name": p_user.username if p_user else "Unknown",
                "joined_at": p.joined_at.isoformat(),
                "transcription_active": False
            }
        
        # Notify others that user joined
        await call_manager.broadcast_to_room(room_id, {
            "type": "user_joined",
            "user_id": str(user_id),
            "user_name": user_name,
            "timestamp": datetime.now().isoformat(),
            "participants": list(participant_list.keys())
        }, exclude_user=str(user_id))
        
        # Send welcome message to the user
        await websocket.send_text(json.dumps({
            "type": "joined_room",
            "room_id": room_id,
            "user_id": str(user_id),
            "participants": participant_list,
            "message": f"Welcome to {room.room_name}"
        }))
        
        # Listen for messages
        while True:
            try:
                data = await websocket.receive_text()
                message = json.loads(data)
                
                # Handle different message types
                if message["type"] == "transcription_update":
                    # Store transcription data if session is active
                    active_session = db.query(TranscriptionSession).filter(
                        and_(
                            TranscriptionSession.room_id == room.id,
                            TranscriptionSession.is_active == True
                        )
                    ).first()
                    
                    if active_session:
                        transcription_data = message.get("data", {})
                        
                        # Create transcription record
                        transcription = TranscriptionData(
                            session_id=active_session.id,
                            participant_id=participant.id,
                            user_id=user_id,
                            transcribed_text=transcription_data.get("transcribed_text", ""),
                            confidence_score=transcription_data.get("confidence_score"),
                            is_final=transcription_data.get("is_final", True),
                            speaker_name=user_name,
                            original_language=transcription_data.get("language"),
                            word_count=len(transcription_data.get("transcribed_text", "").split())
                        )
                        
                        if transcription_data.get("is_final", True):
                            db.add(transcription)
                            db.commit()
                            
                            # Update session stats
                            active_session.total_words += transcription.word_count
                            db.commit()
                    
                    # Broadcast transcription updates to other participants
                    await call_manager.broadcast_to_room(room_id, {
                        "type": "transcription_received",
                        "user_id": str(user_id),
                        "user_name": user_name,
                        "transcription_data": message.get("data"),
                        "timestamp": datetime.now().isoformat()
                    }, exclude_user=str(user_id))
                
                elif message["type"] == "transcription_status":
                    # Update participant transcription status
                    participant.participant_settings = participant.participant_settings or {}
                    participant.participant_settings.update({
                        "transcription_active": message.get("active", False),
                        "language": message.get("language", "auto")
                    })
                    db.commit()
                    
                    # Broadcast status update
                    await call_manager.broadcast_to_room(room_id, {
                        "type": "user_transcription_status",
                        "user_id": str(user_id),
                        "user_name": user_name,
                        "transcription_active": message.get("active", False),
                        "language": message.get("language", "auto"),
                        "timestamp": datetime.now().isoformat()
                    })
                
                elif message["type"] in ["offer", "answer", "ice-candidate"]:
                    # Forward WebRTC signaling messages
                    target_user = message.get("target_user")
                    if target_user and target_user in call_manager.connections.get(room_id, {}):
                        await call_manager.connections[room_id][target_user].send_text(json.dumps({
                            **message,
                            "from_user": str(user_id),
                            "from_user_name": user_name
                        }))
                
                elif message["type"] == "chat_message":
                    # Broadcast chat messages
                    await call_manager.broadcast_to_room(room_id, {
                        "type": "chat_message",
                        "user_id": str(user_id),
                        "user_name": user_name,
                        "message": message.get("message", ""),
                        "timestamp": datetime.now().isoformat()
                    })
                
                else:
                    # Broadcast other message types to all participants
                    await call_manager.broadcast_to_room(room_id, {
                        **message,
                        "from_user": str(user_id),
                        "from_user_name": user_name,
                        "timestamp": datetime.now().isoformat()
                    })
                    
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Error handling message from {user_id}: {e}")
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": f"Error processing message: {str(e)}"
                }))
    
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"Error in video call websocket for user {user_id}: {e}")
    finally:
        # Clean up when user disconnects
        call_manager.leave_call(db, room_id, user_id)
        
        # Notify others that user left
        try:
            await call_manager.broadcast_to_room(room_id, {
                "type": "user_left",
                "user_id": str(user_id),
                "user_name": user_name,
                "timestamp": datetime.now().isoformat()
            })
        except Exception as e:
            logger.error(f"Error broadcasting user left message: {e}")
        finally:
            db.close()

# Transcription Endpoints
@router.post("/room/{room_id}/start-transcription", response_model=TranscriptionSessionResponse)
async def start_transcription_session(
    room_id: str,
    request: StartTranscriptionRequest,
    db: db_dependency,
    current_user: user_dependency
):
    """Start a transcription session for a room"""
    # Verify room exists and user has access
    room = db.query(VideoCallRoom).filter(
        VideoCallRoom.room_id == room_id,
        VideoCallRoom.is_active == True
    ).first()
    
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    # Check if user is participant or creator
    is_participant = db.query(VideoCallParticipant).filter(
        and_(
            VideoCallParticipant.room_id == room.id,
            VideoCallParticipant.user_id == current_user["user_id"],
            VideoCallParticipant.is_currently_in_call == True
        )
    ).first()
    
    if not is_participant and room.created_by != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Not authorized to start transcription in this room")
    
    # Create transcription session
    session = TranscriptionSession(
        room_id=room.id,
        session_name=request.session_name,
        started_by=current_user["user_id"],
        language=request.language,
        session_settings=request.session_settings
    )
    
    db.add(session)
    db.commit()
    db.refresh(session)
    
    # Get starter username
    starter = db.query(User).filter(User.c.id == current_user["user_id"]).first()
    
    return TranscriptionSessionResponse(
        id=session.id,
        room_id=session.room_id,
        session_name=session.session_name,
        started_by=session.started_by,
        started_by_username=starter.username if starter else current_user["username"],
        started_at=session.started_at,
        ended_at=session.ended_at,
        is_active=session.is_active,
        language=session.language,
        total_duration_minutes=session.total_duration_minutes,
        total_words=session.total_words,
        participant_count=session.participant_count,
        session_summary=session.session_summary,
        key_topics=session.key_topics,
        transcription_count=0
    )

@router.post("/end-transcription")
async def end_transcription(
    request: EndTranscriptionRequest,
    db: db_dependency,
    current_user: user_dependency
):
    """End a transcription session"""
    try:
        session = db.query(TranscriptionSession).filter(
            TranscriptionSession.id == request.session_id,
            TranscriptionSession.is_active == True
        ).first()
        
        if not session:
            raise HTTPException(status_code=404, detail="Active transcription session not found")
        
        # Verify user can end session (creator or session starter)
        room = db.query(VideoCallRoom).filter(VideoCallRoom.id == session.room_id).first()
        if session.started_by != current_user["user_id"] and room.created_by != current_user["user_id"]:
            raise HTTPException(status_code=403, detail="Not authorized to end this session")
        
        # Update session
        session.is_active = False
        session.ended_at = datetime.utcnow()
        
        # Calculate final stats
        transcriptions = db.query(TranscriptionData).filter(
            TranscriptionData.session_id == request.session_id,
            TranscriptionData.is_final == True
        ).all()
        
        if transcriptions:
            session.total_words = sum(t.word_count for t in transcriptions)
            session.participant_count = len(set(t.user_id for t in transcriptions))
            
            if session.started_at and session.ended_at:
                duration = session.ended_at - session.started_at
                session.total_duration_minutes = int(duration.total_seconds() / 60)
        
        db.commit()
        
        return {"success": True, "message": "Transcription session ended", "session_id": request.session_id}
        
    except Exception as e:
        logger.error(f"Error ending transcription: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/session/{session_id}/add-transcription")
async def add_transcription(
    session_id: int,
    request: TranscriptionDataRequest,
    db: db_dependency,
    current_user: user_dependency
):
    """Add transcription data to a session"""
    try:
        # Use session_id from path parameter
        # Verify session exists and is active
        session = db.query(TranscriptionSession).filter(
            TranscriptionSession.id == session_id,
            TranscriptionSession.is_active == True
        ).first()
        
        if not session:
            raise HTTPException(status_code=404, detail="Transcription session not found")
        
        # Get room info
        room = db.query(VideoCallRoom).filter(VideoCallRoom.id == session.room_id).first()
        if not room:
            raise HTTPException(status_code=404, detail="Associated room not found")
        
        # Get participant info
        participant = db.query(VideoCallParticipant).filter(
            and_(
                VideoCallParticipant.room_id == room.id,
                VideoCallParticipant.user_id == current_user["user_id"]
            )
        ).first()
        
        if not participant:
            raise HTTPException(status_code=403, detail="Not a participant in this room")
        
        # Get user info for speaker name
        user_info = get_user_info(db, current_user["user_id"], current_user["username"])
        
        # Create transcription data
        transcription = TranscriptionData(
            session_id=session_id,  # Use session_id from path parameter
            participant_id=participant.id,
            user_id=current_user["user_id"],
            transcribed_text=request.transcribed_text,
            original_language=request.original_language,
            confidence_score=request.confidence_score,
            start_time_seconds=request.start_time_seconds,
            duration_seconds=request.duration_seconds,
            is_final=request.is_final,
            speaker_name=user_info["username"],
            word_count=len(request.transcribed_text.split())
        )
        
        db.add(transcription)
        
        # Update session stats
        if request.is_final:
            session.total_words += transcription.word_count
        
        db.commit()
        db.refresh(transcription)
        
        return {"success": True, "transcription_id": transcription.id}
        
    except Exception as e:
        logger.error(f"Error adding transcription: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/analyze-session/{session_id}", response_model=SessionAnalysisResponse)
async def analyze_session_endpoint(
    session_id: int,
    request: AnalyzeSessionRequest,
    db: db_dependency,
    current_user: user_dependency
):
    """Analyze a transcription session"""
    try:
        # Get session
        session = db.query(TranscriptionSession).filter(TranscriptionSession.id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Transcription session not found")
        
        # Get room
        room = db.query(VideoCallRoom).filter(VideoCallRoom.id == session.room_id).first()
        if not room:
            raise HTTPException(status_code=404, detail="Associated room not found")
        
        # Check access
        is_participant = db.query(VideoCallParticipant).filter(
            and_(
                VideoCallParticipant.room_id == room.id,
                VideoCallParticipant.user_id == current_user["user_id"]
            )
        ).first()
        
        if not is_participant and room.created_by != current_user["user_id"]:
            raise HTTPException(status_code=403, detail="Not authorized to analyze this session")
        
        # Get or create analytics
        analytics = db.query(CallAnalytics).filter(CallAnalytics.session_id == session_id).first()
        
        if not analytics:
            # Generate new analytics
            transcriptions = db.query(TranscriptionData).filter(
                TranscriptionData.session_id == session_id,
                TranscriptionData.is_final == True
            ).all()
            
            # Calculate metrics
            total_words = sum(t.word_count for t in transcriptions)
            participant_word_counts = {}
            question_count = sum(1 for t in transcriptions if t.contains_question)
            
            for t in transcriptions:
                if t.user_id not in participant_word_counts:
                    participant_word_counts[t.user_id] = 0
                participant_word_counts[t.user_id] += t.word_count
            
            # Find most active speaker
            most_active_speaker_id = None
            if participant_word_counts:
                most_active_speaker_id = max(participant_word_counts, key=participant_word_counts.get)
            
            # Generate insights (simplified version)
            main_topics = ["Communication", "Collaboration", "Discussion"]
            key_phrases = ["important point", "let's discuss", "I think"]
            
            # Create analytics record
            analytics = CallAnalytics(
                room_id=room.id,
                session_id=session_id,
                total_call_duration_minutes=session.total_duration_minutes,
                total_participants=len(participant_word_counts),
                total_words_spoken=total_words,
                most_active_speaker_id=most_active_speaker_id,
                speaking_time_distribution={str(k): v for k, v in participant_word_counts.items()},
                question_count=question_count,
                main_topics=main_topics,
                key_phrases=key_phrases,
                overall_sentiment=request.include_sentiment and "neutral" or None,
                meeting_summary=f"Session '{session.session_name}' with {len(participant_word_counts)} participants discussing various topics.",
                action_items=["Follow up on discussed topics", "Schedule next meeting"],
                discussion_highlights=[f"Total of {total_words} words spoken", f"{question_count} questions asked"]
            )
            
            db.add(analytics)
            db.commit()
            db.refresh(analytics)
        
        # Build session response
        starter_info = get_user_info(db, session.started_by, "Unknown")
        session_response = TranscriptionSessionResponse(
            id=session.id,
            room_id=session.room_id,
            session_name=session.session_name,
            started_by=session.started_by,
            started_by_username=starter_info["username"],
            started_at=session.started_at,
            ended_at=session.ended_at,
            is_active=session.is_active,
            language=session.language,
            total_duration_minutes=session.total_duration_minutes,
            total_words=session.total_words,
            participant_count=session.participant_count,
            session_summary=session.session_summary,
            key_topics=session.key_topics,
            transcription_count=0
        )
        
        # Get most active speaker username
        most_active_speaker_username = None
        if analytics.most_active_speaker_id:
            speaker_info = get_user_info(db, analytics.most_active_speaker_id, "Unknown")
            most_active_speaker_username = speaker_info["username"]
        
        analytics_response = CallAnalyticsResponse(
            id=analytics.id,
            room_id=analytics.room_id,
            session_id=analytics.session_id,
            total_call_duration_minutes=analytics.total_call_duration_minutes,
            total_participants=analytics.total_participants,
            total_words_spoken=analytics.total_words_spoken,
            most_active_speaker_id=analytics.most_active_speaker_id,
            most_active_speaker_username=most_active_speaker_username,
            speaking_time_distribution=analytics.speaking_time_distribution,
            question_count=analytics.question_count,
            main_topics=analytics.main_topics,
            key_phrases=analytics.key_phrases,
            overall_sentiment=analytics.overall_sentiment,
            meeting_summary=analytics.meeting_summary,
            action_items=analytics.action_items,
            discussion_highlights=analytics.discussion_highlights,
            analysis_generated_at=analytics.analysis_generated_at
        )
        
        # Get timeline (chronological transcriptions)
        timeline_transcriptions = db.query(TranscriptionData).filter(
            TranscriptionData.session_id == session_id,
            TranscriptionData.is_final == True
        ).order_by(TranscriptionData.timestamp).all()
        
        timeline = []
        for t in timeline_transcriptions:
            user_info = get_user_info(db, t.user_id, "Unknown")
            timeline.append(TranscriptionDataResponse(
                id=t.id,
                session_id=t.session_id,
                user_id=t.user_id,
                username=user_info["username"],
                transcribed_text=t.transcribed_text,
                original_language=t.original_language,
                confidence_score=t.confidence_score,
                timestamp=t.timestamp,
                start_time_seconds=t.start_time_seconds,
                duration_seconds=t.duration_seconds,
                is_final=t.is_final,
                speaker_name=t.speaker_name,
                sentiment=t.sentiment,
                word_count=t.word_count,
                contains_question=t.contains_question
            ))
        
        # Participant stats
        participant_stats = {}
        if analytics.speaking_time_distribution:
            for user_id_str, word_count in analytics.speaking_time_distribution.items():
                user_id_int = int(user_id_str)
                user_info = get_user_info(db, user_id_int, "Unknown")
                username = user_info["username"]
                
                participant_stats[username] = {
                    "word_count": word_count,
                    "percentage": round((word_count / analytics.total_words_spoken) * 100, 1) if analytics.total_words_spoken > 0 else 0,
                    "user_id": user_id_int
                }
        
        # Additional insights
        insights = {
            "engagement_level": "high" if analytics.total_words_spoken > 500 else "medium" if analytics.total_words_spoken > 200 else "low",
            "conversation_balance": "balanced" if len(participant_stats) > 1 and max(p["percentage"] for p in participant_stats.values()) < 60 else "dominated",
            "interaction_type": "discussion" if analytics.question_count > 5 else "presentation" if analytics.question_count < 2 else "meeting",
            "key_metrics": {
                "words_per_participant": round(analytics.total_words_spoken / analytics.total_participants, 1) if analytics.total_participants > 0 else 0,
                "questions_per_minute": round(analytics.question_count / analytics.total_call_duration_minutes, 2) if analytics.total_call_duration_minutes > 0 else 0
            }
        }
        
        return SessionAnalysisResponse(
            session_info=session_response,
            analytics=analytics_response,
            participant_stats=participant_stats,
            timeline=timeline,
            insights=insights
        )
        
    except Exception as e:
        logger.error(f"Error analyzing session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/full-transcript/{session_id}", response_model=FullTranscriptResponse)
async def get_full_transcript_endpoint(
    session_id: int,
    db: db_dependency,
    current_user: user_dependency
):
    """Get full transcript for a session"""
    try:
        # Get session
        session = db.query(TranscriptionSession).filter(TranscriptionSession.id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Transcription session not found")
        
        # Get room
        room = db.query(VideoCallRoom).filter(VideoCallRoom.id == session.room_id).first()
        if not room:
            raise HTTPException(status_code=404, detail="Associated room not found")
        
        # Check access (participant or creator)
        is_participant = db.query(VideoCallParticipant).filter(
            and_(
                VideoCallParticipant.room_id == room.id,
                VideoCallParticipant.user_id == current_user["user_id"]
            )
        ).first()
        
        if not is_participant and room.created_by != current_user["user_id"]:
            raise HTTPException(status_code=403, detail="Not authorized to view this transcript")
        
        # Get transcription data
        transcriptions = db.query(TranscriptionData).filter(
            TranscriptionData.session_id == session.id,
            TranscriptionData.is_final == True
        ).order_by(TranscriptionData.timestamp).all()
        
        transcription_responses = []
        for t in transcriptions:
            user_info = get_user_info(db, t.user_id, "Unknown")
            transcription_responses.append(TranscriptionDataResponse(
                id=t.id,
                session_id=t.session_id,
                user_id=t.user_id,
                username=user_info["username"],
                transcribed_text=t.transcribed_text,
                original_language=t.original_language,
                confidence_score=t.confidence_score,
                timestamp=t.timestamp,
                start_time_seconds=t.start_time_seconds,
                duration_seconds=t.duration_seconds,
                is_final=t.is_final,
                speaker_name=t.speaker_name,
                sentiment=t.sentiment,
                word_count=t.word_count,
                contains_question=t.contains_question
            ))
        
        # Build responses
        starter_info = get_user_info(db, session.started_by, "Unknown")
        session_response = TranscriptionSessionResponse(
            id=session.id,
            room_id=session.room_id,
            session_name=session.session_name,
            started_by=session.started_by,
            started_by_username=starter_info["username"],
            started_at=session.started_at,
            ended_at=session.ended_at,
            is_active=session.is_active,
            language=session.language,
            total_duration_minutes=session.total_duration_minutes,
            total_words=session.total_words,
            participant_count=session.participant_count,
            session_summary=session.session_summary,
            key_topics=session.key_topics,
            transcription_count=len(transcription_responses)
        )
        
        creator_info = get_user_info(db, room.created_by, "Unknown")
        room_response = VideoCallRoomResponse(
            id=room.id,
            room_id=room.room_id,
            room_name=room.room_name,
            created_by=room.created_by,
            creator_username=creator_info["username"],
            created_at=room.created_at,
            ended_at=room.ended_at,
            is_active=room.is_active,
            max_participants=room.max_participants,
            current_participant_count=0,
            room_settings=room.room_settings,
            participants=[]
        )
        
        return FullTranscriptResponse(
            session=session_response,
            transcriptions=transcription_responses,
            room_info=room_response
        )
        
    except Exception as e:
        logger.error(f"Error getting transcript: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/join-room", response_model=VideoCallRoomResponse)
async def join_room(
    request: JoinRoomRequest,
    db: db_dependency,
    current_user: user_dependency
):
    """Join an existing video call room"""
    try:
        # Check if room exists and is active
        room = db.query(VideoCallRoom).filter(
            VideoCallRoom.room_id == request.room_id,
            VideoCallRoom.is_active == True
        ).first()
        
        if not room:
            raise HTTPException(status_code=404, detail="Room not found or inactive")
        
        # Check room capacity
        current_participants = db.query(VideoCallParticipant).filter(
            and_(
                VideoCallParticipant.room_id == room.id,
                VideoCallParticipant.is_currently_in_call == True
            )
        ).count()
        
        if current_participants >= room.max_participants:
            raise HTTPException(status_code=400, detail="Room is at maximum capacity")
        
        # Check if user is already in the room
        existing_participant = db.query(VideoCallParticipant).filter(
            and_(
                VideoCallParticipant.room_id == room.id,
                VideoCallParticipant.user_id == current_user["user_id"],
                VideoCallParticipant.is_currently_in_call == True
            )
        ).first()
        
        if existing_participant:
            # User is already in the room, just return room info
            pass
        else:
            # Add user as participant
            participant = VideoCallParticipant(
                room_id=room.id,
                user_id=current_user["user_id"],
                is_currently_in_call=True
            )
            db.add(participant)
            db.commit()
        
        # Get all current participants
        participants = db.query(VideoCallParticipant).filter(
            and_(
                VideoCallParticipant.room_id == room.id,
                VideoCallParticipant.is_currently_in_call == True
            )
        ).all()
        
        participant_responses = []
        for participant in participants:
            user_info = get_user_info(db, participant.user_id, "Unknown")
            participant_responses.append(VideoCallParticipantResponse(
                id=participant.id,
                user_id=participant.user_id,
                username=user_info["username"],
                joined_at=participant.joined_at,
                left_at=participant.left_at,
                is_currently_in_call=participant.is_currently_in_call,
                participant_settings=participant.participant_settings
            ))
        
        # Get creator username
        creator_info = get_user_info(db, room.created_by, "Unknown")
        
        return VideoCallRoomResponse(
            id=room.id,
            room_id=room.room_id,
            room_name=room.room_name,
            created_by=room.created_by,
            creator_username=creator_info["username"],
            created_at=room.created_at,
            ended_at=room.ended_at,
            is_active=room.is_active,
            max_participants=room.max_participants,
            current_participant_count=len(participant_responses),
            room_settings=room.room_settings,
            participants=participant_responses
        )
        
    except Exception as e:
        logger.error(f"Error joining room: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/leave-room")
async def leave_room(
    request: LeaveRoomRequest,
    db: db_dependency,
    current_user: user_dependency
):
    """Leave a video call room"""
    try:
        call_manager.leave_call(db, request.room_id, current_user["user_id"])
        return {"success": True, "message": "Left room successfully"}
    except Exception as e:
        logger.error(f"Error leaving room: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.websocket("/transcription/live")
async def transcription_websocket(
    websocket: WebSocket,
    token: str = Query(...),
    session_id: int = Query(...),
    language: str = Query("auto")
):
    """WebSocket endpoint for live transcription with authentication"""
    
    # Get database session
    from db.connection import get_db
    db = next(get_db())
    
    # Authenticate user from token
    try:
        from jose import jwt, JWTError
        import os
        SECRET_KEY = os.getenv("SECRET_KEY")
        ALGORITHM = os.getenv("ALGORITHM")
        
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("uname")
        user_id: int = payload.get("id")
        
        if username is None or user_id is None:
            await websocket.close(code=1008, reason="Authentication required")
            return
            
    except (JWTError, ImportError) as e:
        logger.error(f"Transcription authentication error: {e}")
        await websocket.close(code=1008, reason="Invalid token")
        return
    
    # Verify session exists and user has access
    session = db.query(TranscriptionSession).filter(
        TranscriptionSession.id == session_id,
        TranscriptionSession.is_active == True
    ).first()
    
    if not session:
        await websocket.close(code=1008, reason="Session not found or inactive")
        return
    
    # Verify user has access to this session
    room = db.query(VideoCallRoom).filter(VideoCallRoom.id == session.room_id).first()
    if not room:
        await websocket.close(code=1008, reason="Room not found")
        return
    
    # Check if user is participant or creator
    is_participant = db.query(VideoCallParticipant).filter(
        and_(
            VideoCallParticipant.room_id == room.id,
            VideoCallParticipant.user_id == user_id,
            VideoCallParticipant.is_currently_in_call == True
        )
    ).first()
    
    if not is_participant and room.created_by != user_id:
        await websocket.close(code=1008, reason="Not authorized for this session")
        return
    
    await websocket.accept()
    
    try:
        # Send session started confirmation
        await websocket.send_text(json.dumps({
            "type": "session_started",
            "session_id": session_id,
            "language": language,
            "message": "Transcription session active"
        }))
        
        # Listen for audio chunks and transcription requests
        while True:
            try:
                # Set a timeout for receiving messages
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                message = json.loads(data)

                if message["type"] == "start_recording":
                    # Acknowledge recording start
                    await websocket.send_text(json.dumps({
                        "type": "recording_started",
                        "session_id": session_id,
                        "language": language
                    }))

                elif message["type"] == "audio_chunk":
                    # Process audio chunk for real transcription
                    audio_data = message.get("audio_data")
                    timestamp = message.get("timestamp", datetime.now().timestamp() * 1000)
                    speaker_info = message.get("speaker_info", {})
                    audio_format = message.get("audio_format", "audio/webm")
                    
                    # Acknowledge receipt first
                    await websocket.send_text(json.dumps({
                        "type": "chunk_received",
                        "timestamp": timestamp,
                        "session_id": session_id
                    }))

                    # Process audio for speech recognition
                    transcribed_text = ""
                    confidence_score = 0
                    
                    if audio_data:
                        try:
                            # Import speech service
                            from services.speech_services import SpeechService
                            
                            # Decode base64 audio data
                            audio_bytes = base64.b64decode(audio_data)
                            
                            # Create temporary file for audio processing
                            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                                if audio_format == "audio/pcm":
                                    # For PCM data, we need to create a proper WAV file
                                    with wave.open(temp_file.name, 'wb') as wav_file:
                                        wav_file.setnchannels(1)  # Mono
                                        wav_file.setsampwidth(2)  # 16-bit
                                        wav_file.setframerate(44100)  # Sample rate
                                        wav_file.writeframes(audio_bytes)
                                else:
                                    # For other formats, write directly
                                    temp_file.write(audio_bytes)
                                
                                temp_file.flush()
                                
                                # Perform speech recognition
                                speech_service = SpeechService()
                                
                                # Try Whisper first, then fallback to speech_recognition
                                try:
                                    result = speech_service.transcribe_with_whisper(temp_file.name, language)
                                    if result.get("success") and result.get("text", "").strip():
                                        transcribed_text = result["text"].strip()
                                        confidence_score = result.get("confidence", 95)
                                except Exception as e:
                                    logger.warning(f"Whisper transcription failed: {e}")
                                    
                                    # Fallback to speech_recognition
                                    try:
                                        result = speech_service.transcribe_with_speech_recognition(
                                            temp_file.name, language or "en-US"
                                        )
                                        if result.get("success") and result.get("text", "").strip():
                                            transcribed_text = result["text"].strip()
                                            confidence_score = result.get("confidence", 85)
                                    except Exception as e2:
                                        logger.warning(f"Speech recognition fallback failed: {e2}")
                                
                                # Clean up temp file
                                try:
                                    os.unlink(temp_file.name)
                                except:
                                    pass
                                    
                        except Exception as e:
                            logger.error(f"Audio processing error: {e}")

                    # If we got transcribed text, save it and send response
                    if transcribed_text.strip():
                        # Get participant info
                        participant = db.query(VideoCallParticipant).filter(
                            and_(
                                VideoCallParticipant.room_id == room.id,
                                VideoCallParticipant.user_id == user_id
                            )
                        ).first()
                        
                        if participant:
                            # Get user info for speaker name
                            user_info = get_user_info(db, user_id, username)
                            # Save to database
                            transcription = TranscriptionData(
                                session_id=session_id,
                                participant_id=participant.id,
                                user_id=user_id,
                                transcribed_text=transcribed_text,
                                original_language=language,
                                confidence_score=confidence_score,
                                start_time_seconds=None,
                                duration_seconds=None,
                                is_final=True,
                                speaker_name=user_info["username"],
                                word_count=len(transcribed_text.split()),
                                timestamp=datetime.utcnow()
                            )
                            db.add(transcription)
                            db.commit()
                            logger.info(f"Saved transcription: '{transcribed_text}' for session {session_id}, user {user_id}")

                        # Send transcription result back to frontend
                        await websocket.send_text(json.dumps({
                            "type": "transcription",
                            "text": transcribed_text,
                            "confidence": confidence_score,
                            "timestamp": timestamp,
                            "session_id": session_id,
                            "speaker_info": speaker_info
                        }))

                elif message["type"] == "stop_recording":
                    await websocket.send_text(json.dumps({
                        "type": "recording_stopped",
                        "session_id": session_id
                    }))
                    break

                else:
                    await websocket.send_text(json.dumps({
                        "type": "unknown_message",
                        "message": f"Unknown message type: {message.get('type')}"
                    }))

            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Error processing transcription message: {e}")
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "error": f"Error processing message: {str(e)}"
                }))

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"Error in transcription websocket: {e}")
    finally:
        db.close()
