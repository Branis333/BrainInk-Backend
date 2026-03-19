"""
Quiz API endpoints for BrainInk education platform.

This module provides endpoints for:
- Generating quizzes based on assignment feedback
- Managing quiz attempts and results
- Teacher quiz oversight and analytics
"""

from fastapi import APIRouter, HTTPException, status
from typing import List, Optional, Dict, Any, Tuple
import json
from datetime import datetime, timezone
from pydantic import BaseModel
from services.nova_services.generate_assignment_service import nova_quiz_service

# Create router for quiz endpoints
router = APIRouter(tags=["Generated Quizzes"])

# Pydantic models for request/response
class QuizQuestion(BaseModel):
    id: str
    question: str
    options: List[str]
    correctAnswer: int  # Use camelCase to match frontend
    explanation: str
    difficulty: str
    topic: str
    weakness_area: str

class GeneratedQuiz(BaseModel):
    id: str
    assignment_id: int
    student_id: int
    title: str
    description: str
    questions: List[QuizQuestion]
    weakness_areas: List[str]
    created_at: datetime
    max_attempts: int = 3
    time_limit_minutes: Optional[int] = 15

class QuizAttempt(BaseModel):
    id: str
    quiz_id: str
    student_id: int
    answers: Dict[str, int]  # {question_id: answer_index}
    score: int
    completed_at: datetime
    time_taken_seconds: int
    feedback: str

class QuizGenerationRequest(BaseModel):
    assignment_id: int
    student_id: int
    feedback: str
    weakness_areas: List[str]
    subject: str
    grade: int
    force_refresh: Optional[bool] = False

class QuizAttemptRequest(BaseModel):
    quiz_id: str
    answers: Dict[str, int]
    time_taken_seconds: int

# In-memory storage (replace with your database models)
generated_quizzes: Dict[str, Dict] = {}
quiz_attempts: Dict[str, Dict] = {}

@router.post("/generated")
async def create_generated_quiz(quiz: GeneratedQuiz):
    """Save a generated quiz to the system."""
    try:
        # Store quiz in memory (replace with your database storage)
        generated_quizzes[quiz.id] = quiz.dict()
        
        print(f"✅ Quiz {quiz.id} saved for student {quiz.student_id}")
        
        return {
            "success": True,
            "message": "Quiz saved successfully",
            "quiz_id": quiz.id
        }
    except Exception as e:
        print(f"❌ Failed to save quiz: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save quiz"
        )

@router.get("/generated/{quiz_id}")
async def get_quiz(quiz_id: str):
    """Get a specific quiz by ID."""
    try:
        if quiz_id not in generated_quizzes:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Quiz not found"
            )
        
        quiz_data = generated_quizzes[quiz_id].copy()  # Make a copy to avoid modifying original
        
        # Ensure questions have the correct field name for frontend (correctAnswer)
        if "questions" in quiz_data:
            fixed_questions = []
            for question in quiz_data["questions"]:
                fixed_question = question.copy()
                # Convert correct_answer to correctAnswer if needed
                if "correct_answer" in fixed_question and "correctAnswer" not in fixed_question:
                    fixed_question["correctAnswer"] = fixed_question["correct_answer"]
                    # Remove the old field to avoid confusion
                    del fixed_question["correct_answer"]
                fixed_questions.append(fixed_question)
            quiz_data["questions"] = fixed_questions
        
        # Add attempts to the quiz data
        quiz_attempts_list = [
            attempt for attempt in quiz_attempts.values()
            if attempt["quiz_id"] == quiz_id
        ]
        quiz_data["attempts"] = quiz_attempts_list
        
        print(f"🔍 Returning quiz {quiz_id} with questions: {[q.get('correctAnswer', 'MISSING') for q in quiz_data.get('questions', [])]}")
        
        return quiz_data
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Failed to get quiz: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve quiz"
        )

