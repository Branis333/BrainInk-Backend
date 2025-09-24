from fastapi import APIRouter, HTTPException, Depends, status, Query, File, UploadFile, Form, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, desc, func
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import os
import tempfile
import mimetypes
from pathlib import Path
import uuid
import json

from db.connection import db_dependency
from Endpoints.auth import get_current_user
from models.reading_assistant_models import (
    ReadingContent, ReadingSession, ReadingAttempt, 
    WordFeedback, ReadingFeedback, ReadingProgress, ReadingGoal,
    ReadingLevel, DifficultyLevel
)
from schemas.reading_assistant_schemas import (
    ReadingContentCreate, ReadingContentOut, ReadingContentUpdate,
    ReadingSessionStart, ReadingSessionOut, ReadingAttemptStart, ReadingAttemptOut,
    AudioUploadRequest, AudioAnalysisResponse, LiveAudioSession,
    FeedbackCreate, FeedbackOut, ProgressUpdate, ReadingProgressOut,
    GoalCreate, GoalOut, StudentReadingDashboard, TeacherReadingDashboard,
    GenerateContentRequest, MessageResponse, ReadingListResponse, SessionListResponse
)
from services.reading_assistant_service import reading_assistant_service
from services.gemini_service import gemini_service
from services.tts_service import tts_service

router = APIRouter(prefix="/after-school/reading-assistant", tags=["Reading Assistant"])

# Dependency for current user
user_dependency = Depends(get_current_user)

# ===============================
# CONTENT MANAGEMENT ENDPOINTS
# ===============================

@router.post("/content", response_model=ReadingContentOut)
async def create_reading_content(
    content_data: ReadingContentCreate,
    db: db_dependency,
    current_user: dict = user_dependency
):
    """Create new reading content manually"""
    
    try:
        # Calculate word count and estimated reading time
        word_count = len(content_data.content.split())
        estimated_time = word_count * 2  # 2 seconds per word for beginners
        
        new_content = ReadingContent(
            title=content_data.title,
            content=content_data.content,
            content_type=content_data.content_type,
            reading_level=content_data.reading_level,
            difficulty_level=content_data.difficulty_level,
            vocabulary_words=content_data.vocabulary_words or {},
            learning_objectives=content_data.learning_objectives or [],
            phonics_focus=content_data.phonics_focus or [],
            word_count=word_count,
            estimated_reading_time=estimated_time,
            created_by=current_user["user_id"]
        )
        
        db.add(new_content)
        db.commit()
        db.refresh(new_content)
        
        return new_content
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating reading content: {str(e)}"
        )

@router.post("/content/generate", response_model=ReadingContentOut)
async def generate_reading_content(
    request: GenerateContentRequest,
    db: db_dependency,
    current_user: dict = user_dependency
):
    """Generate reading content using AI"""
    
    try:
        # Generate content using AI service
        generated_content = await reading_assistant_service.generate_reading_content(
            reading_level=request.reading_level,
            difficulty_level=request.difficulty_level,
            content_type=request.content_type,
            topic=request.topic,
            vocabulary_focus=request.vocabulary_focus,
            phonics_patterns=request.phonics_patterns,
            word_count_target=request.word_count_target
        )
        
        # Create content record in database
        complexity_analysis = generated_content.get("complexity_analysis", {})
        
        new_content = ReadingContent(
            title=generated_content["title"],
            content=generated_content["content"],
            content_type=request.content_type,
            reading_level=request.reading_level,
            difficulty_level=request.difficulty_level,
            vocabulary_words=generated_content.get("vocabulary_words", {}),
            learning_objectives=generated_content.get("learning_objectives", []),
            phonics_focus=generated_content.get("phonics_focus", []),
            word_count=complexity_analysis.get("sentence_count", len(generated_content["content"].split())),
            estimated_reading_time=complexity_analysis.get("estimated_reading_time", 60),
            complexity_score=75.0,  # Default complexity score
            created_by=current_user["user_id"]
        )
        
        db.add(new_content)
        db.commit()
        db.refresh(new_content)
        
        return new_content
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating reading content: {str(e)}"
        )

