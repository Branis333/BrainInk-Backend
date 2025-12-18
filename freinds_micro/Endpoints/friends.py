from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError, DisconnectionError
from typing import List, Optional
from db.connection import db_dependency
from functions.friends_functions import FriendsService
from schemas.friends_schemas import *
from models.friends_models import FriendshipStatus, MessageStatus
from sqlalchemy import text
from datetime import datetime

router = APIRouter(prefix="/friends", tags=["Friends"])

@router.post("/request/send/{user_id}", response_model=dict)
async def send_friend_request(
    user_id: int,
    request: SendFriendRequestSchema,
    db: db_dependency,
):
    """Send a friend request to another user"""
    try:
        service = FriendsService(db)
        success, message, friendship = service.send_friend_request(
            user_id, request.addressee_username, request.message
        )
        
        if success:
            return {"success": True, "message": message, "friendship_id": friendship.id}
        else:
            raise HTTPException(status_code=400, detail=message)
    
    except HTTPException:
        raise
    except (OperationalError, DisconnectionError) as e:
        print(f"Database connection error in send_friend_request: {e}")
        raise HTTPException(
            status_code=503, 
            detail="Database connection error. Please try again."
        )
    except Exception as e:
        print(f"Unexpected error in send_friend_request: {e}")
        raise HTTPException(
            status_code=500, 
            detail="An unexpected error occurred. Please try again."
        )

@router.post("/request/respond/{user_id}")
async def respond_to_friend_request(
    user_id: int,
    request: RespondToFriendRequestSchema,
    db: db_dependency,
):
    """Respond to a friend request (accept/decline/block)"""
    try:
        service = FriendsService(db)
        success, message = service.respond_to_friend_request(
            user_id, request.friendship_id, request.status
        )
        
        if success:
            return {"success": True, "message": message}
        else:
            raise HTTPException(status_code=400, detail=message)
    
    except HTTPException:
        raise
    except (OperationalError, DisconnectionError) as e:
        print(f"Database connection error in respond_to_friend_request: {e}")
        raise HTTPException(
            status_code=503, 
            detail="Database connection error. Please try again."
        )
    except Exception as e:
        print(f"Unexpected error in respond_to_friend_request: {e}")
        raise HTTPException(
            status_code=500, 
            detail="An unexpected error occurred. Please try again."
        )

@router.get("/list/{user_id}", response_model=FriendsListResponse)
async def get_friends_list(
    user_id: int,
    db: db_dependency,
):
    """Get user's friends list"""
    try:
        service = FriendsService(db)
        friends = service.get_friends_list(user_id)
        
        return FriendsListResponse(
            friends=[UserBasicInfo(**friend) for friend in friends],
            total_count=len(friends)
        )
    
    except HTTPException:
        raise
    except (OperationalError, DisconnectionError) as e:
        print(f"Database connection error in get_friends_list: {e}")
        raise HTTPException(
            status_code=503, 
            detail="Database connection error. Please try again."
        )
    except Exception as e:
        print(f"Unexpected error in get_friends_list: {e}")
        raise HTTPException(
            status_code=500, 
            detail="An unexpected error occurred. Please try again."
        )

@router.get("/requests/pending/{user_id}", response_model=List[FriendshipResponse])
async def get_pending_requests(
    user_id: int,
    db: db_dependency,
):
    """Get pending friend requests received"""
    try:
        service = FriendsService(db)
        requests = service.get_pending_requests(user_id)
        
        result = []
        for req in requests:
            requester_info = service.get_user_by_id(req.requester_id)
            friendship_response = FriendshipResponse(
                id=req.id,
                requester_id=req.requester_id,
                addressee_id=req.addressee_id,
                status=req.status,
                created_at=req.created_at,
                updated_at=req.updated_at,
                accepted_at=req.accepted_at,
                message=req.message,
                friend_info=UserBasicInfo(**requester_info) if requester_info else None
            )
            result.append(friendship_response)
        
        return result
    
    except HTTPException:
        raise
    except (OperationalError, DisconnectionError) as e:
        print(f"Database connection error in get_pending_requests: {e}")
        raise HTTPException(
            status_code=503, 
            detail="Database connection error. Please try again."
        )
    except Exception as e:
        print(f"Unexpected error in get_pending_requests: {e}")
        raise HTTPException(
            status_code=500, 
            detail="An unexpected error occurred. Please try again."
        )