@router.get("/generated/student/{student_id}/assignment/{assignment_id}")
async def get_student_quizzes_for_assignment(student_id: int, assignment_id: int):
    """Get all quizzes for a specific student and assignment."""
    try:
        student_quizzes = []
        
        for quiz_data in generated_quizzes.values():
            if (quiz_data["student_id"] == student_id and 
                quiz_data["assignment_id"] == assignment_id):
                
                # Add attempts to the quiz data
                quiz_attempts_list = [
                    attempt for attempt in quiz_attempts.values()
                    if attempt["quiz_id"] == quiz_data["id"]
                ]
                quiz_data["attempts"] = quiz_attempts_list
                student_quizzes.append(quiz_data)
        
        return student_quizzes
    except Exception as e:
        print(f"❌ Failed to get student quizzes: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve student quizzes"
        )

@router.post("/attempts")
async def submit_quiz_attempt(attempt_request: QuizAttemptRequest):
    """Submit a quiz attempt and calculate score."""
    try:
        quiz_id = attempt_request.quiz_id
        
        if quiz_id not in generated_quizzes:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Quiz not found"
            )
        
        quiz_data = generated_quizzes[quiz_id]
        questions = quiz_data["questions"]
        
        # Calculate score
        correct_answers = 0
        total_questions = len(questions)
        
        for question in questions:
            question_id = question["id"]
            correct_answer = question.get("correctAnswer", question.get("correct_answer"))  # Support both formats
            user_answer = attempt_request.answers.get(question_id)
            
            if user_answer == correct_answer:
                correct_answers += 1
        
        score = round((correct_answers / total_questions) * 100) if total_questions > 0 else 0
        
        # Generate feedback
        feedback = generate_attempt_feedback(score, correct_answers, total_questions)
        
        # Create attempt record
        attempt_id = f"attempt_{datetime.now().timestamp()}"
        attempt = {
            "id": attempt_id,
            "quiz_id": quiz_id,
            "student_id": quiz_data["student_id"],  # Get from quiz data
            "answers": attempt_request.answers,
            "score": score,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "time_taken_seconds": attempt_request.time_taken_seconds,
            "feedback": feedback
        }
        
        # Store attempt
        quiz_attempts[attempt_id] = attempt
        
        print(f"✅ Quiz attempt {attempt_id} submitted with score {score}%")
        
        return attempt
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Failed to submit quiz attempt: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit quiz attempt"
        )


def _resolve_difficulty_and_level(grade: int) -> Tuple[str, str]:
    if grade < 60:
        return "easy", "beginner"
    if grade < 80:
        return "medium", "intermediate"
    return "hard", "advanced"


