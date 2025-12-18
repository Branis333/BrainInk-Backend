from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError, DisconnectionError
from typing import List, Optional
from db.connection import db_dependency
from functions.squad_functions import SquadService
from schemas.squad_schemas import *
from datetime import datetime
import json  # Add this missing import

router = APIRouter(prefix="/squads", tags=["Squads"])

@router.post("/create", response_model=SquadResponse)
async def create_squad(
    request: CreateSquadSchema,
    db: db_dependency,
):
    """Create a new squad"""
    try:
        service = SquadService(db)
        success, message, squad = service.create_squad({
            "name": request.name,
            "emoji": request.emoji,
            "description": request.description,
            "creator_id": request.creator_id,
            "invitedFriends": request.invitedFriends,
            "subject_focus": request.subject_focus,
            "is_public": request.is_public
        })
        
        if success and squad:
            # Get full squad data with members
            members = service.get_squad_members(squad.id)
            
            return SquadResponse(
                id=squad.id,
                name=squad.name,
                emoji=squad.emoji,
                description=squad.description,
                creator_id=squad.creator_id,
                is_public=squad.is_public,
                max_members=squad.max_members,
                subject_focus=json.loads(squad.subject_focus) if squad.subject_focus else [],
                weekly_xp=squad.weekly_xp,
                total_xp=squad.total_xp,
                rank=squad.rank,
                members=[SquadMemberResponse(**member) for member in members],
                created_at=squad.created_at,
                updated_at=squad.updated_at
            )
        else:
            raise HTTPException(status_code=400, detail=message)
    
    except HTTPException:
        raise
    except (OperationalError, DisconnectionError) as e:
        print(f"Database connection error in create_squad: {e}")
        raise HTTPException(
            status_code=503, 
            detail="Database connection error. Please try again."
        )
    except Exception as e:
        print(f"Unexpected error in create_squad: {e}")
        raise HTTPException(
            status_code=500, 
            detail="An unexpected error occurred. Please try again."
        )

@router.get("/user/{user_id}/squads", response_model=List[SquadResponse])
async def get_user_squads(
    user_id: int,
    db: db_dependency,
):
    """Get all squads for a user"""
    try:
        service = SquadService(db)
        squads_data = service.get_user_squads(user_id)
        
        squads = []
        for squad_data in squads_data:
            squad = SquadResponse(
                id=squad_data["id"],
                name=squad_data["name"],
                emoji=squad_data["emoji"],
                description=squad_data.get("description"),
                creator_id=0,  # Not needed for list view
                is_public=True,  # Default for list view
                max_members=20,  # Default for list view
                subject_focus=[],  # Not needed for list view
                weekly_xp=squad_data["weekly_xp"],
                total_xp=squad_data["total_xp"],
                rank=squad_data["rank"],
                members=[SquadMemberResponse(**member) for member in squad_data["members"]],
                created_at=datetime.fromisoformat(squad_data["created_at"]) if squad_data["created_at"] else datetime.utcnow(),
                updated_at=datetime.fromisoformat(squad_data["last_activity"]) if squad_data["last_activity"] else datetime.utcnow(),
                unread_count=squad_data.get("unread_count", 0)
            )
            squads.append(squad)
        
        return squads
    
    except HTTPException:
        raise
    except (OperationalError, DisconnectionError) as e:
        print(f"Database connection error in get_user_squads: {e}")
        raise HTTPException(
            status_code=503, 
            detail="Database connection error. Please try again."
        )
    except Exception as e:
        print(f"Unexpected error in get_user_squads: {e}")
        raise HTTPException(
            status_code=500, 
            detail="An unexpected error occurred. Please try again."
        )

@router.post("/join/{squad_id}")
async def join_squad(
    squad_id: str,
    request: JoinSquadSchema,
    db: db_dependency,
):
    """Join a squad"""
    try:
        service = SquadService(db)
        success, message = service.join_squad(squad_id, request.user_id)
        
        if success:
            return {"success": True, "message": message}
        else:
            raise HTTPException(status_code=400, detail=message)
    
    except HTTPException:
        raise
    except (OperationalError, DisconnectionError) as e:
        print(f"Database connection error in join_squad: {e}")
        raise HTTPException(
            status_code=503, 
            detail="Database connection error. Please try again."
        )
    except Exception as e:
        print(f"Unexpected error in join_squad: {e}")
        raise HTTPException(
            status_code=500, 
            detail="An unexpected error occurred. Please try again."
        )