@router.get("/requests/sent/{user_id}", response_model=List[FriendshipResponse])
async def get_sent_requests(
    user_id: int,
    db: db_dependency,
):
    """Get pending friend requests sent by user"""
    try:
        service = FriendsService(db)
        requests = service.get_sent_requests(user_id)
        
        result = []
        for req in requests:
            addressee_info = service.get_user_by_id(req.addressee_id)
            friendship_response = FriendshipResponse(
                id=req.id,
                requester_id=req.requester_id,
                addressee_id=req.addressee_id,
                status=req.status,
                created_at=req.created_at,
                updated_at=req.updated_at,
                accepted_at=req.accepted_at,
                message=req.message,
                friend_info=UserBasicInfo(**addressee_info) if addressee_info else None
            )
            result.append(friendship_response)
        
        return result
    
    except HTTPException:
        raise
    except (OperationalError, DisconnectionError) as e:
        print(f"Database connection error in get_sent_requests: {e}")
        raise HTTPException(
            status_code=503, 
            detail="Database connection error. Please try again."
        )
    except Exception as e:
        print(f"Unexpected error in get_sent_requests: {e}")
        raise HTTPException(
            status_code=500, 
            detail="An unexpected error occurred. Please try again."
        )

@router.post("/message/send/{user_id}")
async def send_message(
    user_id: int,
    request: SendMessageSchema,
    db: db_dependency,
):
    """Send a message to a friend"""
    try:
        service = FriendsService(db)
        success, message, friend_message = service.send_message(
            user_id, request.receiver_username, request.content, request.message_type
        )
        
        if success:
            return {"success": True, "message": message, "message_id": friend_message.id}
        else:
            raise HTTPException(status_code=400, detail=message)
    
    except HTTPException:
        raise
    except (OperationalError, DisconnectionError) as e:
        print(f"Database connection error in send_message: {e}")
        raise HTTPException(
            status_code=503, 
            detail="Database connection error. Please try again."
        )
    except Exception as e:
        print(f"Unexpected error in send_message: {e}")
        raise HTTPException(
            status_code=500, 
            detail="An unexpected error occurred. Please try again."
        )

@router.get("/conversation/{user_id}/{friend_username}", response_model=PaginatedMessagesResponse)
async def get_conversation(
    user_id: int,
    friend_username: str,
    db: db_dependency,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
):
    """Get conversation with a friend"""
    try:
        service = FriendsService(db)
        messages, total_count = service.get_conversation(user_id, friend_username, page, page_size)
        
        message_responses = []
        for msg in messages:
            sender_info = service.get_user_by_id(msg.sender_id)
            message_response = FriendMessageResponse(
                id=msg.id,
                sender_id=msg.sender_id,
                receiver_id=msg.receiver_id,
                content=msg.content,
                message_type=msg.message_type,
                status=msg.status,
                created_at=msg.created_at,
                read_at=msg.read_at,
                sender_info=UserBasicInfo(**sender_info) if sender_info else None
            )
            message_responses.append(message_response)
        
        return PaginatedMessagesResponse(
            messages=message_responses,
            total_count=total_count,
            page=page,
            page_size=page_size,
            has_next=total_count > page * page_size
        )
    
    except HTTPException:
        raise
    except (OperationalError, DisconnectionError) as e:
        print(f"Database connection error in get_conversation: {e}")
        raise HTTPException(
            status_code=503, 
            detail="Database connection error. Please try again."
        )
    except Exception as e:
        print(f"Unexpected error in get_conversation: {e}")
        raise HTTPException(
            status_code=500, 
            detail="An unexpected error occurred. Please try again."
        )

