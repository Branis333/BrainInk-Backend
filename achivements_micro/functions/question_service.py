from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import List, Optional
import random
from datetime import datetime
from models.question_bank import QuestionBank
from schemas.question_schemas import CreateQuestionRequest, UpdateQuestionRequest, QuestionStatsResponse

class QuestionService:
    def __init__(self, db: Session):
        self.db = db
    
    def create_question(self, question_data: CreateQuestionRequest) -> QuestionBank:
        """Create a new question"""
        try:
            question = QuestionBank(
                question_text=question_data.question_text,
                option_a=question_data.option_a,
                option_b=question_data.option_b,
                option_c=question_data.option_c,
                option_d=question_data.option_d,
                correct_answer=question_data.correct_answer,
                subject=question_data.subject,
                topic=question_data.topic,
                difficulty_level=question_data.difficulty_level.value,
                explanation=question_data.explanation,
                source=question_data.source,
                points_value=question_data.points_value,
                time_limit_seconds=question_data.time_limit_seconds
            )
            
            self.db.add(question)
            self.db.commit()
            self.db.refresh(question)
            return question
            
        except Exception as e:
            self.db.rollback()
            raise Exception(f"Failed to create question: {str(e)}")
    
    def get_question_by_id(self, question_id: int) -> Optional[QuestionBank]:
        """Get a question by ID"""
        return self.db.query(QuestionBank).filter(QuestionBank.id == question_id).first()
    
    def get_questions(self,
                     subject: Optional[str] = None,
                     topic: Optional[str] = None,
                     difficulty_level: Optional[str] = None,
                     is_active: Optional[bool] = True,
                     limit: int = 50,
                     offset: int = 0) -> List[QuestionBank]:
        """Get questions with filters"""
        query = self.db.query(QuestionBank)
        
        if is_active is not None:
            query = query.filter(QuestionBank.is_active == is_active)
        if subject:
            query = query.filter(QuestionBank.subject.ilike(f"%{subject}%"))
        if topic:
            query = query.filter(QuestionBank.topic.ilike(f"%{topic}%"))
        if difficulty_level:
            query = query.filter(QuestionBank.difficulty_level == difficulty_level)
        
        return query.order_by(desc(QuestionBank.created_at)).offset(offset).limit(limit).all()
    
    def update_question(self, question_id: int, update_data: UpdateQuestionRequest) -> Optional[QuestionBank]:
        """Update a question"""
        try:
            question = self.get_question_by_id(question_id)
            if not question:
                return None
            
            # Update only provided fields
            for field, value in update_data.dict(exclude_unset=True).items():
                if field == "difficulty_level" and value:
                    setattr(question, field, value.value)
                else:
                    setattr(question, field, value)
            
            question.updated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(question)
            return question
            
        except Exception as e:
            self.db.rollback()
            raise Exception(f"Failed to update question: {str(e)}")
    
    def delete_question(self, question_id: int) -> bool:
        """Soft delete a question"""
        try:
            question = self.get_question_by_id(question_id)
            if not question:
                return False
            
            question.is_active = False
            question.updated_at = datetime.utcnow()
            self.db.commit()
            return True
            
        except Exception as e:
            self.db.rollback()
            raise Exception(f"Failed to delete question: {str(e)}")
    
    def get_random_questions(self, 
                           count: int = 30,
                           subject: Optional[str] = None,
                           difficulty_level: Optional[str] = None,
                           topics: Optional[List[str]] = None) -> List[QuestionBank]:
        """Get random questions from the question bank"""
        query = self.db.query(QuestionBank).filter(QuestionBank.is_active == True)
        
        # Apply filters
        if subject:
            query = query.filter(QuestionBank.subject.ilike(f"%{subject}%"))
        if difficulty_level:
            query = query.filter(QuestionBank.difficulty_level == difficulty_level)
        if topics:
            query = query.filter(QuestionBank.topic.in_(topics))
        
        # Get all matching questions
        all_questions = query.all()
        
        # Return random sample
        if len(all_questions) <= count:
            return all_questions
        else:
            return random.sample(all_questions, count)
    
    def get_questions_by_subject(self, subject: str) -> List[QuestionBank]:
        """Get all questions for a specific subject"""
        return self.db.query(QuestionBank).filter(
            QuestionBank.subject.ilike(f"%{subject}%"),
            QuestionBank.is_active == True
        ).all()
    
    def get_question_stats(self) -> QuestionStatsResponse:
        """Get statistics about the question bank"""
        total_questions = self.db.query(QuestionBank).count()
        active_questions = self.db.query(QuestionBank).filter(QuestionBank.is_active == True).count()
        
        # By subject
        subjects = self.db.query(
            QuestionBank.subject, 
            func.count(QuestionBank.id)
        ).filter(
            QuestionBank.is_active == True
        ).group_by(QuestionBank.subject).all()
        
        # By difficulty
        difficulties = self.db.query(
            QuestionBank.difficulty_level, 
            func.count(QuestionBank.id)
        ).filter(
            QuestionBank.is_active == True
        ).group_by(QuestionBank.difficulty_level).all()
        
        # By topic (top 20)
        topics = self.db.query(
            QuestionBank.topic, 
            func.count(QuestionBank.id)
        ).filter(
            QuestionBank.is_active == True
        ).group_by(QuestionBank.topic).order_by(
            desc(func.count(QuestionBank.id))
        ).limit(20).all()
        
        # Most used questions
        most_used = self.db.query(QuestionBank).filter(
            QuestionBank.is_active == True
        ).order_by(desc(QuestionBank.times_used)).limit(10).all()
        
        # Highest correct rate
        highest_correct = self.db.query(QuestionBank).filter(
            QuestionBank.is_active == True,
            QuestionBank.times_used >= 5  # Only questions used at least 5 times
        ).order_by(desc(QuestionBank.correct_rate)).limit(10).all()
        
        return QuestionStatsResponse(
            total_questions=total_questions,
            active_questions=active_questions,
            by_subject=dict(subjects),
            by_difficulty=dict(difficulties),
            by_topic=dict(topics),
            most_used_questions=[
                {
                    "id": q.id,
                    "question_text": q.question_text[:100] + "..." if len(q.question_text) > 100 else q.question_text,
                    "times_used": q.times_used,
                    "subject": q.subject,
                    "topic": q.topic
                } for q in most_used
            ],
            highest_correct_rate=[
                {
                    "id": q.id,
                    "question_text": q.question_text[:100] + "..." if len(q.question_text) > 100 else q.question_text,
                    "correct_rate": q.correct_rate,
                    "times_used": q.times_used,
                    "subject": q.subject,
                    "topic": q.topic
                } for q in highest_correct
            ]
        )
    
    def get_unique_subjects(self) -> List[str]:
        """Get list of unique subjects"""
        result = self.db.query(QuestionBank.subject).filter(
            QuestionBank.is_active == True
        ).distinct().all()
        return [row[0] for row in result]
    
    def get_unique_topics(self, subject: Optional[str] = None) -> List[str]:
        """Get list of unique topics, optionally filtered by subject"""
        query = self.db.query(QuestionBank.topic).filter(QuestionBank.is_active == True)
        
        if subject:
            query = query.filter(QuestionBank.subject.ilike(f"%{subject}%"))
        
        result = query.distinct().all()
        return [row[0] for row in result]
    
    def increment_question_usage(self, question_id: int, was_correct: bool):
        """Increment usage stats for a question"""
        try:
            question = self.get_question_by_id(question_id)
            if question:
                question.times_used += 1
                
                # Update correct rate
                if question.times_used == 1:
                    question.correct_rate = 100.0 if was_correct else 0.0
                else:
                    # Recalculate correct rate
                    total_correct = (question.correct_rate / 100.0) * (question.times_used - 1)
                    if was_correct:
                        total_correct += 1
                    question.correct_rate = (total_correct / question.times_used) * 100.0
                
                self.db.commit()
        except Exception as e:
            self.db.rollback()
            print(f"Error updating question usage: {e}")