@router.post("/message/send")
async def send_squad_message(
    request: SendSquadMessageSchema,
    db: db_dependency,
):
    """Send a message to a squad"""
    try:
        service = SquadService(db)
        success, message, squad_message = service.send_squad_message({
            "squad_id": request.squad_id,
            "sender_id": request.sender_id,
            "content": request.content,
            "message_type": request.message_type,
            "metadata": request.metadata
        })
        
        if success and squad_message:
            return {
                "success": True,
                "message": message,
                "message_id": squad_message.id
            }
        else:
            raise HTTPException(status_code=400, detail=message)
    
    except HTTPException:
        raise
    except (OperationalError, DisconnectionError) as e:
        print(f"Database connection error in send_squad_message: {e}")
        raise HTTPException(
            status_code=503, 
            detail="Database connection error. Please try again."
        )
    except Exception as e:
        print(f"Unexpected error in send_squad_message: {e}")
        raise HTTPException(
            status_code=500, 
            detail="An unexpected error occurred. Please try again."
        )

@router.get("/messages/{squad_id}", response_model=PaginatedMessagesResponse)
async def get_squad_messages(
    squad_id: str,
    db: db_dependency,
    user_id: int = Query(...),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
):
    """Get messages from a squad"""
    try:
        service = SquadService(db)
        messages_data, total_count = service.get_squad_messages(squad_id, user_id, page, page_size)
        
        messages = [SquadMessageResponse(**msg) for msg in messages_data]
        
        return PaginatedMessagesResponse(
            messages=messages,
            total_count=total_count,
            page=page,
            page_size=page_size,
            has_next=total_count > page * page_size
        )
    
    except HTTPException:
        raise
    except (OperationalError, DisconnectionError) as e:
        print(f"Database connection error in get_squad_messages: {e}")
        raise HTTPException(
            status_code=503, 
            detail="Database connection error. Please try again."
        )
    except Exception as e:
        print(f"Unexpected error in get_squad_messages: {e}")
        raise HTTPException(
            status_code=500, 
            detail="An unexpected error occurred. Please try again."
        )

@router.post("/squad/{squad_id}/promote")
async def promote_member(
    squad_id: str,
    request: dict,
    db: db_dependency,
):
    """Promote a squad member"""
    try:
        service = SquadService(db)
        member_id = request.get("member_id")
        promoter_id = request.get("promoter_id")  # Should come from auth
        
        success, message = service.promote_member(squad_id, member_id, promoter_id)
        
        if success:
            return {"success": True, "message": message}
        else:
            raise HTTPException(status_code=400, detail=message)
    
    except HTTPException:
        raise
    except (OperationalError, DisconnectionError) as e:
        print(f"Database connection error in promote_member: {e}")
        raise HTTPException(
            status_code=503, 
            detail="Database connection error. Please try again."
        )
    except Exception as e:
        print(f"Unexpected error in promote_member: {e}")
        raise HTTPException(
            status_code=500, 
            detail="An unexpected error occurred. Please try again."
        )

@router.post("/squad/{squad_id}/remove")
async def remove_member(
    squad_id: str,
    request: dict,
    db: db_dependency,
):
    """Remove a squad member"""
    try:
        service = SquadService(db)
        member_id = request.get("member_id")
        remover_id = request.get("remover_id")  # Should come from auth
        
        success, message = service.remove_member(squad_id, member_id, remover_id)
        
        if success:
            return {"success": True, "message": message}
        else:
            raise HTTPException(status_code=400, detail=message)
    
    except HTTPException:
        raise
    except (OperationalError, DisconnectionError) as e:
        print(f"Database connection error in remove_member: {e}")
        raise HTTPException(
            status_code=503, 
            detail="Database connection error. Please try again."
        )
    except Exception as e:
        print(f"Unexpected error in remove_member: {e}")
        raise HTTPException(
            status_code=500, 
            detail="An unexpected error occurred. Please try again."
        )