@router.post("/message/mark-read/{user_id}/{friend_username}")
async def mark_messages_as_read(
    user_id: int,
    friend_username: str,
    db: db_dependency,
):
    """Mark all messages from a friend as read"""
    try:
        service = FriendsService(db)
        success = service.mark_messages_as_read(user_id, friend_username)
        
        if success:
            return {"success": True, "message": "Messages marked as read"}
        else:
            raise HTTPException(status_code=400, detail="Failed to mark messages as read")
    
    except HTTPException:
        raise
    except (OperationalError, DisconnectionError) as e:
        print(f"Database connection error in mark_messages_as_read: {e}")
        raise HTTPException(
            status_code=503, 
            detail="Database connection error. Please try again."
        )
    except Exception as e:
        print(f"Unexpected error in mark_messages_as_read: {e}")
        raise HTTPException(
            status_code=500, 
            detail="An unexpected error occurred. Please try again."
        )

@router.post("/invite/create/{user_id}", response_model=FriendInviteResponse)
async def create_invite(
    user_id: int,
    request: CreateInviteSchema,
    db: db_dependency,
):
    """Create a friend invite code"""
    try:
        service = FriendsService(db)
        invite = service.create_invite(
            user_id, request.max_uses, request.expires_in_hours, request.message
        )
        
        return FriendInviteResponse(
            id=invite.id,
            invite_code=invite.invite_code,
            max_uses=invite.max_uses,
            current_uses=invite.current_uses,
            expires_at=invite.expires_at,
            is_active=invite.is_active,
            message=invite.message,
            created_at=invite.created_at
        )
    
    except HTTPException:
        raise
    except (OperationalError, DisconnectionError) as e:
        print(f"Database connection error in create_invite: {e}")
        raise HTTPException(
            status_code=503, 
            detail="Database connection error. Please try again."
        )
    except Exception as e:
        print(f"Unexpected error in create_invite: {e}")
        raise HTTPException(
            status_code=500, 
            detail="An unexpected error occurred. Please try again."
        )

@router.post("/invite/use/{user_id}/{invite_code}")
async def use_invite(
    user_id: int,
    invite_code: str,
    db: db_dependency,
):
    """Use an invite code to send friend request"""
    try:
        service = FriendsService(db)
        success, message = service.use_invite(user_id, invite_code)
        
        if success:
            return {"success": True, "message": message}
        else:
            raise HTTPException(status_code=400, detail=message)
    
    except HTTPException:
        raise
    except (OperationalError, DisconnectionError) as e:
        print(f"Database connection error in use_invite: {e}")
        raise HTTPException(
            status_code=503, 
            detail="Database connection error. Please try again."
        )
    except Exception as e:
        print(f"Unexpected error in use_invite: {e}")
        raise HTTPException(
            status_code=500, 
            detail="An unexpected error occurred. Please try again."
        )

# Utility endpoints
@router.get("/users/search")
async def search_users(
    db: db_dependency,
    username: str = Query(..., min_length=1),
):
    """Search for users by username"""
    try:
        result = db.execute(
            text("SELECT id, username, fname, lname, avatar FROM users WHERE username ILIKE :username AND is_active = true LIMIT 10"),
            {"username": f"%{username}%"}
        )
        users = result.fetchall()
        
        user_list = []
        for user in users:
            user_list.append({
                "id": user.id,
                "username": user.username,
                "fname": user.fname,
                "lname": user.lname,
                "avatar": user.avatar
            })
        
        return {"users": user_list, "total_count": len(user_list)}
    
    except Exception as e:
        print(f"Error searching users: {e}")
        raise HTTPException(status_code=500, detail="Failed to search users")

@router.get("/health/detailed")
async def detailed_health_check(db: db_dependency):
    """Detailed health check with database connectivity test"""
    try:
        # Test database connection
        result = db.execute(text("SELECT 1 as test"))
        db_test = result.fetchone()
        
        # Test users table access
        users_result = db.execute(text("SELECT COUNT(*) as user_count FROM users"))
        user_count = users_result.fetchone()
        
        return {
            "status": "healthy",
            "service": "friends",
            "database": "connected",
            "database_test": "passed",
            "users_table_accessible": True,
            "total_users": user_count[0] if user_count else 0,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "service": "friends", 
            "database": "disconnected",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }