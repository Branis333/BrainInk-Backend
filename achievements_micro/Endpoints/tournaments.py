from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from db.connection import db_dependency
from db.verify_token import user_dependency
from functions.tournament_functions import TournamentService
from schemas.tournament_schemas import *
from models.tournament_models import TournamentInvitation, TournamentParticipant, Tournament
from models.models import User

router = APIRouter(prefix="/tournaments", tags=["Tournaments"])

@router.post("/create", response_model=TournamentResponse)
async def create_tournament(
    tournament_data: CreateTournamentRequest,
    db: db_dependency,
    current_user: user_dependency
):
    """Create a new tournament"""
    try:
        service = TournamentService(db)
        tournament = service.create_tournament(current_user["user_id"], tournament_data)
        
        # Manually get creator info since tournament.creator is now manually added
        return TournamentResponse(
            id=tournament.id,
            name=tournament.name,
            description=tournament.description,
            creator=TournamentCreatorResponse(
                id=tournament.creator.id,
                username=tournament.creator.username
            ),
            max_players=tournament.max_players,
            current_players=tournament.current_players,
            tournament_type=tournament.tournament_type,
            bracket_type=tournament.bracket_type,
            status=tournament.status,
            has_prizes=tournament.has_prizes,
            first_place_prize=tournament.first_place_prize,
            second_place_prize=tournament.second_place_prize,
            third_place_prize=tournament.third_place_prize,
            prize_type=tournament.prize_type,
            total_questions=tournament.total_questions,
            time_limit_minutes=tournament.time_limit_minutes,
            difficulty_level=tournament.difficulty_level,
            subject_category=tournament.subject_category,
            registration_start=tournament.registration_start,
            registration_end=tournament.registration_end,
            tournament_start=tournament.tournament_start,
            tournament_end=tournament.tournament_end,
            created_at=tournament.created_at
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/", response_model=List[TournamentResponse])
async def get_tournaments(
    db: db_dependency,
    status: Optional[TournamentStatusEnum] = None,
    tournament_type: Optional[TournamentTypeEnum] = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """Get tournaments with optional filters"""
    try:
        service = TournamentService(db)
        tournaments = service.get_tournaments_with_creators(status, tournament_type, limit, offset)
        
        result = []
        for tournament in tournaments:
            tournament_response = TournamentResponse(
                id=tournament.id,
                name=tournament.name,
                description=tournament.description,
                creator=TournamentCreatorResponse(
                    id=tournament.creator.id,
                    username=tournament.creator.username
                ),
                max_players=tournament.max_players,
                current_players=tournament.current_players,
                tournament_type=tournament.tournament_type,
                bracket_type=tournament.bracket_type,
                status=tournament.status,
                has_prizes=tournament.has_prizes,
                first_place_prize=tournament.first_place_prize,
                second_place_prize=tournament.second_place_prize,
                third_place_prize=tournament.third_place_prize,
                prize_type=tournament.prize_type,
                total_questions=tournament.total_questions,
                time_limit_minutes=tournament.time_limit_minutes,
                difficulty_level=tournament.difficulty_level,
                subject_category=tournament.subject_category,
                registration_start=tournament.registration_start,
                registration_end=tournament.registration_end,
                tournament_start=tournament.tournament_start,
                tournament_end=tournament.tournament_end,
                created_at=tournament.created_at
            )
            result.append(tournament_response)
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{tournament_id}", response_model=TournamentDetailResponse)
async def get_tournament_details(
    tournament_id: int,
    db: db_dependency,
    current_user: user_dependency
):
    """Get detailed tournament information"""
    try:
        service = TournamentService(db)
        tournament = service.get_tournament_with_creator(tournament_id, current_user["user_id"])
        
        if not tournament:
            raise HTTPException(status_code=404, detail="Tournament not found")
        
        # Get participants manually
        participants = []
        tournament_participants = db.query(TournamentParticipant).filter(
            TournamentParticipant.tournament_id == tournament_id
        ).all()
        
        for participant in tournament_participants:
            # Manually get user info
            user = db.query(User).filter(User.id == participant.user_id).first()
            participants.append(TournamentParticipantResponse(
                id=participant.id,
                user_id=participant.user_id,
                username=user.username if user else "Unknown",
                seed_number=participant.seed_number,
                is_eliminated=participant.is_eliminated,
                final_position=participant.final_position,
                total_score=participant.total_score,
                joined_at=participant.joined_at
            ))
        
        return TournamentDetailResponse(
            id=tournament.id,
            name=tournament.name,
            description=tournament.description,
            creator=TournamentCreatorResponse(
                id=tournament.creator.id,
                username=tournament.creator.username
            ),
            max_players=tournament.max_players,
            current_players=tournament.current_players,
            tournament_type=tournament.tournament_type,
            bracket_type=tournament.bracket_type,
            status=tournament.status,
            has_prizes=tournament.has_prizes,
            first_place_prize=tournament.first_place_prize,
            second_place_prize=tournament.second_place_prize,
            third_place_prize=tournament.third_place_prize,
            prize_type=tournament.prize_type,
            total_questions=tournament.total_questions,
            time_limit_minutes=tournament.time_limit_minutes,
            difficulty_level=tournament.difficulty_level,
            subject_category=tournament.subject_category,
            registration_start=tournament.registration_start,
            registration_end=tournament.registration_end,
            tournament_start=tournament.tournament_start,
            tournament_end=tournament.tournament_end,
            created_at=tournament.created_at,
            participants=participants,
            can_join=getattr(tournament, 'can_join', False),
            is_participant=getattr(tournament, 'is_participant', False)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{tournament_id}/join")
async def join_tournament(
    tournament_id: int,
    db: db_dependency,
    current_user: user_dependency
):
    """Join a tournament"""
    try:
        service = TournamentService(db)
        success = service.join_tournament(tournament_id, current_user["user_id"])
        
        if success:
            return {"message": "Successfully joined tournament", "tournament_id": tournament_id}
        else:
            raise HTTPException(status_code=400, detail="Failed to join tournament")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{tournament_id}/start")
async def start_tournament(
    tournament_id: int,
    db: db_dependency,
    current_user: user_dependency
):
    """Start a tournament (creator only)"""
    try:
        service = TournamentService(db)
        tournament = service.get_tournament(tournament_id)
        
        if not tournament:
            raise HTTPException(status_code=404, detail="Tournament not found")
        
        if tournament.creator_id != current_user["user_id"]:
            raise HTTPException(status_code=403, detail="Only tournament creator can start tournament")
        
        success = service.start_tournament(tournament_id)
        
        if success:
            return {"message": "Tournament started successfully", "tournament_id": tournament_id}
        else:
            raise HTTPException(status_code=400, detail="Failed to start tournament")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{tournament_id}/bracket", response_model=TournamentBracketResponse)
async def get_tournament_bracket(
    tournament_id: int,
    db: db_dependency
):
    """Get tournament bracket"""
    try:
        service = TournamentService(db)
        bracket = service.get_tournament_bracket(tournament_id)
        
        if not bracket:
            raise HTTPException(status_code=404, detail="Tournament bracket not found")
        
        return bracket
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/user/my-tournaments")
async def get_my_tournaments(
    db: db_dependency,
    current_user: user_dependency
):
    """Get user's tournaments (created, participating, invited)"""
    try:
        service = TournamentService(db)
        tournaments = service.get_user_tournaments(current_user["user_id"])
        
        # Manually convert tournaments to response format
        def tournament_to_response(tournament):
            creator = db.query(User).filter(User.id == tournament.creator_id).first()
            return {
                "id": tournament.id,
                "name": tournament.name,
                "description": tournament.description,
                "creator": {
                    "id": creator.id,
                    "username": creator.username
                } if creator else None,
                "max_players": tournament.max_players,
                "current_players": tournament.current_players,
                "tournament_type": tournament.tournament_type,
                "bracket_type": tournament.bracket_type,
                "status": tournament.status,
                "has_prizes": tournament.has_prizes,
                "created_at": tournament.created_at.isoformat()
            }
        
        return {
            "created": [tournament_to_response(t) for t in tournaments["created"]],
            "participating": [tournament_to_response(t) for t in tournaments["participating"]],
            "invited": [tournament_to_response(t) for t in tournaments["invited"]]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{tournament_id}/invite")
async def invite_players(
    tournament_id: int,
    invite_request: InvitePlayersRequest,
    db: db_dependency,
    current_user: user_dependency
):
    """Invite players to tournament (creator only)"""
    try:
        service = TournamentService(db)
        tournament = service.get_tournament(tournament_id)
        
        if not tournament:
            raise HTTPException(status_code=404, detail="Tournament not found")
        
        if tournament.creator_id != current_user["user_id"]:
            raise HTTPException(status_code=403, detail="Only tournament creator can invite players")
        
        service._send_invitations(tournament_id, current_user["user_id"], invite_request.user_ids)
        db.commit()
        
        return {"message": f"Invitations sent to {len(invite_request.user_ids)} users"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/invitations/my-invitations", response_model=List[TournamentInvitationResponse])
async def get_my_invitations(
    db: db_dependency,
    current_user: user_dependency
):
    """Get user's tournament invitations"""
    try:
        invitations = db.query(TournamentInvitation).filter(
            TournamentInvitation.invitee_id == current_user["user_id"]
        ).all()
        
        result = []
        for invitation in invitations:
            # Manually get tournament and inviter info
            tournament = db.query(Tournament).filter(Tournament.id == invitation.tournament_id).first()
            inviter = db.query(User).filter(User.id == invitation.inviter_id).first()
            
            result.append(TournamentInvitationResponse(
                id=invitation.id,
                tournament_id=invitation.tournament_id,
                tournament_name=tournament.name if tournament else "Unknown Tournament",
                inviter_username=inviter.username if inviter else "Unknown User",
                status=invitation.status,
                invited_at=invitation.invited_at
            ))
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/invitations/{invitation_id}/respond")
async def respond_to_invitation(
    invitation_id: int,
    accept: bool,
    db: db_dependency,
    current_user: user_dependency
):
    """Respond to tournament invitation"""
    try:
        invitation = db.query(TournamentInvitation).filter(
            TournamentInvitation.id == invitation_id,
            TournamentInvitation.invitee_id == current_user["user_id"]
        ).first()
        
        if not invitation:
            raise HTTPException(status_code=404, detail="Invitation not found")
        
        if invitation.status != "pending":
            raise HTTPException(status_code=400, detail="Invitation already responded to")
        
        if accept:
            invitation.status = "accepted"
            invitation.responded_at = datetime.utcnow()
            
            # Join the tournament
            service = TournamentService(db)
            service.join_tournament(invitation.tournament_id, current_user["user_id"])
        else:
            invitation.status = "declined"
            invitation.responded_at = datetime.utcnow()
        
        db.commit()
        
        return {"message": f"Invitation {'accepted' if accept else 'declined'}"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))