@router.get("/study-leagues", response_model=List[StudyLeagueResponse])
async def get_study_leagues(
    db: db_dependency,
    status: str = Query("all", pattern="^(all|active|upcoming|ended)$"),
):
    """Get available study leagues"""
    try:
        service = SquadService(db)
        leagues_data = service.get_study_leagues(status)
        
        leagues = [StudyLeagueResponse(**league) for league in leagues_data]
        return leagues
    
    except HTTPException:
        raise
    except (OperationalError, DisconnectionError) as e:
        print(f"Database connection error in get_study_leagues: {e}")
        raise HTTPException(
            status_code=503, 
            detail="Database connection error. Please try again."
        )
    except Exception as e:
        print(f"Unexpected error in get_study_leagues: {e}")
        raise HTTPException(
            status_code=500, 
            detail="An unexpected error occurred. Please try again."
        )

@router.post("/study-leagues/create", response_model=StudyLeagueDetailResponse)
async def create_study_league(
    request: CreateLeagueSchema,
    db: db_dependency,
):
    """Create a new study league"""
    try:
        service = SquadService(db)
        success, message, league = service.create_study_league({
            "name": request.name,
            "description": request.description,
            "subject": request.subject,
            "max_participants": request.max_participants,
            "entry_fee": request.entry_fee,
            "prize_pool": request.prize_pool,
            "difficulty": request.difficulty,
            "league_type": request.league_type,
            "duration_days": request.duration_days,
            "creator_id": request.creator_id
        })
        
        if success and league:
            # Get detailed league info
            league_detail = service.get_study_league_detail(league.id, request.creator_id)
            
            return StudyLeagueDetailResponse(**league_detail)
        else:
            raise HTTPException(status_code=400, detail=message)
    
    except HTTPException:
        raise
    except (OperationalError, DisconnectionError) as e:
        print(f"Database connection error in create_study_league: {e}")
        raise HTTPException(
            status_code=503, 
            detail="Database connection error. Please try again."
        )
    except Exception as e:
        print(f"Unexpected error in create_study_league: {e}")
        raise HTTPException(
            status_code=500, 
            detail="An unexpected error occurred. Please try again."
        )

