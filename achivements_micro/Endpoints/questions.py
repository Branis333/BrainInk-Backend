from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from db.connection import db_dependency
from db.verify_token import user_dependency
from functions.question_service import QuestionService
from schemas.question_schemas import *
from models.question_bank import QuestionBank

router = APIRouter(prefix="/questions", tags=["Questions"])

@router.post("/create", response_model=QuestionResponse)
async def create_question(
    question_data: CreateQuestionRequest,
    db: db_dependency,
    current_user: user_dependency
):
    """Create a new question"""
    try:
        service = QuestionService(db)
        question = service.create_question(question_data)
        
        return QuestionResponse(
            id=question.id,
            question_text=question.question_text,
            option_a=question.option_a,
            option_b=question.option_b,
            option_c=question.option_c,
            option_d=question.option_d,
            correct_answer=question.correct_answer,
            subject=question.subject,
            topic=question.topic,
            difficulty_level=question.difficulty_level,
            explanation=question.explanation,
            source=question.source,
            points_value=question.points_value,
            time_limit_seconds=question.time_limit_seconds,
            times_used=question.times_used,
            correct_rate=question.correct_rate,
            is_active=question.is_active,
            created_at=question.created_at,
            updated_at=question.updated_at
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/", response_model=List[QuestionListResponse])
async def get_questions(
    db: db_dependency,
    subject: Optional[str] = None,
    topic: Optional[str] = None,
    difficulty_level: Optional[str] = None,
    is_active: Optional[bool] = True,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0)
):
    """Get questions with optional filters"""
    try:
        service = QuestionService(db)
        questions = service.get_questions(
            subject=subject,
            topic=topic,
            difficulty_level=difficulty_level,
            is_active=is_active,
            limit=limit,
            offset=offset
        )
        
        return [QuestionListResponse(
            id=q.id,
            question_text=q.question_text,
            subject=q.subject,
            topic=q.topic,
            difficulty_level=q.difficulty_level,
            points_value=q.points_value,
            times_used=q.times_used,
            correct_rate=q.correct_rate,
            is_active=q.is_active,
            created_at=q.created_at
        ) for q in questions]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{question_id}", response_model=QuestionResponse)
async def get_question(question_id: int, db: db_dependency):
    """Get a specific question by ID"""
    try:
        service = QuestionService(db)
        question = service.get_question_by_id(question_id)
        
        if not question:
            raise HTTPException(status_code=404, detail="Question not found")
        
        return QuestionResponse(
            id=question.id,
            question_text=question.question_text,
            option_a=question.option_a,
            option_b=question.option_b,
            option_c=question.option_c,
            option_d=question.option_d,
            correct_answer=question.correct_answer,
            subject=question.subject,
            topic=question.topic,
            difficulty_level=question.difficulty_level,
            explanation=question.explanation,
            source=question.source,
            points_value=question.points_value,
            time_limit_seconds=question.time_limit_seconds,
            times_used=question.times_used,
            correct_rate=question.correct_rate,
            is_active=question.is_active,
            created_at=question.created_at,
            updated_at=question.updated_at
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{question_id}", response_model=QuestionResponse)
async def update_question(
    question_id: int,
    update_data: UpdateQuestionRequest,
    db: db_dependency,
    current_user: user_dependency
):
    """Update a question"""
    try:
        service = QuestionService(db)
        question = service.update_question(question_id, update_data)
        
        if not question:
            raise HTTPException(status_code=404, detail="Question not found")
        
        return QuestionResponse(
            id=question.id,
            question_text=question.question_text,
            option_a=question.option_a,
            option_b=question.option_b,
            option_c=question.option_c,
            option_d=question.option_d,
            correct_answer=question.correct_answer,
            subject=question.subject,
            topic=question.topic,
            difficulty_level=question.difficulty_level,
            explanation=question.explanation,
            source=question.source,
            points_value=question.points_value,
            time_limit_seconds=question.time_limit_seconds,
            times_used=question.times_used,
            correct_rate=question.correct_rate,
            is_active=question.is_active,
            created_at=question.created_at,
            updated_at=question.updated_at
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{question_id}")
async def delete_question(
    question_id: int,
    db: db_dependency,
    current_user: user_dependency
):
    """Delete a question (soft delete - sets is_active to False)"""
    try:
        service = QuestionService(db)
        success = service.delete_question(question_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Question not found")
        
        return {"message": "Question deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/stats/overview", response_model=QuestionStatsResponse)
async def get_question_stats(db: db_dependency):
    """Get question bank statistics"""
    try:
        service = QuestionService(db)
        stats = service.get_question_stats()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/random/{count}")
async def get_random_questions(
    count: int,
    db: db_dependency,
    subject: Optional[str] = None,
    difficulty_level: Optional[str] = None,
    topics: Optional[str] = None  # Comma-separated topics
):
    """Get random questions for tournaments or practice"""
    try:
        service = QuestionService(db)
        
        # Parse topics if provided
        topic_list = None
        if topics:
            topic_list = [topic.strip() for topic in topics.split(",")]
        
        questions = service.get_random_questions(
            count=count,
            subject=subject,
            difficulty_level=difficulty_level,
            topics=topic_list
        )
        
        # Return questions without correct answers for practice mode
        return [
            {
                "id": q.id,
                "question_text": q.question_text,
                "option_a": q.option_a,
                "option_b": q.option_b,
                "option_c": q.option_c,
                "option_d": q.option_d,
                "subject": q.subject,
                "topic": q.topic,
                "difficulty_level": q.difficulty_level,
                "points_value": q.points_value,
                "time_limit_seconds": q.time_limit_seconds
            }
            for q in questions
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/subjects/list")
async def get_subjects(db: db_dependency):
    """Get list of all subjects"""
    try:
        service = QuestionService(db)
        subjects = service.get_unique_subjects()
        return {"subjects": subjects}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/topics/list")
async def get_topics(
    db: db_dependency,
    subject: Optional[str] = None
):
    """Get list of all topics, optionally filtered by subject"""
    try:
        service = QuestionService(db)
        topics = service.get_unique_topics(subject)
        return {"topics": topics}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))