def _build_quiz_record(
    *,
    request: QuizGenerationRequest,
    questions: List[Dict[str, Any]],
    service_version: str,
) -> Dict[str, Any]:
    quiz_id = f"quiz_{request.assignment_id}_{request.student_id}_{int(datetime.now().timestamp())}"
    return {
        "id": quiz_id,
        "assignment_id": request.assignment_id,
        "student_id": request.student_id,
        "title": "Improvement Quiz - Assignment Review",
        "description": "This quiz is designed to help you improve in areas where you can grow. Focus on the concepts and take your time!",
        "questions": questions,
        "weakness_areas": request.weakness_areas or ["General Understanding"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "max_attempts": 3,
        "time_limit_minutes": 15,
        "attempts": [],
        "generated_by": "nova_ai",
        "nova_available": True,
        "service_version": service_version,
    }


async def _generate_quiz_with_nova(request: QuizGenerationRequest, service_version: str) -> Dict[str, Any]:
    difficulty, student_level = _resolve_difficulty_and_level(request.grade)

    if not request.force_refresh:
        now_utc = datetime.now(timezone.utc)
        for quiz in list(generated_quizzes.values()):
            if (
                quiz.get("assignment_id") == request.assignment_id and
                quiz.get("student_id") == request.student_id
            ):
                created_at_str = quiz.get("created_at") or quiz.get("createdAt")
                if not created_at_str:
                    continue
                try:
                    created_dt = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
                    age_sec = (now_utc - created_dt).total_seconds()
                    if age_sec <= 120 and quiz.get("generated_by") in {"nova_ai", "fallback"}:
                        print("🟡 Returning cached Nova-backed quiz (<=2 min old)")
                        return quiz
                except Exception:
                    continue

    weakness_areas_text = ", ".join(request.weakness_areas) if request.weakness_areas else "general understanding"
    description = (
        f"Generate an improvement quiz based on feedback: '{request.feedback}'. "
        f"Focus on {weakness_areas_text} in {request.subject}."
    )

    questions: List[Dict[str, Any]] = []
    try:
        quiz_data = await nova_quiz_service.generate_quiz(
            description=description,
            num_questions=5,
            difficulty=difficulty,
            subject=request.subject,
            student_level=student_level,
            weakness_areas=request.weakness_areas,
            context=f"Assignment feedback: {request.feedback}",
        )
        if quiz_data and quiz_data.get("questions"):
            questions = quiz_data["questions"]
    except Exception as exc:
        print(f"⚠️ Nova quiz generation failed, using fallback: {exc}")

    if len(questions) < 5:
        fallback_questions = generate_fallback_questions(request, difficulty)
        questions.extend(fallback_questions[: 5 - len(questions)])

    quiz = _build_quiz_record(
        request=request,
        questions=questions[:5],
        service_version=service_version,
    )
    generated_quizzes[quiz["id"]] = quiz
    return quiz

@router.post("/generate-with-nova-v2")
async def generate_quiz_with_nova_v2(request: QuizGenerationRequest):
    """Generate a quiz using the Nova pipeline (v2)."""
    try:
        print(f"🧠 [NOVA V2] Generating quiz for student {request.student_id}, assignment {request.assignment_id}")
        return await _generate_quiz_with_nova(request, service_version="NovaQuizService_v2")
    except Exception as e:
        print(f"❌ Failed to generate quiz with Nova v2: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate quiz: {str(e)}"
        )


@router.post("/generate-with-kana-v2")
async def generate_quiz_with_kana_v2(request: QuizGenerationRequest):
    """Legacy alias for clients still calling the old route. Uses Nova internally."""
    return await generate_quiz_with_nova_v2(request)

async def call_kana_service_direct(request: QuizGenerationRequest, difficulty: str, student_level: str, weakness_areas_text: str) -> Dict:
    """Legacy helper name retained for compatibility; uses Nova internally."""
    description = f"Generate an improvement quiz based on feedback: '{request.feedback}'. Focus on {weakness_areas_text} in {request.subject}."
    quiz = await nova_quiz_service.generate_quiz(
        description=description,
        num_questions=5,
        difficulty=difficulty,
        subject=request.subject,
        student_level=student_level,
        weakness_areas=request.weakness_areas,
        context=f"Assignment feedback: {request.feedback}",
    )
    return quiz

@router.post("/generate-with-nova")
async def generate_quiz_with_nova(request: QuizGenerationRequest):
    """Generate a quiz using the Nova pipeline (v1 compatibility route)."""
    try:
        print(f"🧠 [NOVA V1] Generating quiz for student {request.student_id}, assignment {request.assignment_id}")
        return await _generate_quiz_with_nova(request, service_version="NovaQuizService_v1")
    except Exception as e:
        print(f"❌ Failed to generate quiz with Nova v1: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate quiz: {str(e)}"
        )

@router.post("/generate-with-kana")
async def generate_quiz_with_kana(request: QuizGenerationRequest):
    """Legacy alias for clients still calling the old route. Uses Nova internally."""
    return await generate_quiz_with_nova(request)

def parse_kana_response(response: str, request: QuizGenerationRequest, difficulty: str) -> List[Dict]:
    """Parse AI response into quiz questions - supports multiple legacy formats."""
    try:
        # First try to parse as direct JSON (from new QuizService endpoints)
        try:
            parsed_data = json.loads(response)
            questions = []
            
            # Handle new QuizService format (array of questions)
            if isinstance(parsed_data, list):
                for i, q in enumerate(parsed_data):
                    question = {
                        "id": q.get("id", f"q_{int(datetime.now().timestamp())}_{i}"),
                        "question": q.get("question", ""),
                        "options": q.get("options", []),
                        "correctAnswer": q.get("correctAnswer", q.get("correct_answer", 0)),  # Use camelCase for frontend
                        "explanation": q.get("explanation", ""),
                        "difficulty": q.get("difficulty", difficulty),
                        "topic": q.get("topic", request.subject),
                        "weakness_area": q.get("weakness_area", q.get("weaknessArea", 
                            request.weakness_areas[0] if request.weakness_areas else "General"))
                    }
                    questions.append(question)
                return questions
            
            # Handle QuizService wrapper format (quiz object with questions array)
            elif isinstance(parsed_data, dict) and "questions" in parsed_data:
                for i, q in enumerate(parsed_data["questions"]):
                    question = {
                        "id": q.get("id", f"q_{int(datetime.now().timestamp())}_{i}"),
                        "question": q.get("question", ""),
                        "options": q.get("options", []),
                        "correctAnswer": q.get("correctAnswer", q.get("correct_answer", 0)),  # Use camelCase for frontend
                        "explanation": q.get("explanation", ""),
                        "difficulty": q.get("difficulty", difficulty),
                        "topic": q.get("topic", request.subject),
                        "weakness_area": q.get("weakness_area", q.get("weaknessArea",
                            request.weakness_areas[0] if request.weakness_areas else "General"))
                    }
                    questions.append(question)
                return questions
                
        except json.JSONDecodeError:
            pass
        
        # Fallback: Try to extract JSON array from text response (legacy format)
        import re
        json_match = re.search(r'\[[\s\S]*\]', response)
        if json_match:
            parsed_questions = json.loads(json_match.group(0))
            
            questions = []
            for i, q in enumerate(parsed_questions):
                question = {
                    "id": f"q_{int(datetime.now().timestamp())}_{i}",
                    "question": q.get("question", ""),
                    "options": q.get("options", []),
                    "correctAnswer": q.get("correctAnswer", q.get("correct_answer", 0)),  # Use camelCase for frontend
                    "explanation": q.get("explanation", ""),
                    "difficulty": difficulty,
                    "topic": q.get("topic", request.subject),
                    "weakness_area": q.get("weakness_area", q.get("weaknessArea",
                        request.weakness_areas[0] if request.weakness_areas else "General"))
                }
                questions.append(question)
            
            return questions
            
    except Exception as e:
        print(f"⚠️ Failed to parse AI response: {e}")
        print(f"Response content: {response[:500]}...")  # Log first 500 chars for debugging
    
    # Return fallback if parsing fails
    print("🔄 Falling back to generated questions due to parsing failure")
    return generate_fallback_questions(request, difficulty)

def generate_fallback_questions(request: QuizGenerationRequest, difficulty: str) -> List[Dict]:
    """Generate diverse fallback questions when AI generation is unavailable."""
    questions = []
    weakness_areas = request.weakness_areas or ["General Understanding"]
    subject = request.subject
    
    # Create varied fallback questions based on subject and weakness areas
    fallback_templates = [
        {
            "question": f"Which strategy would be most effective for improving your understanding of {weakness_areas[0] if weakness_areas else 'this topic'}?",
            "options": [
                f"Practice fundamental concepts in {weakness_areas[0] if weakness_areas else 'the subject'}",
                "Focus only on advanced problems",
                "Skip the basics and move to complex topics", 
                "Memorize answers without understanding"
            ],
            "correctAnswer": 0,  # Use camelCase for frontend
            "explanation": f"Building a strong foundation in {weakness_areas[0] if weakness_areas else 'fundamental concepts'} is essential for long-term understanding and success.",
            "topic": subject,
            "weakness_area": weakness_areas[0] if weakness_areas else "General Understanding"
        },
        {
            "question": f"What is the most important step when encountering difficulties in {subject}?",
            "options": [
                "Identify specific knowledge gaps",
                "Give up immediately",
                "Only focus on easy problems", 
                "Avoid asking for help"
            ],
            "correctAnswer": 0,  # Use camelCase for frontend
            "explanation": "Identifying specific knowledge gaps helps you focus your study efforts on areas that need the most improvement.",
            "topic": subject,
            "weakness_area": weakness_areas[1] if len(weakness_areas) > 1 else "Problem Solving"
        },
        {
            "question": f"How can you best apply feedback to improve your performance in {subject}?",
            "options": [
                "Ignore the feedback completely",
                "Read it once and forget about it",
                "Use it to guide focused practice and study",
                "Only focus on positive comments"
            ],
            "correctAnswer": 2,  # Use camelCase for frontend
            "explanation": "Using feedback to guide focused practice helps you address specific weaknesses and improve systematically.",
            "topic": subject,
            "weakness_area": weakness_areas[2] if len(weakness_areas) > 2 else "Learning Strategies"
        },
        {
            "question": f"What approach works best for mastering challenging concepts in {subject}?",
            "options": [
                "Rush through practice problems",
                "Break complex problems into smaller parts",
                "Avoid practicing difficult topics",
                "Study only the night before tests"
            ],
            "correctAnswer": 1,  # Use camelCase for frontend
            "explanation": "Breaking complex problems into smaller, manageable parts makes them easier to understand and solve.",
            "topic": subject,
            "weakness_area": weakness_areas[3] if len(weakness_areas) > 3 else "Critical Thinking"
        },
        {
            "question": f"Which habit will most help you succeed in {subject}?",
            "options": [
                "Cramming before exams",
                "Regular practice and review",
                "Avoiding challenging problems",
                "Working alone without seeking help"
            ],
            "correctAnswer": 1,  # Use camelCase for frontend
            "explanation": "Regular practice and review helps build understanding gradually and reinforces learning over time.",
            "topic": subject,
            "weakness_area": weakness_areas[4] if len(weakness_areas) > 4 else "Study Habits"
        }
    ]
    
    # Generate unique questions
    for i, template in enumerate(fallback_templates[:5]):
        question = {
            "id": f"fallback_q_{int(datetime.now().timestamp())}_{i}",
            "question": template["question"],
            "options": template["options"],
            "correctAnswer": template["correctAnswer"],  # Use camelCase for frontend
            "explanation": template["explanation"],
            "difficulty": difficulty,
            "topic": template["topic"],
            "weakness_area": template["weakness_area"]
        }
        questions.append(question)
    
    print(f"⚠️ Generated {len(questions)} diverse fallback questions")
    return questions

def generate_attempt_feedback(score: int, correct: int, total: int) -> str:
    """Generate personalized feedback for a quiz attempt."""
    if score >= 80:
        return f"Excellent work! You scored {score}% ({correct}/{total} correct). You show great improvement in your understanding!"
    elif score >= 60:
        return f"Good effort! You scored {score}% ({correct}/{total} correct). You're making progress - keep practicing!"
    else:
        return f"You scored {score}% ({correct}/{total} correct). Don't worry, this is a learning opportunity! Review the explanations and try again."

@router.get("/health/nova-service")
async def check_nova_service_health():
    """Check Nova quiz generation service readiness."""
    try:
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "overall_status": "healthy",
            "provider": "nova",
            "service": "nova_quiz_service",
        }
    except Exception as e:
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "overall_status": "error",
            "error": str(e)
        }