@router.get("/study-leagues/browse", response_model=PaginatedLeaguesResponse)
async def browse_study_leagues(
    db: db_dependency,
    status: str = Query("all", pattern="^(all|active|upcoming|ended)$"),  # Changed regex to pattern
    subject: Optional[str] = Query(None),
    difficulty: str = Query("all", pattern="^(all|beginner|intermediate|advanced)$"),  # Changed regex to pattern
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """Browse available study leagues with filters and pagination"""
    try:
        service = SquadService(db)
        leagues_data, total_count = service.get_study_leagues_paginated(
            status_filter=status,
            subject_filter=subject,
            difficulty_filter=difficulty if difficulty != "all" else None,
            page=page,
            page_size=page_size
        )
        
        leagues = [StudyLeagueResponse(**league) for league in leagues_data]
        
        return PaginatedLeaguesResponse(
            leagues=leagues,
            total_count=total_count,
            page=page,
            page_size=page_size,
            has_next=total_count > page * page_size
        )
    
    except HTTPException:
        raise
    except (OperationalError, DisconnectionError) as e:
        print(f"Database connection error in browse_study_leagues: {e}")
        raise HTTPException(
            status_code=503, 
            detail="Database connection error. Please try again."
        )
    except Exception as e:
        print(f"Unexpected error in browse_study_leagues: {e}")
        raise HTTPException(
            status_code=500, 
            detail="An unexpected error occurred. Please try again."
        )

@router.get("/study-leagues/{league_id}", response_model=StudyLeagueDetailResponse)
async def get_study_league_detail(
    league_id: str,
    db: db_dependency,
    user_id: Optional[int] = Query(None),
):
    """Get detailed information about a specific study league"""
    try:
        service = SquadService(db)
        league_detail = service.get_study_league_detail(league_id, user_id)
        
        if league_detail:
            return StudyLeagueDetailResponse(**league_detail)
        else:
            raise HTTPException(status_code=404, detail="Study league not found")
    
    except HTTPException:
        raise
    except (OperationalError, DisconnectionError) as e:
        print(f"Database connection error in get_study_league_detail: {e}")
        raise HTTPException(
            status_code=503, 
            detail="Database connection error. Please try again."
        )
    except Exception as e:
        print(f"Unexpected error in get_study_league_detail: {e}")
        raise HTTPException(
            status_code=500, 
            detail="An unexpected error occurred. Please try again."
        )

@router.put("/study-leagues/{league_id}")
async def update_study_league(
    league_id: str,
    request: UpdateLeagueSchema,
    db: db_dependency,
    user_id: int = Query(...),
):
    """Update a study league (only creator can update)"""
    try:
        service = SquadService(db)
        
        update_data = {k: v for k, v in request.dict().items() if v is not None}
        success, message = service.update_study_league(league_id, update_data, user_id)
        
        if success:
            return {"success": True, "message": message}
        else:
            raise HTTPException(status_code=400, detail=message)
    
    except HTTPException:
        raise
    except (OperationalError, DisconnectionError) as e:
        print(f"Database connection error in update_study_league: {e}")
        raise HTTPException(
            status_code=503, 
            detail="Database connection error. Please try again."
        )
    except Exception as e:
        print(f"Unexpected error in update_study_league: {e}")
        raise HTTPException(
            status_code=500, 
            detail="An unexpected error occurred. Please try again."
        )

@router.delete("/study-leagues/{league_id}")
async def delete_study_league(
    league_id: str,
    db: db_dependency,
    user_id: int = Query(...),
):
    """Delete a study league (only creator can delete)"""
    try:
        service = SquadService(db)
        success, message = service.delete_study_league(league_id, user_id)
        
        if success:
            return {"success": True, "message": message}
        else:
            raise HTTPException(status_code=400, detail=message)
    
    except HTTPException:
        raise
    except (OperationalError, DisconnectionError) as e:
        print(f"Database connection error in delete_study_league: {e}")
        raise HTTPException(
            status_code=503, 
            detail="Database connection error. Please try again."
        )
    except Exception as e:
        print(f"Unexpected error in delete_study_league: {e}")
        raise HTTPException(
            status_code=500, 
            detail="An unexpected error occurred. Please try again."
        )

@router.get("/study-leagues/{league_id}/leaderboard", response_model=LeagueLeaderboardResponse)
async def get_league_leaderboard(
    league_id: str,
    db: db_dependency,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    user_id: Optional[int] = Query(None),
):
    """Get study league leaderboard"""
    try:
        service = SquadService(db)
        
        # Get league info
        league_detail = service.get_study_league_detail(league_id, user_id)
        if not league_detail:
            raise HTTPException(status_code=404, detail="Study league not found")
        
        # Get leaderboard
        participants, total_count = service.get_league_leaderboard(league_id, page, page_size)
        
        return LeagueLeaderboardResponse(
            league_info=StudyLeagueDetailResponse(**league_detail),
            participants=[LeagueParticipantResponse(**participant) for participant in participants],
            total_participants=total_count,
            page=page,
            page_size=page_size,
            has_next=total_count > page * page_size
        )
    
    except HTTPException:
        raise
    except (OperationalError, DisconnectionError) as e:
        print(f"Database connection error in get_league_leaderboard: {e}")
        raise HTTPException(
            status_code=503, 
            detail="Database connection error. Please try again."
        )
    except Exception as e:
        print(f"Unexpected error in get_league_leaderboard: {e}")
        raise HTTPException(
            status_code=500, 
            detail="An unexpected error occurred. Please try again."
        )

@router.post("/study-leagues/{league_id}/stats")
async def update_participant_stats(
    league_id: str,
    request: LeagueStatsUpdateSchema,
    db: db_dependency,
):
    """Update participant statistics in a league"""
    try:
        service = SquadService(db)
        success, message = service.update_participant_stats(league_id, request.user_id, {
            "questions_answered": request.questions_answered,
            "correct_answers": request.correct_answers,
            "xp_earned": request.xp_earned
        })
        
        if success:
            return {"success": True, "message": message}
        else:
            raise HTTPException(status_code=400, detail=message)
    
    except HTTPException:
        raise
    except (OperationalError, DisconnectionError) as e:
        print(f"Database connection error in update_participant_stats: {e}")
        raise HTTPException(
            status_code=503, 
            detail="Database connection error. Please try again."
        )
    except Exception as e:
        print(f"Unexpected error in update_participant_stats: {e}")
        raise HTTPException(
            status_code=500, 
            detail="An unexpected error occurred. Please try again."
        )

@router.get("/user/{user_id}/study-leagues", response_model=List[StudyLeagueResponse])
async def get_user_study_leagues(
    user_id: int,
    db: db_dependency,
    status: str = Query("all", pattern="^(all|active|upcoming|ended)$"),  # Changed regex to pattern
):
    """Get study leagues that a user is participating in"""
    try:
        service = SquadService(db)
        leagues_data = service.get_user_leagues(user_id, status)
        
        leagues = [StudyLeagueResponse(**league) for league in leagues_data]
        return leagues
    
    except HTTPException:
        raise
    except (OperationalError, DisconnectionError) as e:
        print(f"Database connection error in get_user_study_leagues: {e}")
        raise HTTPException(
            status_code=503, 
            detail="Database connection error. Please try again."
        )
    except Exception as e:
        print(f"Unexpected error in get_user_study_leagues: {e}")
        raise HTTPException(
            status_code=500, 
            detail="An unexpected error occurred. Please try again."
        )

# Update the existing join league endpoint to be more consistent
@router.post("/study-leagues/{league_id}/join")
async def join_study_league(
    league_id: str,
    request: JoinLeagueSchema,
    db: db_dependency,
):
    """Join a study league"""
    try:
        service = SquadService(db)
        success, message = service.join_study_league(league_id, request.user_id)
        
        if success:
            return {"success": True, "message": message}
        else:
            raise HTTPException(status_code=400, detail=message)
    
    except HTTPException:
        raise
    except (OperationalError, DisconnectionError) as e:
        print(f"Database connection error in join_study_league: {e}")
        raise HTTPException(
            status_code=503, 
            detail="Database connection error. Please try again."
        )
    except Exception as e:
        print(f"Unexpected error in join_study_league: {e}")
        raise HTTPException(
            status_code=500, 
            detail="An unexpected error occurred. Please try again."
        )

@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "squads",
        "timestamp": datetime.utcnow().isoformat()
    }