@router.get("/content", response_model=ReadingListResponse)
async def get_reading_content(
    db: db_dependency,
    current_user: dict = user_dependency,
    reading_level: Optional[ReadingLevel] = None,
    difficulty_level: Optional[DifficultyLevel] = None,
    content_type: Optional[str] = None,
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=50)
):
    """Get reading content with optional filtering"""
    
    try:
        query = db.query(ReadingContent).filter(ReadingContent.is_active == True)
        
        # Apply filters
        if reading_level:
            query = query.filter(ReadingContent.reading_level == reading_level)
        if difficulty_level:
            query = query.filter(ReadingContent.difficulty_level == difficulty_level)
        if content_type:
            query = query.filter(ReadingContent.content_type == content_type)
        
        # Get total count
        total_count = query.count()
        
        # Apply pagination
        offset = (page - 1) * size
        content_list = query.offset(offset).limit(size).all()
        
        return ReadingListResponse(
            success=True,
            total_count=total_count,
            items=content_list,
            pagination={
                "page": page,
                "size": size,
                "total_pages": (total_count + size - 1) // size
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching reading content: {str(e)}"
        )

@router.get("/content/{content_id}", response_model=ReadingContentOut)
async def get_content_by_id(
    content_id: int,
    db: db_dependency,
    current_user: dict = user_dependency
):
    """Get specific reading content by ID"""
    
    content = db.query(ReadingContent).filter(
        ReadingContent.id == content_id,
        ReadingContent.is_active == True
    ).first()
    
    if not content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reading content not found"
        )
    
    return content

# ===============================
# READING SESSION ENDPOINTS
# ===============================

@router.post("/sessions/start", response_model=ReadingSessionOut)
async def start_reading_session(
    session_data: ReadingSessionStart,
    db: db_dependency,
    current_user: dict = user_dependency
):
    """Start a new reading session"""
    
    try:
        # Verify content exists
        content = db.query(ReadingContent).filter(
            ReadingContent.id == session_data.content_id,
            ReadingContent.is_active == True
        ).first()
        
        if not content:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Reading content not found"
            )
        
        # Create new session
        new_session = ReadingSession(
            student_id=current_user["user_id"],
            content_id=session_data.content_id,
            session_type=session_data.session_type,
            started_at=datetime.utcnow()
        )
        
        db.add(new_session)
        db.commit()
        db.refresh(new_session)
        
        return new_session
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error starting reading session: {str(e)}"
        )

@router.post("/sessions/{session_id}/complete", response_model=ReadingSessionOut)
async def complete_reading_session(
    session_id: int,
    db: db_dependency,
    current_user: dict = user_dependency
):
    """Mark reading session as complete and update progress"""
    
    try:
        session = db.query(ReadingSession).filter(
            ReadingSession.id == session_id,
            ReadingSession.student_id == current_user["user_id"]
        ).first()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Reading session not found"
            )
        
        # Complete the session
        session.completed_at = datetime.utcnow()
        session.is_completed = True
        
        if session.started_at:
            session.total_duration = int((session.completed_at - session.started_at).total_seconds())
        
        # Calculate overall scores from attempts
        attempts = db.query(ReadingAttempt).filter(
            ReadingAttempt.session_id == session_id
        ).all()
        
        if attempts:
            accuracy_scores = [a.accuracy_percentage for a in attempts if a.accuracy_percentage]
            fluency_scores = [a.fluency_score for a in attempts if a.fluency_score]
            pronunciation_scores = [a.pronunciation_score for a in attempts if a.pronunciation_score]
            
            if accuracy_scores:
                session.accuracy_score = sum(accuracy_scores) / len(accuracy_scores)
            if fluency_scores:
                session.fluency_score = sum(fluency_scores) / len(fluency_scores)
            if pronunciation_scores:
                session.pronunciation_score = sum(pronunciation_scores) / len(pronunciation_scores)
            
            # Calculate weighted overall score
            if session.accuracy_score and session.fluency_score and session.pronunciation_score:
                session.overall_score = (
                    session.accuracy_score * 0.4 +
                    session.fluency_score * 0.3 +
                    session.pronunciation_score * 0.3
                )
        
        # Update student progress
        session_data = {
            'duration': session.total_duration,
            'words_read_correctly': session.accuracy_score or 0
        }
        
        await reading_assistant_service.update_reading_progress(
            student_id=current_user["user_id"],
            session_data=session_data,
            db=db
        )
        
        db.commit()
        db.refresh(session)
        
        return session
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error completing reading session: {str(e)}"
        )

