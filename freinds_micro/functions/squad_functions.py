from sqlalchemy.orm import Session
from sqlalchemy import text, or_, and_, func, desc
from sqlalchemy.exc import OperationalError, DisconnectionError
from models.squad_models import Squad, SquadMembership, SquadMessage, SquadBattle, StudyLeague, LeagueParticipation
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
import secrets
import string
import time
import json
import uuid

class SquadService:
    def __init__(self, db: Session):
        self.db = db
    
    def _execute_with_retry(self, query, params=None, max_retries=3):
        """Execute database query with retry logic"""
        for attempt in range(max_retries):
            try:
                if params:
                    result = self.db.execute(query, params)
                else:
                    result = self.db.execute(query)
                return result
            except (OperationalError, DisconnectionError) as e:
                print(f"Database query attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    try:
                        self.db.rollback()
                    except:
                        pass
                    time.sleep(1)
                    continue
                else:
                    raise e
            except Exception as e:
                raise e
    
    def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user info by ID"""
        try:
            query = text("SELECT id, username, fname, lname, avatar FROM users WHERE id = :user_id AND is_active = true")
            result = self._execute_with_retry(query, {"user_id": user_id})
            row = result.fetchone()
            
            if row:
                return {
                    "id": row.id,
                    "username": row.username,
                    "fname": row.fname,
                    "lname": row.lname,
                    "avatar": row.avatar
                }
            return None
        except Exception as e:
            print(f"Error getting user by ID '{user_id}': {e}")
            return None

    def create_squad(self, squad_data: Dict[str, Any]) -> Tuple[bool, str, Optional[Squad]]:
        """Create a new squad"""
        try:
            # Generate unique squad ID
            squad_id = str(uuid.uuid4())[:8].upper()
            
            # Create squad
            squad = Squad(
                id=squad_id,
                name=squad_data["name"],
                emoji=squad_data.get("emoji", "🦄"),
                description=squad_data.get("description"),
                creator_id=squad_data["creator_id"],
                is_public=squad_data.get("is_public", True),
                subject_focus=json.dumps(squad_data.get("subject_focus", [])) if squad_data.get("subject_focus") else None
            )
            
            self.db.add(squad)
            self.db.flush()  # Get the squad ID
            
            # Add creator as leader
            creator_membership = SquadMembership(
                squad_id=squad.id,
                user_id=squad_data["creator_id"],
                role="leader"
            )
            self.db.add(creator_membership)
            
            # Invite friends
            invited_friends = squad_data.get("invitedFriends", [])
            for friend_id in invited_friends:
                if friend_id != squad_data["creator_id"]:  # Don't re-add creator
                    member = SquadMembership(
                        squad_id=squad.id,
                        user_id=friend_id,
                        role="member"
                    )
                    self.db.add(member)
            
            self.db.commit()
            self.db.refresh(squad)
            
            return True, "Squad created successfully", squad
            
        except Exception as e:
            self.db.rollback()
            print(f"Error creating squad: {e}")
            return False, f"Failed to create squad: {str(e)}", None

    def get_user_squads(self, user_id: int) -> List[Dict[str, Any]]:
        """Get all squads a user is a member of"""
        try:
            # Get squads with member count and user's role
            query = text("""
                SELECT s.*, sm.role, sm.weekly_xp as member_weekly_xp, sm.total_xp as member_total_xp,
                       (SELECT COUNT(*) FROM squad_memberships WHERE squad_id = s.id) as member_count
                FROM squads s
                JOIN squad_memberships sm ON s.id = sm.squad_id
                WHERE sm.user_id = :user_id
                ORDER BY s.updated_at DESC
            """)
            
            result = self._execute_with_retry(query, {"user_id": user_id})
            rows = result.fetchall()
            
            squads = []
            for row in rows:
                # Get squad members with user info
                members = self.get_squad_members(row.id)
                
                squad_data = {
                    "id": row.id,
                    "name": row.name,
                    "emoji": row.emoji,
                    "description": row.description,
                    "weekly_xp": row.weekly_xp,
                    "total_xp": row.total_xp,
                    "rank": row.rank,
                    "members": members,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                    "unread_count": 0,  # TODO: Implement unread message count
                    "last_activity": row.updated_at.isoformat() if row.updated_at else None
                }
                squads.append(squad_data)
            
            return squads
            
        except Exception as e:
            print(f"Error getting user squads: {e}")
            return []

    def get_squad_members(self, squad_id: str) -> List[Dict[str, Any]]:
        """Get all members of a squad with their info"""
        try:
            query = text("""
                SELECT sm.*, u.username, u.fname, u.lname, u.avatar
                FROM squad_memberships sm
                JOIN users u ON sm.user_id = u.id
                WHERE sm.squad_id = :squad_id AND u.is_active = true
                ORDER BY sm.role DESC, sm.joined_at ASC
            """)
            
            result = self._execute_with_retry(query, {"squad_id": squad_id})
            rows = result.fetchall()
            
            members = []
            for row in rows:
                member = {
                    "id": row.user_id,
                    "username": row.username,
                    "fname": row.fname,
                    "lname": row.lname,
                    "avatar": row.avatar,
                    "role": row.role,
                    "weekly_xp": row.weekly_xp,
                    "total_xp": row.total_xp,
                    "joined_at": row.joined_at.isoformat() if row.joined_at else None,
                    "last_active": row.last_active.isoformat() if row.last_active else None,
                    "is_online": False  # TODO: Implement online status
                }
                members.append(member)
            
            return members
            
        except Exception as e:
            print(f"Error getting squad members: {e}")
            return []

    def join_squad(self, squad_id: str, user_id: int) -> Tuple[bool, str]:
        """Join a squad"""
        try:
            # Check if squad exists and is public
            squad = self.db.query(Squad).filter(Squad.id == squad_id).first()
            if not squad:
                return False, "Squad not found"
            
            if not squad.is_public:
                return False, "Squad is private"
            
            # Check if user is already a member
            existing = self.db.query(SquadMembership).filter(
                SquadMembership.squad_id == squad_id,
                SquadMembership.user_id == user_id
            ).first()
            
            if existing:
                return False, "Already a member of this squad"
            
            # Check member limit
            member_count = self.db.query(SquadMembership).filter(
                SquadMembership.squad_id == squad_id
            ).count()
            
            if member_count >= squad.max_members:
                return False, "Squad is full"
            
            # Add membership
            membership = SquadMembership(
                squad_id=squad_id,
                user_id=user_id,
                role="member"
            )
            
            self.db.add(membership)
            self.db.commit()
            
            return True, "Successfully joined squad"
            
        except Exception as e:
            self.db.rollback()
            print(f"Error joining squad: {e}")
            return False, f"Failed to join squad: {str(e)}"

    def send_squad_message(self, message_data: Dict[str, Any]) -> Tuple[bool, str, Optional[SquadMessage]]:
        """Send a message to a squad"""
        try:
            # Verify user is a squad member
            membership = self.db.query(SquadMembership).filter(
                SquadMembership.squad_id == message_data["squad_id"],
                SquadMembership.user_id == message_data["sender_id"]
            ).first()
            
            if not membership:
                return False, "Not a member of this squad", None
            
            # Create message
            message_id = str(uuid.uuid4())
            message = SquadMessage(
                id=message_id,
                squad_id=message_data["squad_id"],
                sender_id=message_data["sender_id"],
                content=message_data["content"],
                message_type=message_data.get("message_type", "text"),
                message_metadata=json.dumps(message_data.get("metadata", {})) if message_data.get("metadata") else None  # Changed from metadata to message_metadata
            )
            
            self.db.add(message)
            
            # Update squad last activity
            self.db.query(Squad).filter(Squad.id == message_data["squad_id"]).update({
                "updated_at": datetime.utcnow()
            })
            
            self.db.commit()
            self.db.refresh(message)
            
            return True, "Message sent successfully", message
            
        except Exception as e:
            self.db.rollback()
            print(f"Error sending squad message: {e}")
            return False, f"Failed to send message: {str(e)}", None

    def get_squad_messages(self, squad_id: str, user_id: int, page: int = 1, page_size: int = 50) -> Tuple[List[Dict[str, Any]], int]:
        """Get messages from a squad"""
        try:
            # Verify user is a squad member
            membership = self.db.query(SquadMembership).filter(
                SquadMembership.squad_id == squad_id,
                SquadMembership.user_id == user_id
            ).first()
            
            if not membership:
                return [], 0
            
            # Get total count
            total_count = self.db.query(SquadMessage).filter(
                SquadMessage.squad_id == squad_id
            ).count()
            
            # Get messages with pagination
            offset = (page - 1) * page_size
            messages = self.db.query(SquadMessage).filter(
                SquadMessage.squad_id == squad_id
            ).order_by(SquadMessage.created_at.desc()).offset(offset).limit(page_size).all()
            
            # Enrich messages with sender info
            message_responses = []
            for msg in messages:
                sender_info = self.get_user_by_id(msg.sender_id)
                message_data = {
                    "id": msg.id,
                    "squad_id": msg.squad_id,
                    "sender_id": msg.sender_id,
                    "sender_name": f"{sender_info.get('fname', '')} {sender_info.get('lname', '')}" if sender_info else "Unknown",
                    "sender_avatar": sender_info.get('avatar') if sender_info else None,
                    "content": msg.content,
                    "message_type": msg.message_type,
                    "metadata": json.loads(msg.message_metadata) if msg.message_metadata else {},  # Changed from metadata to message_metadata
                    "created_at": msg.created_at.isoformat(),
                    "reactions": []  # TODO: Implement reactions
                }
                message_responses.append(message_data)
            
            return message_responses, total_count
            
        except Exception as e:
            print(f"Error getting squad messages: {e}")
            return [], 0

    def promote_member(self, squad_id: str, member_id: int, promoter_id: int) -> Tuple[bool, str]:
        """Promote a squad member"""
        try:
            # Check if promoter is a leader
            promoter_membership = self.db.query(SquadMembership).filter(
                SquadMembership.squad_id == squad_id,
                SquadMembership.user_id == promoter_id,
                SquadMembership.role == "leader"
            ).first()
            
            if not promoter_membership:
                return False, "Only squad leaders can promote members"
            
            # Update member role
            self.db.query(SquadMembership).filter(
                SquadMembership.squad_id == squad_id,
                SquadMembership.user_id == member_id
            ).update({"role": "moderator"})
            
            self.db.commit()
            return True, "Member promoted successfully"
            
        except Exception as e:
            self.db.rollback()
            print(f"Error promoting member: {e}")
            return False, f"Failed to promote member: {str(e)}"

    def remove_member(self, squad_id: str, member_id: int, remover_id: int) -> Tuple[bool, str]:
        """Remove a member from squad"""
        try:
            # Check if remover has permission
            remover_membership = self.db.query(SquadMembership).filter(
                SquadMembership.squad_id == squad_id,
                SquadMembership.user_id == remover_id
            ).first()
            
            if not remover_membership or remover_membership.role not in ["leader", "moderator"]:
                return False, "Insufficient permissions"
            
            # Cannot remove squad leader
            member_membership = self.db.query(SquadMembership).filter(
                SquadMembership.squad_id == squad_id,
                SquadMembership.user_id == member_id
            ).first()
            
            if member_membership and member_membership.role == "leader":
                return False, "Cannot remove squad leader"
            
            # Remove member
            self.db.query(SquadMembership).filter(
                SquadMembership.squad_id == squad_id,
                SquadMembership.user_id == member_id
            ).delete()
            
            self.db.commit()
            return True, "Member removed successfully"
            
        except Exception as e:
            self.db.rollback()
            print(f"Error removing member: {e}")
            return False, f"Failed to remove member: {str(e)}"

    def get_study_leagues(self, status_filter: str = "all") -> List[Dict[str, Any]]:
        """Get available study leagues"""
        try:
            query = self.db.query(StudyLeague)
            
            if status_filter != "all":
                query = query.filter(StudyLeague.status == status_filter)
            
            leagues = query.order_by(StudyLeague.created_at.desc()).all()
            
            league_responses = []
            for league in leagues:
                # Get participant count
                participant_count = self.db.query(LeagueParticipation).filter(
                    LeagueParticipation.league_id == league.id
                ).count()
                
                league_data = {
                    "id": league.id,
                    "name": league.name,
                    "description": league.description,
                    "subject": league.subject,
                    "participants": participant_count,
                    "max_participants": league.max_participants,
                    "entry_fee": league.entry_fee,
                    "prize_pool": league.prize_pool,
                    "difficulty": league.difficulty,
                    "league_type": league.league_type,
                    "status": league.status,
                    "start_date": league.start_date.isoformat(),
                    "end_date": league.end_date.isoformat(),
                    "created_at": league.created_at.isoformat()
                }
                league_responses.append(league_data)
            
            return league_responses
            
        except Exception as e:
            print(f"Error getting study leagues: {e}")
            return []

    def join_study_league(self, league_id: str, user_id: int) -> Tuple[bool, str]:
        """Join a study league"""
        try:
            # Check if league exists and is joinable
            league = self.db.query(StudyLeague).filter(StudyLeague.id == league_id).first()
            if not league:
                return False, "League not found"
            
            if league.status != "upcoming":
                return False, "League is not open for registration"
            
            # Check if already joined
            existing = self.db.query(LeagueParticipation).filter(
                LeagueParticipation.league_id == league_id,
                LeagueParticipation.user_id == user_id
            ).first()
            
            if existing:
                return False, "Already joined this league"
            
            # Check participant limit
            participant_count = self.db.query(LeagueParticipation).filter(
                LeagueParticipation.league_id == league_id
            ).count()
            
            if participant_count >= league.max_participants:
                return False, "League is full"
            
            # Add participation
            participation = LeagueParticipation(
                league_id=league_id,
                user_id=user_id
            )
            
            self.db.add(participation)
            self.db.commit()
            
            return True, "Successfully joined league"
            
        except Exception as e:
            self.db.rollback()
            print(f"Error joining league: {e}")
            return False, f"Failed to join league: {str(e)}"

    def get_squad_battles(self, user_id: int) -> List[Dict[str, Any]]:
        """Get squad battles for user's squads"""
        try:
            # Get user's squad IDs
            user_squads = self.db.query(SquadMembership.squad_id).filter(
                SquadMembership.user_id == user_id
            ).all()
            squad_ids = [s.squad_id for s in user_squads]
            
            if not squad_ids:
                return []
            
            # Get battles
            battles = self.db.query(SquadBattle).filter(
                or_(
                    SquadBattle.challenger_squad_id.in_(squad_ids),
                    SquadBattle.challenged_squad_id.in_(squad_ids)
                )
            ).order_by(SquadBattle.created_at.desc()).all()
            
            battle_responses = []
            for battle in battles:
                # Get squad info
                challenger_squad = self.db.query(Squad).filter(Squad.id == battle.challenger_squad_id).first()
                challenged_squad = self.db.query(Squad).filter(Squad.id == battle.challenged_squad_id).first()
                
                battle_data = {
                    "id": battle.id,
                    "challenger_squad_id": battle.challenger_squad_id,
                    "challenged_squad_id": battle.challenged_squad_id,
                    "battle_type": battle.battle_type,
                    "status": battle.status,
                    "entry_fee": battle.entry_fee,
                    "prize_pool": battle.prize_pool,
                    "duration_minutes": battle.duration_minutes,
                    "subject": battle.subject,
                    "challenger_score": battle.challenger_score,
                    "challenged_score": battle.challenged_score,
                    "winner_squad_id": battle.winner_squad_id,
                    "created_at": battle.created_at.isoformat(),
                    "start_time": battle.start_time.isoformat() if battle.start_time else None,
                    "end_time": battle.end_time.isoformat() if battle.end_time else None,
                    "challenger_squad": {
                        "id": challenger_squad.id,
                        "name": challenger_squad.name,
                        "emoji": challenger_squad.emoji
                    } if challenger_squad else None,
                    "challenged_squad": {
                        "id": challenged_squad.id,
                        "name": challenged_squad.name,
                        "emoji": challenged_squad.emoji
                    } if challenged_squad else None
                }
                battle_responses.append(battle_data)
            
            return battle_responses
            
        except Exception as e:
            print(f"Error getting squad battles: {e}")
            return []

    def challenge_squad(self, challenge_data: Dict[str, Any]) -> Tuple[bool, str, Optional[SquadBattle]]:
        """Create a squad battle challenge"""
        try:
            # Verify challenger squad exists
            challenger_squad = self.db.query(Squad).filter(
                Squad.id == challenge_data["challenger_squad_id"]
            ).first()
            
            challenged_squad = self.db.query(Squad).filter(
                Squad.id == challenge_data["challenged_squad_id"]
            ).first()
            
            if not challenger_squad or not challenged_squad:
                return False, "One or both squads not found", None
            
            # Create battle
            battle_id = str(uuid.uuid4())
            battle = SquadBattle(
                id=battle_id,
                challenger_squad_id=challenge_data["challenger_squad_id"],
                challenged_squad_id=challenge_data["challenged_squad_id"],
                battle_type=challenge_data.get("battle_type", "quiz_battle"),
                entry_fee=challenge_data.get("entry_fee", 0),
                duration_minutes=challenge_data.get("duration_minutes", 30),
                subject=challenge_data.get("subject")
            )
            
            self.db.add(battle)
            self.db.commit()
            self.db.refresh(battle)
            
            return True, "Squad challenge created successfully", battle
            
        except Exception as e:
            self.db.rollback()
            print(f"Error creating squad challenge: {e}")
            return False, f"Failed to create challenge: {str(e)}", None

    def create_study_league(self, league_data: Dict[str, Any]) -> Tuple[bool, str, Optional[StudyLeague]]:
        """Create a new study league"""
        try:
            # Generate unique league ID
            league_id = str(uuid.uuid4())[:8].upper() + "_LEAGUE"
            
            # Calculate start and end dates
            start_date = datetime.utcnow()
            end_date = start_date + timedelta(days=league_data.get("duration_days", 7))
            
            # Create league
            league = StudyLeague(
                id=league_id,
                name=league_data["name"],
                description=league_data.get("description"),
                subject=league_data["subject"],
                max_participants=league_data.get("max_participants", 1000),
                entry_fee=league_data.get("entry_fee", 0),
                prize_pool=league_data.get("prize_pool", 0),
                difficulty=league_data.get("difficulty", "intermediate"),
                league_type=league_data.get("league_type", "weekly"),
                start_date=start_date,
                end_date=end_date
            )
            
            self.db.add(league)
            self.db.flush()  # Get the league ID
            
            # Auto-join the creator
            creator_participation = LeagueParticipation(
                league_id=league.id,
                user_id=league_data["creator_id"]
            )
            self.db.add(creator_participation)
            
            self.db.commit()
            self.db.refresh(league)
            
            return True, "Study league created successfully", league
            
        except Exception as e:
            self.db.rollback()
            print(f"Error creating study league: {e}")
            return False, f"Failed to create study league: {str(e)}", None

    def get_study_league_detail(self, league_id: str, user_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """Get detailed information about a study league"""
        try:
            league = self.db.query(StudyLeague).filter(StudyLeague.id == league_id).first()
            if not league:
                return None
            
            # Get participant count
            participant_count = self.db.query(LeagueParticipation).filter(
                LeagueParticipation.league_id == league_id
            ).count()
            
            # Get user's participation if user_id provided
            my_participation = None
            if user_id:
                participation = self.db.query(LeagueParticipation).filter(
                    LeagueParticipation.league_id == league_id,
                    LeagueParticipation.user_id == user_id
                ).first()
                
                if participation:
                    my_participation = {
                        "score": participation.score,
                        "rank": participation.rank,
                        "questions_answered": participation.questions_answered,
                        "accuracy": participation.accuracy,
                        "xp_earned": participation.xp_earned,
                        "joined_at": participation.joined_at.isoformat()
                    }
            
            # Get top 10 participants
            top_participants = self.get_league_leaderboard(league_id, 1, 10)[0]
            
            league_data = {
                "id": league.id,
                "name": league.name,
                "description": league.description,
                "subject": league.subject,
                "participants": participant_count,
                "max_participants": league.max_participants,
                "entry_fee": league.entry_fee,
                "prize_pool": league.prize_pool,
                "difficulty": league.difficulty,
                "league_type": league.league_type,
                "status": league.status,
                "start_date": league.start_date.isoformat(),
                "end_date": league.end_date.isoformat(),
                "created_at": league.created_at.isoformat(),
                "creator_id": 0,  # You might want to add creator_id to the model
                "my_participation": my_participation,
                "top_participants": top_participants
            }
            
            return league_data
            
        except Exception as e:
            print(f"Error getting study league detail: {e}")
            return None

    def update_study_league(self, league_id: str, update_data: Dict[str, Any], user_id: int) -> Tuple[bool, str]:
        """Update a study league (only creator can update)"""
        try:
            league = self.db.query(StudyLeague).filter(StudyLeague.id == league_id).first()
            if not league:
                return False, "League not found"
            
            # TODO: Add creator_id check when you add creator_id to the model
            # if league.creator_id != user_id:
            #     return False, "Only the league creator can update this league"
            
            if league.status != "upcoming":
                return False, "Can only update upcoming leagues"
            
            # Update fields
            for field, value in update_data.items():
                if hasattr(league, field) and value is not None:
                    setattr(league, field, value)
            
            self.db.commit()
            return True, "League updated successfully"
            
        except Exception as e:
            self.db.rollback()
            print(f"Error updating study league: {e}")
            return False, f"Failed to update league: {str(e)}"

    def delete_study_league(self, league_id: str, user_id: int) -> Tuple[bool, str]:
        """Delete a study league (only creator can delete if no participants)"""
        try:
            league = self.db.query(StudyLeague).filter(StudyLeague.id == league_id).first()
            if not league:
                return False, "League not found"
            
            # TODO: Add creator_id check when you add creator_id to the model
            # if league.creator_id != user_id:
            #     return False, "Only the league creator can delete this league"
            
            if league.status != "upcoming":
                return False, "Can only delete upcoming leagues"
            
            # Check if there are participants (other than creator)
            participant_count = self.db.query(LeagueParticipation).filter(
                LeagueParticipation.league_id == league_id
            ).count()
            
            if participant_count > 1:  # More than just the creator
                return False, "Cannot delete league with participants"
            
            # Delete participations first
            self.db.query(LeagueParticipation).filter(
                LeagueParticipation.league_id == league_id
            ).delete()
            
            # Delete league
            self.db.delete(league)
            self.db.commit()
            
            return True, "League deleted successfully"
            
        except Exception as e:
            self.db.rollback()
            print(f"Error deleting study league: {e}")
            return False, f"Failed to delete league: {str(e)}"

    def get_study_leagues_paginated(self, status_filter: str = "all", subject_filter: str = None, 
                                  difficulty_filter: str = None, page: int = 1, page_size: int = 20) -> Tuple[List[Dict[str, Any]], int]:
        """Get paginated list of study leagues with filters"""
        try:
            query = self.db.query(StudyLeague)
            
            # Apply filters
            if status_filter != "all":
                query = query.filter(StudyLeague.status == status_filter)
            
            if subject_filter:
                query = query.filter(StudyLeague.subject.ilike(f"%{subject_filter}%"))
            
            if difficulty_filter and difficulty_filter != "all":
                query = query.filter(StudyLeague.difficulty == difficulty_filter)
            
            # Get total count
            total_count = query.count()
            
            # Apply pagination
            offset = (page - 1) * page_size
            leagues = query.order_by(StudyLeague.created_at.desc()).offset(offset).limit(page_size).all()
            
            league_responses = []
            for league in leagues:
                # Get participant count
                participant_count = self.db.query(LeagueParticipation).filter(
                    LeagueParticipation.league_id == league.id
                ).count()
                
                league_data = {
                    "id": league.id,
                    "name": league.name,
                    "description": league.description,
                    "subject": league.subject,
                    "participants": participant_count,
                    "max_participants": league.max_participants,
                    "entry_fee": league.entry_fee,
                    "prize_pool": league.prize_pool,
                    "difficulty": league.difficulty,
                    "league_type": league.league_type,
                    "status": league.status,
                    "start_date": league.start_date.isoformat(),
                    "end_date": league.end_date.isoformat(),
                    "created_at": league.created_at.isoformat()
                }
                league_responses.append(league_data)
            
            return league_responses, total_count
            
        except Exception as e:
            print(f"Error getting paginated study leagues: {e}")
            return [], 0

    def get_league_leaderboard(self, league_id: str, page: int = 1, page_size: int = 50) -> Tuple[List[Dict[str, Any]], int]:
        """Get league leaderboard with participant rankings"""
        try:
            # Get total count
            total_count = self.db.query(LeagueParticipation).filter(
                LeagueParticipation.league_id == league_id
            ).count()
            
            # Get participants with ranking
            offset = (page - 1) * page_size
            query = text("""
                SELECT lp.*, u.username, u.fname, u.lname, u.avatar,
                       ROW_NUMBER() OVER (ORDER BY lp.score DESC, lp.accuracy DESC, lp.questions_answered DESC) as rank
                FROM league_participations lp
                JOIN users u ON lp.user_id = u.id
                WHERE lp.league_id = :league_id AND u.is_active = true
                ORDER BY lp.score DESC, lp.accuracy DESC, lp.questions_answered DESC
                LIMIT :limit OFFSET :offset
            """)
            
            result = self._execute_with_retry(query, {
                "league_id": league_id,
                "limit": page_size,
                "offset": offset
            })
            rows = result.fetchall()
            
            participants = []
            for row in rows:
                participant = {
                    "id": row.user_id,
                    "username": row.username,
                    "fname": row.fname,
                    "lname": row.lname,
                    "avatar": row.avatar,
                    "score": row.score,
                    "rank": row.rank,
                    "questions_answered": row.questions_answered,
                    "accuracy": row.accuracy,
                    "xp_earned": row.xp_earned
                }
                participants.append(participant)
            
            return participants, total_count
            
        except Exception as e:
            print(f"Error getting league leaderboard: {e}")
            return [], 0

    def update_participant_stats(self, league_id: str, user_id: int, stats_data: Dict[str, Any]) -> Tuple[bool, str]:
        """Update participant statistics in a league"""
        try:
            participation = self.db.query(LeagueParticipation).filter(
                LeagueParticipation.league_id == league_id,
                LeagueParticipation.user_id == user_id
            ).first()
            
            if not participation:
                return False, "User is not participating in this league"
            
            # Update stats
            participation.questions_answered += stats_data.get("questions_answered", 0)
            correct_answers = stats_data.get("correct_answers", 0)
            participation.xp_earned += stats_data.get("xp_earned", 0)
            
            # Calculate new accuracy
            if participation.questions_answered > 0:
                total_correct = int(participation.accuracy * (participation.questions_answered - stats_data.get("questions_answered", 0))) + correct_answers
                participation.accuracy = total_correct / participation.questions_answered
            
            # Update score (you can customize this scoring logic)
            participation.score = participation.xp_earned + (participation.accuracy * 100)
            
            # Update last activity
            participation.last_activity = datetime.utcnow()
            
            self.db.commit()
            return True, "Participant stats updated successfully"
            
        except Exception as e:
            self.db.rollback()
            print(f"Error updating participant stats: {e}")
            return False, f"Failed to update stats: {str(e)}"

    def get_user_leagues(self, user_id: int, status_filter: str = "all") -> List[Dict[str, Any]]:
        """Get leagues that a user is participating in"""
        try:
            query = text("""
                SELECT sl.*, lp.score, lp.rank, lp.questions_answered, lp.accuracy, lp.xp_earned, lp.joined_at,
                       (SELECT COUNT(*) FROM league_participations WHERE league_id = sl.id) as total_participants
                FROM study_leagues sl
                JOIN league_participations lp ON sl.id = lp.league_id
                WHERE lp.user_id = :user_id
            """)
            
            if status_filter != "all":
                query = text(str(query) + " AND sl.status = :status_filter")
                params = {"user_id": user_id, "status_filter": status_filter}
            else:
                params = {"user_id": user_id}
            
            query = text(str(query) + " ORDER BY sl.created_at DESC")
            
            result = self._execute_with_retry(query, params)
            rows = result.fetchall()
            
            leagues = []
            for row in rows:
                league_data = {
                    "id": row.id,
                    "name": row.name,
                    "description": row.description,
                    "subject": row.subject,
                    "participants": row.total_participants,
                    "max_participants": row.max_participants,
                    "entry_fee": row.entry_fee,
                    "prize_pool": row.prize_pool,
                    "difficulty": row.difficulty,
                    "league_type": row.league_type,
                    "status": row.status,
                    "start_date": row.start_date.isoformat(),
                    "end_date": row.end_date.isoformat(),
                    "created_at": row.created_at.isoformat(),
                    "my_rank": row.rank,
                    "my_score": row.score,
                    "my_stats": {
                        "questions_answered": row.questions_answered,
                        "accuracy": row.accuracy,
                        "xp_earned": row.xp_earned,
                        "joined_at": row.joined_at.isoformat()
                    }
                }
                leagues.append(league_data)
            
            return leagues
            
        except Exception as e:
            print(f"Error getting user leagues: {e}")
            return []

    def update_squad(self, squad_id: str, update_data: Dict[str, Any], user_id: int) -> Tuple[bool, str, Optional[Squad]]:
        """Update a squad (only creator/leader can update)"""
        try:
            # Get squad and verify ownership
            squad = self.db.query(Squad).filter(Squad.id == squad_id).first()
            if not squad:
                return False, "Squad not found", None
            
            # Check if user is the creator or a leader
            membership = self.db.query(SquadMembership).filter(
                SquadMembership.squad_id == squad_id,
                SquadMembership.user_id == user_id,
                SquadMembership.role == "leader"
            ).first()
            
            if not membership and squad.creator_id != user_id:
                return False, "Only squad leaders can update this squad", None
            
            # Update fields
            updated_fields = []
            for field, value in update_data.items():
                if value is not None and hasattr(squad, field):
                    old_value = getattr(squad, field)
                    
                    # Special handling for subject_focus
                    if field == "subject_focus" and isinstance(value, list):
                        setattr(squad, field, json.dumps(value))
                        updated_fields.append(f"{field}: {old_value} -> {json.dumps(value)}")
                    else:
                        setattr(squad, field, value)
                        updated_fields.append(f"{field}: {old_value} -> {value}")
            
            # Update timestamp
            squad.updated_at = datetime.utcnow()
            
            self.db.commit()
            self.db.refresh(squad)
            
            # Log the update (you could also create a squad activity/audit log)
            print(f"Squad {squad_id} updated by user {user_id}. Changes: {', '.join(updated_fields)}")
            
            return True, "Squad updated successfully", squad
            
        except Exception as e:
            self.db.rollback()
            print(f"Error updating squad: {e}")
            return False, f"Failed to update squad: {str(e)}", None

    def delete_squad(self, squad_id: str, user_id: int, confirm_deletion: bool = False, transfer_leadership: Optional[int] = None) -> Tuple[bool, str]:
        """Delete a squad (only creator can delete)"""
        try:
            # Get squad and verify ownership
            squad = self.db.query(Squad).filter(Squad.id == squad_id).first()
            if not squad:
                return False, "Squad not found"
            
            # Only creator can delete the squad
            if squad.creator_id != user_id:
                return False, "Only the squad creator can delete this squad"
            
            # Require confirmation
            if not confirm_deletion:
                return False, "Deletion must be confirmed"
            
            # Get squad members
            members = self.db.query(SquadMembership).filter(
                SquadMembership.squad_id == squad_id
            ).all()
            
            member_count = len(members)
            
            # If there are other members and no leadership transfer specified
            if member_count > 1 and transfer_leadership is None:
                return False, f"Squad has {member_count} members. Please transfer leadership or remove all members first"
            
            # If transferring leadership
            if transfer_leadership is not None and member_count > 1:
                # Verify the new leader is a member
                new_leader_membership = self.db.query(SquadMembership).filter(
                    SquadMembership.squad_id == squad_id,
                    SquadMembership.user_id == transfer_leadership
                ).first()
                
                if not new_leader_membership:
                    return False, "Transfer target is not a member of this squad"
                
                if transfer_leadership == user_id:
                    return False, "Cannot transfer leadership to yourself before deletion"
                
                # Transfer leadership
                squad.creator_id = transfer_leadership
                new_leader_membership.role = "leader"
                
                # Remove the original creator from the squad
                self.db.query(SquadMembership).filter(
                    SquadMembership.squad_id == squad_id,
                    SquadMembership.user_id == user_id
                ).delete()
                
                self.db.commit()
                return True, f"Leadership transferred to user {transfer_leadership}. You have left the squad."
            
            # If no transfer needed or only creator in squad, delete everything
            else:
                # Delete all squad messages
                self.db.query(SquadMessage).filter(
                    SquadMessage.squad_id == squad_id
                ).delete()
                
                # Delete all squad memberships
                self.db.query(SquadMembership).filter(
                    SquadMembership.squad_id == squad_id
                ).delete()
                
                # Delete squad battles
                self.db.query(SquadBattle).filter(
                    or_(
                        SquadBattle.challenger_squad_id == squad_id,
                        SquadBattle.challenged_squad_id == squad_id
                    )
                ).delete()
                
                # Delete the squad
                self.db.delete(squad)
                
                self.db.commit()
                
                print(f"Squad {squad_id} deleted by creator {user_id}")
                return True, "Squad deleted successfully"
            
        except Exception as e:
            self.db.rollback()
            print(f"Error deleting squad: {e}")
            return False, f"Failed to delete squad: {str(e)}"

    def leave_squad(self, squad_id: str, user_id: int) -> Tuple[bool, str]:
        """Leave a squad (with special handling for creators)"""
        try:
            # Get squad and user membership
            squad = self.db.query(Squad).filter(Squad.id == squad_id).first()
            if not squad:
                return False, "Squad not found"
            
            membership = self.db.query(SquadMembership).filter(
                SquadMembership.squad_id == squad_id,
                SquadMembership.user_id == user_id
            ).first()
            
            if not membership:
                return False, "You are not a member of this squad"
            
            # Check if user is the creator
            if squad.creator_id == user_id:
                # Get other members
                other_members = self.db.query(SquadMembership).filter(
                    SquadMembership.squad_id == squad_id,
                    SquadMembership.user_id != user_id
                ).all()
                
                if other_members:
                    return False, "As squad creator, you must transfer leadership or delete the squad before leaving"
                else:
                    # Creator is the only member, delete the squad
                    self.db.delete(membership)
                    self.db.delete(squad)
                    self.db.commit()
                    return True, "You were the last member. Squad has been deleted."
            
            # Regular member leaving
            self.db.delete(membership)
            self.db.commit()
            
            return True, "Successfully left the squad"
            
        except Exception as e:
            self.db.rollback()
            print(f"Error leaving squad: {e}")
            return False, f"Failed to leave squad: {str(e)}"

    def transfer_squad_leadership(self, squad_id: str, current_leader_id: int, new_leader_id: int) -> Tuple[bool, str]:
        """Transfer squad leadership to another member"""
        try:
            # Get squad and verify current leader
            squad = self.db.query(Squad).filter(Squad.id == squad_id).first()
            if not squad:
                return False, "Squad not found"
            
            if squad.creator_id != current_leader_id:
                return False, "Only the current squad leader can transfer leadership"
            
            if current_leader_id == new_leader_id:
                return False, "Cannot transfer leadership to yourself"
            
            # Verify new leader is a member
            new_leader_membership = self.db.query(SquadMembership).filter(
                SquadMembership.squad_id == squad_id,
                SquadMembership.user_id == new_leader_id
            ).first()
            
            if not new_leader_membership:
                return False, "New leader must be a squad member"
            
            # Update current leader to member
            current_leader_membership = self.db.query(SquadMembership).filter(
                SquadMembership.squad_id == squad_id,
                SquadMembership.user_id == current_leader_id
            ).first()
            
            if current_leader_membership:
                current_leader_membership.role = "member"
            
            # Transfer leadership
            squad.creator_id = new_leader_id
            new_leader_membership.role = "leader"
            
            self.db.commit()
            
            return True, f"Leadership transferred successfully to user {new_leader_id}"
            
        except Exception as e:
            self.db.rollback()
            print(f"Error transferring leadership: {e}")
            return False, f"Failed to transfer leadership: {str(e)}"

    def get_squad_detail(self, squad_id: str, user_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """Get detailed squad information"""
        try:
            squad = self.db.query(Squad).filter(Squad.id == squad_id).first()
            if not squad:
                return None
            
            # Get members with their info
            members = self.get_squad_members(squad_id)
            
            # Check if user is a member
            is_member = False
            user_role = None
            if user_id:
                membership = self.db.query(SquadMembership).filter(
                    SquadMembership.squad_id == squad_id,
                    SquadMembership.user_id == user_id
                ).first()
                if membership:
                    is_member = True
                    user_role = membership.role
            
            squad_data = {
                "id": squad.id,
                "name": squad.name,
                "emoji": squad.emoji,
                "description": squad.description,
                "creator_id": squad.creator_id,
                "is_public": squad.is_public,
                "max_members": squad.max_members,
                "subject_focus": json.loads(squad.subject_focus) if squad.subject_focus else [],
                "weekly_xp": squad.weekly_xp,
                "total_xp": squad.total_xp,
                "rank": squad.rank,
                "members": members,
                "created_at": squad.created_at.isoformat(),
                "updated_at": squad.updated_at.isoformat(),
                "is_member": is_member,
                "user_role": user_role,
                "can_edit": user_id == squad.creator_id or (user_role == "leader" if user_role else False),
                "can_delete": user_id == squad.creator_id
            }
            
            return squad_data
            
        except Exception as e:
            print(f"Error getting squad detail: {e}")
            return None