@router.get("/health/detailed")
async def detailed_health_check(db: db_dependency):
    """Detailed health check with database connectivity test"""
    try:
        from sqlalchemy import text
        
        # Test database connection
        result = db.execute(text("SELECT 1 as test"))
        db_test = result.fetchone()
        
        # Test squad tables access
        squads_result = db.execute(text("SELECT COUNT(*) as squad_count FROM squads"))
        squad_count = squads_result.fetchone()
        
        return {
            "status": "healthy",
            "service": "squads",
            "database": "connected",
            "database_test": "passed",
            "squad_tables_accessible": True,
            "total_squads": squad_count[0] if squad_count else 0,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "service": "squads", 
            "database": "disconnected",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }

@router.get("/squad/{squad_id}", response_model=SquadResponse)
async def get_squad_detail(
    squad_id: str,
    db: db_dependency,
    user_id: Optional[int] = Query(None),
):
    """Get detailed information about a specific squad"""
    try:
        service = SquadService(db)
        squad_detail = service.get_squad_detail(squad_id, user_id)
        
        if squad_detail:
            return SquadResponse(**squad_detail)
        else:
            raise HTTPException(status_code=404, detail="Squad not found")
    
    except HTTPException:
        raise
    except (OperationalError, DisconnectionError) as e:
        print(f"Database connection error in get_squad_detail: {e}")
        raise HTTPException(
            status_code=503, 
            detail="Database connection error. Please try again."
        )
    except Exception as e:
        print(f"Unexpected error in get_squad_detail: {e}")
        raise HTTPException(
            status_code=500, 
            detail="An unexpected error occurred. Please try again."
        )