# ===============================
# AUDIO PROCESSING ENDPOINTS
# ===============================

@router.post("/audio/upload", response_model=AudioAnalysisResponse)
async def upload_reading_audio(
    db: db_dependency,
    current_user: dict = user_dependency,
    session_id: int = Form(...),
    content_id: int = Form(...),
    attempt_number: int = Form(1),
    audio_file: UploadFile = File(...)
):
    """Upload and analyze reading audio"""
    
    try:
        # Validate session ownership
        session = db.query(ReadingSession).filter(
            ReadingSession.id == session_id,
            ReadingSession.student_id == current_user["user_id"]
        ).first()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Reading session not found"
            )
        
        # Get content for analysis
        content = db.query(ReadingContent).filter(
            ReadingContent.id == content_id
        ).first()
        
        if not content:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Reading content not found"
            )
        
        # Validate audio file
        if not audio_file.content_type or not audio_file.content_type.startswith('audio/'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid audio file type"
            )
        
        # Save audio file temporarily
        temp_dir = tempfile.mkdtemp()
        audio_filename = f"reading_audio_{session_id}_{attempt_number}_{uuid.uuid4().hex}.wav"
        audio_path = os.path.join(temp_dir, audio_filename)
        
        with open(audio_path, "wb") as f:
            f.write(await audio_file.read())
        
        # Create attempt record
        attempt = ReadingAttempt(
            session_id=session_id,
            content_id=content_id,
            attempt_number=attempt_number,
            audio_file_path=audio_path,
            started_at=datetime.utcnow()
        )
        
        db.add(attempt)
        db.flush()  # Get the attempt ID
        
        # Process audio and analyze reading
        analysis_result = await reading_assistant_service.process_reading_audio(
            audio_file_path=audio_path,
            target_text=content.content,
            reading_level=content.reading_level,
            session_id=session_id,
            db=db
        )
        
        # Update attempt with results
        attempt.transcribed_text = analysis_result.transcribed_text
        attempt.word_accuracy = [wa.dict() for wa in analysis_result.word_accuracy]
        attempt.pronunciation_errors = analysis_result.pronunciation_errors
        attempt.reading_speed = analysis_result.reading_speed
        attempt.pauses_analysis = analysis_result.pauses_analysis
        attempt.accuracy_percentage = analysis_result.accuracy_percentage
        attempt.fluency_score = analysis_result.fluency_score
        attempt.pronunciation_score = analysis_result.pronunciation_score
        attempt.completed_at = datetime.utcnow()
        attempt.duration = int((attempt.completed_at - attempt.started_at).total_seconds())
        
        # Generate feedback message
        feedback_message = await reading_assistant_service._generate_reading_feedback(
            analysis_result.dict(),
            content.content,
            content.reading_level
        )
        
        # Create feedback record
        feedback = ReadingFeedback(
            session_id=session_id,
            feedback_type="encouragement",
            message=feedback_message,
            focus_area="overall_reading",
            is_delivered=True,
            delivered_at=datetime.utcnow()
        )
        
        db.add(feedback)
        db.commit()
        
        # Get recommendations for next content
        recommended_content = await reading_assistant_service.get_recommended_content(
            student_id=current_user["user_id"],
            db=db,
            limit=3
        )

        next_suggestions = [
            {
                "id": rc.id,
                "title": rc.title,
                "reading_level": rc.reading_level.value,
                "difficulty_level": rc.difficulty_level.value
            }
            for rc in recommended_content
        ]

        # Generate pronunciation audio for incorrect words
        pronunciation_urls = {}
        if hasattr(analysis_result, 'word_accuracy'):
            incorrect_words = [
                {
                    "word": wa.spoken_word or "unknown", 
                    "target_word": wa.target_word,
                    "phonetic_tip": wa.pronunciation_tip or f"Say '{wa.target_word}' clearly"
                }
                for wa in analysis_result.word_accuracy 
                if not wa.is_correct and wa.target_word
            ]
            
            if incorrect_words:
                # Generate pronunciation for words that need correction
                try:
                    for word_data in incorrect_words[:5]:  # Limit to 5 words to avoid overload
                        target_word = word_data["target_word"]
                        phonetic_tip = word_data["phonetic_tip"]
                        
                        pronunciation_result = await tts_service.generate_word_pronunciation(
                            word=target_word,
                            phonetic_hint=phonetic_tip
                        )
                        
                        if pronunciation_result["success"]:
                            pronunciation_urls[target_word] = {
                                "audio_url": pronunciation_result["audio_url"],
                                "duration_seconds": pronunciation_result["duration_seconds"],
                                "instructions": f"Tap to hear how to say '{target_word}' correctly"
                            }
                except Exception as e:
                    print(f"⚠️ Pronunciation generation warning: {e}")
                    # Don't fail the whole request if TTS fails        # Clean up temporary file
        try:
            os.unlink(audio_path)
            os.rmdir(temp_dir)
        except:
            pass  # Don't fail if cleanup fails
        
        return AudioAnalysisResponse(
            success=True,
            attempt_id=attempt.id,
            transcribed_text=analysis_result.transcribed_text,
            analysis_results=analysis_result,
            feedback_message=feedback_message,
            next_suggestions=next_suggestions,
            pronunciation_urls=pronunciation_urls  # Add pronunciation URLs
        )
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing audio: {str(e)}"
        )