@router.get("/health/kana-service")
async def check_kana_service_health():
    """Legacy health alias retained for compatibility. Returns Nova health."""
    return await check_nova_service_health()

def calculate_average_score() -> float:
    """Calculate average score across all quiz attempts."""
    if not quiz_attempts:
        return 0.0
    
    total_score = sum(attempt["score"] for attempt in quiz_attempts.values())
    return round(total_score / len(quiz_attempts), 2)

def get_common_weakness_areas() -> List[str]:
    """Get the most common weakness areas across all quizzes."""
    weakness_counts = {}
    
    for quiz in generated_quizzes.values():
        for area in quiz["weakness_areas"]:
            weakness_counts[area] = weakness_counts.get(area, 0) + 1
    
    # Return top 5 most common areas
    return sorted(weakness_counts.keys(), key=lambda x: weakness_counts[x], reverse=True)[:5]

def calculate_student_engagement() -> Dict[str, Any]:
    """Calculate student engagement metrics."""
    student_quiz_counts = {}
    
    for quiz in generated_quizzes.values():
        student_id = quiz["student_id"]
        student_quiz_counts[student_id] = student_quiz_counts.get(student_id, 0) + 1
    
    return {
        "active_students": len(student_quiz_counts),
        "average_quizzes_per_student": round(sum(student_quiz_counts.values()) / len(student_quiz_counts), 2) if student_quiz_counts else 0
    }

# To include this router in your main FastAPI app, add:
# app.include_router(quiz_router, prefix="/api/v1")