@router.put("/squad/{squad_id}", response_model=SquadResponse)
async def update_squad(
    squad_id: str,
    request: UpdateSquadSchema,
    db: db_dependency,
    user_id: int = Query(..., description="ID of the user making the request"),
):
    """Update a squad (only creator/leader can update)"""
    try:
        service = SquadService(db)
        
        # Filter out None values - use model_dump instead of dict()
        update_data = {k: v for k, v in request.model_dump().items() if v is not None}
        
        if not update_data:
            raise HTTPException(status_code=400, detail="No fields to update")
        
        success, message, squad = service.update_squad(squad_id, update_data, user_id)
        
        if success and squad:
            # Get updated squad detail with members
            squad_detail = service.get_squad_detail(squad_id, user_id)
            if squad_detail:
                return SquadResponse(**squad_detail)
            else:
                raise HTTPException(status_code=404, detail="Squad not found after update")
        else:
            raise HTTPException(status_code=400, detail=message)
    
    except HTTPException:
        raise
    except (OperationalError, DisconnectionError) as e:
        print(f"Database connection error in update_squad: {e}")
        raise HTTPException(
            status_code=503, 
            detail="Database connection error. Please try again."
        )
    except Exception as e:
        print(f"Unexpected error in update_squad: {e}")
        raise HTTPException(
            status_code=500, 
            detail="An unexpected error occurred. Please try again."
        )

@router.delete("/squad/{squad_id}")
async def delete_squad(
    squad_id: str,
    request: DeleteSquadSchema,
    db: db_dependency,
    user_id: int = Query(..., description="ID of the user making the request"),
):
    """Delete a squad (only creator can delete)"""
    try:
        service = SquadService(db)
        
        success, message = service.delete_squad(
            squad_id, 
            user_id, 
            request.confirm_deletion,
            request.transfer_leadership
        )
        
        if success:
            return {"success": True, "message": message}
        else:
            raise HTTPException(status_code=400, detail=message)
    
    except HTTPException:
        raise
    except (OperationalError, DisconnectionError) as e:
        print(f"Database connection error in delete_squad: {e}")
        raise HTTPException(
            status_code=503, 
            detail="Database connection error. Please try again."
        )
    except Exception as e:
        print(f"Unexpected error in delete_squad: {e}")
        raise HTTPException(
            status_code=500, 
            detail="An unexpected error occurred. Please try again."
        )

@router.post("/squad/{squad_id}/leave")
async def leave_squad(
    squad_id: str,
    db: db_dependency,
    user_id: int = Query(..., description="ID of the user leaving"),
):
    """Leave a squad"""
    try:
        service = SquadService(db)
        success, message = service.leave_squad(squad_id, user_id)
        
        if success:
            return {"success": True, "message": message}
        else:
            raise HTTPException(status_code=400, detail=message)
    
    except HTTPException:
        raise
    except (OperationalError, DisconnectionError) as e:
        print(f"Database connection error in leave_squad: {e}")
        raise HTTPException(
            status_code=503, 
            detail="Database connection error. Please try again."
        )
    except Exception as e:
        print(f"Unexpected error in leave_squad: {e}")
        raise HTTPException(
            status_code=500, 
            detail="An unexpected error occurred. Please try again."
        )

@router.post("/squad/{squad_id}/transfer-leadership")
async def transfer_squad_leadership(
    squad_id: str,
    request: dict,
    db: db_dependency,
    current_leader_id: int = Query(..., description="ID of the current leader"),
):
    """Transfer squad leadership to another member"""
    try:
        service = SquadService(db)
        new_leader_id = request.get("new_leader_id")
        
        if not new_leader_id:
            raise HTTPException(status_code=400, detail="new_leader_id is required")
        
        success, message = service.transfer_squad_leadership(squad_id, current_leader_id, new_leader_id)
        
        if success:
            return {"success": True, "message": message}
        else:
            raise HTTPException(status_code=400, detail=message)
    
    except HTTPException:
        raise
    except (OperationalError, DisconnectionError) as e:
        print(f"Database connection error in transfer_squad_leadership: {e}")
        raise HTTPException(
            status_code=503, 
            detail="Database connection error. Please try again."
        )
    except Exception as e:
        print(f"Unexpected error in transfer_squad_leadership: {e}")
        raise HTTPException(
            status_code=500, 
            detail="An unexpected error occurred. Please try again."
        )