# ===============================
# PROGRESS & ANALYTICS ENDPOINTS
# ===============================

@router.get("/progress", response_model=ReadingProgressOut)
async def get_reading_progress(
    db: db_dependency,
    current_user: dict = user_dependency,
    student_id: Optional[int] = None
):
    """Get student's reading progress"""
    
    # Use current user if no student_id provided
    target_student_id = student_id or current_user["user_id"]
    
    # TODO: Add permission check for accessing other students' progress
    
    progress = db.query(ReadingProgress).filter_by(student_id=target_student_id).first()
    
    if not progress:
        # Create initial progress record
        progress = ReadingProgress(
            student_id=target_student_id,
            current_reading_level=ReadingLevel.KINDERGARTEN,
            current_difficulty=DifficultyLevel.BEGINNER
        )
        db.add(progress)
        db.commit()
        db.refresh(progress)
    
    return progress

@router.get("/dashboard", response_model=StudentReadingDashboard)
async def get_student_dashboard(
    db: db_dependency,
    current_user: dict = user_dependency
):
    """Get comprehensive reading dashboard for student"""
    
    try:
        student_id = current_user["user_id"]
        
        # Get progress
        progress = db.query(ReadingProgress).filter_by(student_id=student_id).first()
        if not progress:
            progress = ReadingProgress(
                student_id=student_id,
                current_reading_level=ReadingLevel.KINDERGARTEN,
                current_difficulty=DifficultyLevel.BEGINNER
            )
            db.add(progress)
            db.commit()
            db.refresh(progress)
        
        # Get recent sessions
        recent_sessions = db.query(ReadingSession).filter_by(
            student_id=student_id
        ).order_by(ReadingSession.started_at.desc()).limit(5).all()
        
        # Get active goals
        active_goals = db.query(ReadingGoal).filter_by(
            student_id=student_id,
            is_active=True,
            is_achieved=False
        ).all()
        
        # Get recommended content
        recommended_content = await reading_assistant_service.get_recommended_content(
            student_id=student_id,
            db=db,
            limit=5
        )
        
        # Calculate weekly stats
        week_ago = datetime.utcnow() - timedelta(days=7)
        weekly_sessions = db.query(ReadingSession).filter(
            ReadingSession.student_id == student_id,
            ReadingSession.started_at >= week_ago
        ).all()
        
        weekly_stats = {
            "sessions_completed": len([s for s in weekly_sessions if s.is_completed]),
            "total_reading_time": sum([s.total_duration or 0 for s in weekly_sessions]),
            "average_accuracy": sum([s.accuracy_score or 0 for s in weekly_sessions]) / max(len(weekly_sessions), 1),
            "words_practiced": progress.words_read_correctly  # This week's words (simplified)
        }
        
        # Mock achievements (could be expanded)
        achievements = [
            {"type": "streak", "title": "5 Day Reading Streak!", "earned_date": datetime.utcnow()},
            {"type": "accuracy", "title": "90% Accuracy Master", "earned_date": datetime.utcnow() - timedelta(days=2)}
        ]
        
        return StudentReadingDashboard(
            student_info={"id": student_id, "name": current_user.get("name", "Student")},
            current_progress=progress,
            recent_sessions=recent_sessions,
            active_goals=active_goals,
            achievements=achievements,
            recommended_content=recommended_content,
            weekly_stats=weekly_stats
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating dashboard: {str(e)}"
        )

