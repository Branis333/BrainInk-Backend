from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
import math
import random
from models.tournament_models import *
from models.models import User  # Import your main User model
from schemas.tournament_schemas import *

class TournamentService:
    def __init__(self, db: Session):
        self.db = db
    
    def create_tournament(self, creator_id: int, tournament_data: CreateTournamentRequest) -> Tournament:
        """Create a new tournament"""
        try:
            # Validate max_players is a power of 2 for single elimination
            if tournament_data.bracket_type == BracketTypeEnum.SINGLE_ELIMINATION:
                if not self._is_power_of_2(tournament_data.max_players):
                    # Round up to next power of 2
                    tournament_data.max_players = self._next_power_of_2(tournament_data.max_players)
            
            tournament = Tournament(
                name=tournament_data.name,
                description=tournament_data.description,
                creator_id=creator_id,
                max_players=tournament_data.max_players,
                tournament_type=tournament_data.tournament_type.value,  # Convert enum to string
                bracket_type=tournament_data.bracket_type.value,  # Convert enum to string
                
                # Prize configuration
                has_prizes=tournament_data.prize_config.has_prizes,
                first_place_prize=tournament_data.prize_config.first_place_prize,
                second_place_prize=tournament_data.prize_config.second_place_prize,
                third_place_prize=tournament_data.prize_config.third_place_prize,
                prize_type=tournament_data.prize_config.prize_type,
                
                # Question configuration
                total_questions=tournament_data.question_config.total_questions,
                time_limit_minutes=tournament_data.question_config.time_limit_minutes,
                difficulty_level=tournament_data.question_config.difficulty_level.value,  # Convert enum to string
                subject_category=tournament_data.question_config.subject_category,
                custom_topics=','.join(tournament_data.question_config.custom_topics or []),
                
                # Timing
                registration_end=tournament_data.registration_end,
                tournament_start=tournament_data.tournament_start,
                status="draft"  # Use string instead of enum
            )
            
            self.db.add(tournament)
            self.db.commit()
            self.db.refresh(tournament)
            
            # Manually add creator info
            creator = self.db.query(User).filter(User.id == creator_id).first()
            tournament.creator = creator
            
            # Send invitations if specified
            if tournament_data.invited_users:
                # Convert string IDs to integers
                user_ids = [int(user_id) for user_id in tournament_data.invited_users]
                self._send_invitations(tournament.id, creator_id, user_ids)
            
            # Generate questions using AI (placeholder for now)
            self._generate_tournament_questions(tournament.id, tournament_data.question_config)
            
            return tournament
            
        except Exception as e:
            self.db.rollback()
            raise Exception(f"Failed to create tournament: {str(e)}")
    
    def get_tournament(self, tournament_id: int, user_id: Optional[int] = None) -> Optional[Tournament]:
        """Get tournament details"""
        tournament = self.db.query(Tournament).filter(Tournament.id == tournament_id).first()
        if not tournament:
            return None
        
        if user_id:
            # Check if user is participant
            tournament.is_participant = self._is_user_participant(tournament_id, user_id)
            tournament.can_join = self._can_user_join(tournament, user_id)
        
        return tournament
    
    def get_tournament_with_creator(self, tournament_id: int, user_id: Optional[int] = None) -> Optional[Tournament]:
        """Get tournament with creator information"""
        tournament = self.db.query(Tournament).filter(Tournament.id == tournament_id).first()
        if not tournament:
            return None
        
        # Manually query creator
        creator = self.db.query(User).filter(User.id == tournament.creator_id).first()
        tournament.creator = creator
        
        if user_id:
            tournament.is_participant = self._is_user_participant(tournament_id, user_id)
            tournament.can_join = self._can_user_join(tournament, user_id)
        
        return tournament
    
    def get_tournaments(self, 
                       status: Optional[TournamentStatusEnum] = None,
                       tournament_type: Optional[TournamentTypeEnum] = None,
                       limit: int = 50,
                       offset: int = 0) -> List[Tournament]:
        """Get tournaments with filters"""
        query = self.db.query(Tournament)
        
        if status:
            query = query.filter(Tournament.status == status.value)  # Convert enum to string
        if tournament_type:
            query = query.filter(Tournament.tournament_type == tournament_type.value)  # Convert enum to string
        
        return query.order_by(desc(Tournament.created_at)).offset(offset).limit(limit).all()
    
    def get_tournaments_with_creators(self, 
                                    status: Optional[TournamentStatusEnum] = None,
                                    tournament_type: Optional[TournamentTypeEnum] = None,
                                    limit: int = 50,
                                    offset: int = 0) -> List[Tournament]:
        """Get tournaments with creator information"""
        query = self.db.query(Tournament)
        
        if status:
            query = query.filter(Tournament.status == status.value)
        if tournament_type:
            query = query.filter(Tournament.tournament_type == tournament_type.value)
        
        tournaments = query.order_by(desc(Tournament.created_at)).offset(offset).limit(limit).all()
        
        # Manually add creator to each tournament
        for tournament in tournaments:
            creator = self.db.query(User).filter(User.id == tournament.creator_id).first()
            tournament.creator = creator
        
        return tournaments
    
    def join_tournament(self, tournament_id: int, user_id: int) -> bool:
        """Join a tournament"""
        try:
            tournament = self.get_tournament(tournament_id)
            if not tournament:
                raise ValueError("Tournament not found")
            
            if not self._can_user_join(tournament, user_id):
                raise ValueError("Cannot join this tournament")
            
            # Check if already participating
            existing = self.db.query(TournamentParticipant).filter(
                and_(
                    TournamentParticipant.tournament_id == tournament_id,
                    TournamentParticipant.user_id == user_id
                )
            ).first()
            
            if existing:
                raise ValueError("Already participating in this tournament")
            
            # Add participant
            participant = TournamentParticipant(
                tournament_id=tournament_id,
                user_id=user_id
            )
            self.db.add(participant)
            
            # Update tournament participant count
            tournament.current_players += 1
            
            # If tournament is full, change status to ready
            if tournament.current_players >= tournament.max_players:
                tournament.status = "open"  # Use string instead of enum
            
            self.db.commit()
            return True
            
        except Exception as e:
            self.db.rollback()
            raise Exception(f"Failed to join tournament: {str(e)}")
    
    def start_tournament(self, tournament_id: int) -> bool:
        """Start a tournament and generate brackets"""
        try:
            tournament = self.get_tournament(tournament_id)
            if not tournament:
                raise ValueError("Tournament not found")
            
            if tournament.status != "open":  # Use string instead of enum
                raise ValueError("Tournament is not ready to start")
            
            # Generate brackets
            self._generate_brackets(tournament_id)
            
            # Update tournament status
            tournament.status = "in_progress"  # Use string instead of enum
            tournament.tournament_start = datetime.utcnow()
            
            self.db.commit()
            return True
            
        except Exception as e:
            self.db.rollback()
            raise Exception(f"Failed to start tournament: {str(e)}")
    
    def get_tournament_bracket(self, tournament_id: int) -> Optional[TournamentBracketResponse]:
        """Get tournament bracket structure"""
        tournament = self.get_tournament(tournament_id)
        if not tournament:
            return None
        
        brackets = self.db.query(TournamentBracket).filter(
            TournamentBracket.tournament_id == tournament_id
        ).order_by(TournamentBracket.round_number).all()
        
        rounds = []
        for bracket in brackets:
            matches = self.db.query(TournamentMatch).filter(
                TournamentMatch.bracket_id == bracket.id
            ).order_by(TournamentMatch.match_number).all()
            
            match_responses = []
            for match in matches:
                player1 = self.db.query(User).filter(User.id == match.player1_id).first() if match.player1_id else None
                player2 = self.db.query(User).filter(User.id == match.player2_id).first() if match.player2_id else None
                winner = self.db.query(User).filter(User.id == match.winner_id).first() if match.winner_id else None
                
                match_response = MatchResponse(
                    id=match.id,
                    match_number=match.match_number,
                    round_number=match.round_number,
                    player1_id=match.player1_id,
                    player1_username=player1.username if player1 else None,
                    player2_id=match.player2_id,
                    player2_username=player2.username if player2 else None,
                    winner_id=match.winner_id,
                    winner_username=winner.username if winner else None,
                    player1_score=match.player1_score,
                    player2_score=match.player2_score,
                    player1_time=match.player1_time,
                    player2_time=match.player2_time,
                    is_completed=match.is_completed,
                    started_at=match.started_at,
                    completed_at=match.completed_at
                )
                match_responses.append(match_response)
            
            round_response = BracketRoundResponse(
                round_number=bracket.round_number,
                round_name=bracket.round_name,
                total_matches=bracket.total_matches,
                matches=match_responses
            )
            rounds.append(round_response)
        
        return TournamentBracketResponse(
            tournament_id=tournament_id,
            tournament_name=tournament.name,
            bracket_type=tournament.bracket_type,
            total_rounds=len(rounds),
            rounds=rounds
        )
    
    def get_user_tournaments(self, user_id: int) -> Dict[str, List[Tournament]]:
        """Get tournaments for a specific user"""
        # Created tournaments
        created = self.db.query(Tournament).filter(Tournament.creator_id == user_id).all()
        
        # Participating tournaments
        participant_tournaments = self.db.query(Tournament).join(TournamentParticipant).filter(
            TournamentParticipant.user_id == user_id
        ).all()
        
        # Invited tournaments
        invited_tournaments = self.db.query(Tournament).join(TournamentInvitation).filter(
            and_(
                TournamentInvitation.invitee_id == user_id,
                TournamentInvitation.status == "pending"
            )
        ).all()
        
        return {
            "created": created,
            "participating": participant_tournaments,
            "invited": invited_tournaments
        }
    
    # Helper methods
    def _is_power_of_2(self, n: int) -> bool:
        return n > 0 and (n & (n - 1)) == 0
    
    def _next_power_of_2(self, n: int) -> int:
        return 2 ** math.ceil(math.log2(n))
    
    def _can_user_join(self, tournament: Tournament, user_id: int) -> bool:
        if tournament.status not in ["draft", "open"]:  # Use strings instead of enums
            return False
        if tournament.current_players >= tournament.max_players:
            return False
        if tournament.tournament_type == "invite_only":  # Use string instead of enum
            # Check if user has invitation
            invitation = self.db.query(TournamentInvitation).filter(
                and_(
                    TournamentInvitation.tournament_id == tournament.id,
                    TournamentInvitation.invitee_id == user_id,
                    TournamentInvitation.status == "pending"
                )
            ).first()
            return invitation is not None
        return True
    
    def _is_user_participant(self, tournament_id: int, user_id: int) -> bool:
        participant = self.db.query(TournamentParticipant).filter(
            and_(
                TournamentParticipant.tournament_id == tournament_id,
                TournamentParticipant.user_id == user_id
            )
        ).first()
        return participant is not None
    
    def _send_invitations(self, tournament_id: int, inviter_id: int, user_ids: List[int]):
        """Send tournament invitations"""
        for user_id in user_ids:
            invitation = TournamentInvitation(
                tournament_id=tournament_id,
                inviter_id=inviter_id,
                invitee_id=user_id
            )
            self.db.add(invitation)
    
    def _generate_brackets(self, tournament_id: int):
        """Generate tournament brackets"""
        participants = self.db.query(TournamentParticipant).filter(
            TournamentParticipant.tournament_id == tournament_id
        ).all()
        
        # Assign seed numbers
        random.shuffle(participants)
        for i, participant in enumerate(participants):
            participant.seed_number = i + 1
        
        # Generate bracket structure for single elimination
        total_players = len(participants)
        total_rounds = math.ceil(math.log2(total_players))
        
        for round_num in range(1, total_rounds + 1):
            round_name = self._get_round_name(round_num, total_rounds)
            matches_in_round = total_players // (2 ** round_num)
            
            if matches_in_round < 1:
                matches_in_round = 1
            
            bracket = TournamentBracket(
                tournament_id=tournament_id,
                round_number=round_num,
                round_name=round_name,
                total_matches=matches_in_round
            )
            self.db.add(bracket)
            self.db.flush()
            
            # Generate matches for first round
            if round_num == 1:
                self._generate_first_round_matches(tournament_id, bracket.id, participants)
    
    def _get_round_name(self, round_num: int, total_rounds: int) -> str:
        """Get appropriate round name"""
        if round_num == total_rounds:
            return "Finals"
        elif round_num == total_rounds - 1:
            return "Semifinals"
        elif round_num == total_rounds - 2:
            return "Quarterfinals"
        else:
            return f"Round {round_num}"
    
    def _generate_first_round_matches(self, tournament_id: int, bracket_id: int, participants: List[TournamentParticipant]):
        """Generate first round matches"""
        for i in range(0, len(participants), 2):
            player1 = participants[i] if i < len(participants) else None
            player2 = participants[i + 1] if i + 1 < len(participants) else None
            
            match = TournamentMatch(
                tournament_id=tournament_id,
                bracket_id=bracket_id,
                match_number=i // 2 + 1,
                round_number=1,
                player1_id=player1.user_id if player1 else None,
                player2_id=player2.user_id if player2 else None
            )
            self.db.add(match)
    
    def _generate_tournament_questions(self, tournament_id: int, question_config: QuestionConfiguration):
        """Generate questions for tournament (placeholder - integrate with AI)"""
        # This would integrate with your AI service to generate questions
        # For now, we'll create placeholder questions
        categories = question_config.custom_topics or ["General Knowledge"]
        
        for i in range(question_config.total_questions):
            question = TournamentQuestion(
                tournament_id=tournament_id,
                question_text=f"Sample question {i + 1}",
                option_a="Option A",
                option_b="Option B", 
                option_c="Option C",
                option_d="Option D",
                correct_answer="A",
                category=random.choice(categories),
                difficulty=question_config.difficulty_level.value,  # Convert enum to string
                points_value=10,
                time_limit_seconds=30,
                generated_by_ai=True
            )
            self.db.add(question)