# ===============================
# GOAL SETTING ENDPOINTS
# ===============================

@router.post("/goals", response_model=GoalOut)
async def create_reading_goal(
    goal_data: GoalCreate,
    db: db_dependency,
    current_user: dict = user_dependency
):
    """Create a new reading goal for student"""
    
    try:
        new_goal = ReadingGoal(
            student_id=current_user["user_id"],
            goal_type=goal_data.goal_type,
            target_value=goal_data.target_value,
            target_date=goal_data.target_date,
            title=goal_data.title,
            description=goal_data.description
        )
        
        db.add(new_goal)
        db.commit()
        db.refresh(new_goal)
        
        return new_goal
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating reading goal: {str(e)}"
        )

@router.get("/goals", response_model=List[GoalOut])
async def get_reading_goals(
    db: db_dependency,
    current_user: dict = user_dependency,
    active_only: bool = Query(True)
):
    """Get student's reading goals"""
    
    query = db.query(ReadingGoal).filter_by(student_id=current_user["user_id"])
    
    if active_only:
        query = query.filter(ReadingGoal.is_active == True)
    
    goals = query.order_by(ReadingGoal.created_at.desc()).all()
    return goals

# ===============================
# RECOMMENDATIONS ENDPOINT
# ===============================

@router.get("/recommendations", response_model=List[ReadingContentOut])
async def get_content_recommendations(
    db: db_dependency,
    current_user: dict = user_dependency,
    limit: int = Query(5, ge=1, le=20)
):
    """Get personalized content recommendations"""
    
    try:
        recommendations = await reading_assistant_service.get_recommended_content(
            student_id=current_user["user_id"],
            db=db,
            limit=limit
        )
        
        return recommendations
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting recommendations: {str(e)}"
        )

# ===============================
# LIVE AUDIO SESSION (WebSocket - Future Enhancement)
# ===============================

# Note: WebSocket implementation would go here for real-time audio processing
# This would allow live feedback as the student reads

# ===============================
# TEXT-TO-SPEECH PRONUNCIATION ENDPOINTS
# ===============================

@router.post("/pronunciation/word")
async def get_word_pronunciation(
    request: dict,
    current_user: dict = user_dependency
):
    """Get pronunciation audio for a specific word"""
    
    try:
        word = request.get("word", "").strip()
        phonetic_hint = request.get("phonetic_hint")
        context = request.get("context")
        
        if not word:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Word is required"
            )
        
        # Generate pronunciation audio
        result = await tts_service.generate_word_pronunciation(
            word=word,
            phonetic_hint=phonetic_hint,
            context=context
        )
        
        return {
            "success": result["success"],
            "word": word,
            "audio_url": result["audio_url"],
            "duration_seconds": result["duration_seconds"],
            "phonetic_hint": phonetic_hint,
            "context": context,
            "pronunciation_instructions": f"Tap to hear how to say '{word}' correctly"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating pronunciation: {str(e)}"
        )

@router.post("/pronunciation/sentence")
async def get_sentence_pronunciation(
    request: dict,
    current_user: dict = user_dependency
):
    """Get pronunciation audio for a sentence with highlighted words"""
    
    try:
        sentence = request.get("sentence", "").strip()
        highlight_words = request.get("highlight_words", [])
        
        if not sentence:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Sentence is required"
            )
        
        # Generate sentence pronunciation
        result = await tts_service.generate_sentence_pronunciation(
            sentence=sentence,
            highlight_words=highlight_words
        )
        
        return {
            "success": result["success"],
            "sentence": sentence,
            "audio_url": result["audio_url"],
            "duration_seconds": result["duration_seconds"],
            "highlighted_words": highlight_words,
            "pronunciation_instructions": "Tap to hear the correct pronunciation"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating sentence pronunciation: {str(e)}"
        )

@router.get("/pronunciation-audio/{filename}")
async def serve_pronunciation_audio(filename: str):
    """Serve generated pronunciation audio files"""
    
    try:
        # Construct file path
        audio_dir = Path(tempfile.gettempdir()) / "reading_assistant_tts"
        file_path = audio_dir / filename
        
        if not file_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pronunciation audio not found"
            )
        
        # Determine media type
        media_type = "audio/mpeg" if filename.endswith(".mp3") else "audio/wav"
        
        return FileResponse(
            path=str(file_path),
            media_type=media_type,
            filename=filename
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error serving pronunciation audio: {str(e)}"
        )

@router.post("/pronunciation/feedback-words")
async def get_feedback_words_pronunciation(
    request: dict,
    current_user: dict = user_dependency
):
    """Generate pronunciation for words that need correction based on analysis"""
    
    try:
        words_to_correct = request.get("words", [])
        reading_level = request.get("reading_level", "kindergarten")
        
        if not words_to_correct:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Words list is required"
            )
        
        pronunciation_results = []
        
        for word_data in words_to_correct:
            word = word_data.get("word", "")
            target_word = word_data.get("target_word", word)
            phonetic_tip = word_data.get("phonetic_tip", "")
            
            if word:
                # Generate pronunciation for the target (correct) word
                result = await tts_service.generate_word_pronunciation(
                    word=target_word,
                    phonetic_hint=phonetic_tip,
                    context=f"The correct pronunciation of {word}"
                )
                
                pronunciation_results.append({
                    "original_word": word,
                    "target_word": target_word,
                    "audio_url": result["audio_url"],
                    "duration_seconds": result["duration_seconds"],
                    "phonetic_tip": phonetic_tip,
                    "success": result["success"]
                })
        
        return {
            "success": True,
            "reading_level": reading_level,
            "pronunciation_results": pronunciation_results,
            "instructions": "Tap on any word to hear the correct pronunciation",
            "total_words": len(pronunciation_results)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating feedback pronunciations: {str(e)}"
        )

# ===============================
# ENHANCED AUDIO ANALYSIS WITH TTS
# ===============================

@router.post("/debug-ai")
async def debug_ai_analysis(
    debug_data: dict,
    db: db_dependency,
    current_user: dict = user_dependency
):
    """Debug endpoint to see raw AI response"""
    
    try:
        expected_text = debug_data.get("expected_text", "")
        transcribed_text = debug_data.get("transcribed_text", "")
        reading_level = debug_data.get("reading_level", "kindergarten")
        
        # Get raw AI response
        ai_result = await gemini_service.analyze_speech_performance(
            expected_text=expected_text,
            transcribed_text=transcribed_text,
            reading_level=reading_level
        )
        
        return {
            "debug": True,
            "raw_ai_response": ai_result,
            "input_data": debug_data
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Debug error: {str(e)}"
        )

@router.get("/health")
async def health_check():
    """Health check endpoint for reading assistant service"""
    return {
        "status": "healthy",
        "service": "reading-assistant",
        "version": "1.0.0",
        "features": [
            "ai_content_generation",
            "speech_analysis", 
            "progress_tracking",
            "personalized_recommendations"
        ]
    }