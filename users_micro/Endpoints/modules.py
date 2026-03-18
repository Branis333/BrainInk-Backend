"""
Quiz API endpoints for BrainInk education platform.

This module provides endpoints for:
- Generating quizzes based on assignment feedback
- Managing quiz attempts and results
- Teacher quiz oversight and analytics
"""

from fastapi import APIRouter, HTTPException, status
from typing import List, Optional, Dict, Any
import json
import requests
from datetime import datetime, timezone
from pydantic import BaseModel
import uuid

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

@router.post("/generate-with-kana-v2")
async def generate_quiz_with_kana_v2(request: QuizGenerationRequest):
    """Generate a quiz using the new Kana AI QuizService with improved integration."""
    try:
        print(f"🧠 [V2] Generating quiz for student {request.student_id}, assignment {request.assignment_id}")
        
        # Determine difficulty based on grade
        if request.grade < 60:
            difficulty = "easy"
            student_level = "beginner"
        elif request.grade < 80:
            difficulty = "medium" 
            student_level = "intermediate"
        else:
            difficulty = "hard"
            student_level = "advanced"

        # Short-lived cache: if we recently generated a Kana-backed quiz for this assignment+student, reuse it
        try:
            from datetime import timezone as _tz
            now_iso = datetime.now(_tz.utc)
            for quiz in list(generated_quizzes.values()):
                if (
                    quiz.get("assignment_id") == request.assignment_id and
                    quiz.get("student_id") == request.student_id
                ):
                    # Respect explicit force refresh from client
                    if request.force_refresh:
                        break
                    created_at_str = quiz.get("created_at") or quiz.get("createdAt")
                    if created_at_str:
                        try:
                            created_dt = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
                            age_sec = (now_iso - created_dt).total_seconds()
                            # Only return cache if it was generated by Kana (not fallback)
                            if age_sec <= 120 and (quiz.get("kana_available") is True or quiz.get("generated_by") in {"kana_ai_v2", "kana_ai"}):
                                print("🟡 Using cached Kana-backed quiz to avoid extra KANA calls (<=2min old)")
                                return quiz
                        except Exception:
                            pass
        except Exception:
            pass
        
        weakness_areas_text = ", ".join(request.weakness_areas) if request.weakness_areas else "general understanding"
        
        # Try new QuizService endpoints directly
        questions = []
        kana_error = None
        
        try:
            print("🤖 Calling Kana AI QuizService endpoints...")
            quiz_data = await call_kana_service_direct(request, difficulty, student_level, weakness_areas_text)
            
            if quiz_data and quiz_data.get("questions"):
                questions = quiz_data["questions"]
                print(f"✅ QuizService returned {len(questions)} questions")
            else:
                raise Exception("No questions returned from QuizService")
                
        except Exception as e:
            kana_error = str(e)
            print(f"❌ Kana QuizService failed: {kana_error}")
            
        # Only use fallback if QuizService completely failed
        if len(questions) == 0:
            print("🔄 Using fallback generation as Kana QuizService is unavailable")
            questions = generate_fallback_questions(request, difficulty)
        
        # Ensure we have exactly 5 questions
        if len(questions) < 5:
            print(f"⚠️ Only {len(questions)} questions available, padding with fallback")
            fallback_questions = generate_fallback_questions(request, difficulty)
            questions.extend(fallback_questions[:5-len(questions)])
        
        questions = questions[:5]  # Ensure exactly 5 questions
        
        # Create quiz object
        quiz_id = f"quiz_{request.assignment_id}_{request.student_id}_{int(datetime.now().timestamp())}"
        quiz = {
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
            "generated_by": "kana_ai_v2" if kana_error is None else "fallback",
            "kana_available": kana_error is None,
            "service_version": "QuizService_v2"
        }
        
        # Save quiz
        generated_quizzes[quiz_id] = quiz
        
        print(f"✅ Quiz {quiz_id} generated successfully with {len(questions)} questions using QuizService")
        if kana_error:
            print(f"⚠️ Note: Fallback used due to Kana error: {kana_error}")
        
        return quiz
        
    except Exception as e:
        print(f"❌ Failed to generate quiz with QuizService: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate quiz: {str(e)}"
        )

async def call_kana_service_direct(request: QuizGenerationRequest, difficulty: str, student_level: str, weakness_areas_text: str) -> Dict:
    """Call Kana AI QuizService directly with structured request, with retry/backoff on rate limits."""
    kana_urls = [
        "https://kana-backend-app.onrender.com",
        "http://localhost:10000",
    ]
    
    # Exponential backoff parameters
    max_retries = 3
    base_delay = 1.5  # seconds

    for base_url in kana_urls:
        try:
            print(f"🔗 Trying QuizService at: {base_url}")
            
            # Use the improvement quiz endpoint (most appropriate for this use case)
            improvement_url = f"{base_url}/api/kana/generate-improvement-quiz"
            
            payload = {
                "assignment_id": request.assignment_id,
                "student_id": request.student_id,
                "feedback": request.feedback,
                "weakness_areas": request.weakness_areas,
                "subject": request.subject,
                "grade": student_level,
                "numQuestions": 5,
                "context": f"Student grade: {request.grade}, Difficulty: {difficulty}"
            }
            
            # Retry improvement endpoint on 429/503
            for attempt in range(max_retries):
                response = requests.post(
                    improvement_url,
                    json=payload,
                    timeout=30,
                    headers={"Content-Type": "application/json"}
                )
                if response.status_code == 200:
                    data = response.json()
                    print(f"✅ Successfully got quiz from improvement endpoint")
                    return data
                if response.status_code in (429, 503):
                    retry_after = response.headers.get("Retry-After")
                    delay = float(retry_after) if retry_after else (base_delay * (2 ** attempt))
                    print(f"⏳ Rate limited (status {response.status_code}). Retrying in {delay:.1f}s...")
                    import asyncio as _asyncio
                    await _asyncio.sleep(delay)
                    continue
                # Non-retryable
                print(f"⚠️ Improvement endpoint returned status {response.status_code}: {response.text}")
                break
            
            # Fallback to description-based generation
            description_url = f"{base_url}/api/kana/generate-quiz-by-description"
            
            description = f"Generate an improvement quiz based on feedback: '{request.feedback}'. Focus on {weakness_areas_text} in {request.subject}."
            
            payload = {
                "description": description,
                "numQuestions": 5,
                "difficulty": difficulty,
                "subject": request.subject,
                "studentLevel": student_level,
                "weaknessAreas": request.weakness_areas,
                "context": f"Assignment feedback: {request.feedback}"
            }
            
            # Retry description endpoint on 429/503
            for attempt in range(max_retries):
                response = requests.post(
                    description_url,
                    json=payload,
                    timeout=30,
                    headers={"Content-Type": "application/json"}
                )
                if response.status_code == 200:
                    data = response.json()
                    if data.get("quiz"):
                        print(f"✅ Successfully got quiz from description endpoint")
                        return data["quiz"]
                if response.status_code in (429, 503):
                    retry_after = response.headers.get("Retry-After")
                    delay = float(retry_after) if retry_after else (base_delay * (2 ** attempt))
                    print(f"⏳ Rate limited (status {response.status_code}) on description. Retrying in {delay:.1f}s...")
                    import asyncio as _asyncio
                    await _asyncio.sleep(delay)
                    continue
                print(f"⚠️ Description endpoint returned status {response.status_code}: {response.text}")
                break
                
        except requests.exceptions.ConnectionError:
            print(f"❌ Connection failed to {base_url}")
            continue
        except requests.exceptions.Timeout:
            print(f"⏰ Timeout connecting to {base_url}")
            continue
        except Exception as e:
            print(f"❌ Error with {base_url}: {e}")
            continue
    
    raise Exception("All QuizService endpoints are unavailable")

@router.post("/generate-with-kana")
async def generate_quiz_with_kana(request: QuizGenerationRequest):
    """Generate a quiz using Kana AI based on assignment feedback."""
    try:
        print(f"🧠 Generating quiz for student {request.student_id}, assignment {request.assignment_id}")
        
        # Determine difficulty based on grade
        if request.grade < 60:
            difficulty = "easy"
            student_level = "beginner"
        elif request.grade < 80:
            difficulty = "medium"
            student_level = "intermediate"
        else:
            difficulty = "hard"
            student_level = "advanced"
        
        # Prepare prompt for Kana AI
        weakness_areas_text = ", ".join(request.weakness_areas) if request.weakness_areas else "general understanding"
        
        prompt = f"""
Create EXACTLY 5 unique multiple choice questions to help a student improve in their weak areas based on their assignment feedback.

Context:
- Subject: {request.subject}
- Student Level: {student_level}
- Difficulty: {difficulty}
- Weakness Areas: {weakness_areas_text}
- Assignment Feedback: {request.feedback}

CRITICAL REQUIREMENTS:
1. Generate EXACTLY 5 questions - no more, no less
2. Each question MUST be unique and different from others
3. Each question should target one of the weakness areas mentioned
4. Provide EXACTLY 4 multiple choice options (A, B, C, D) per question
5. Include clear explanations for the correct answers
6. Make questions educational and encouraging
7. Focus on concept understanding, not just memorization
8. Use the assignment feedback as context to understand what the student struggled with

Response Format - Return ONLY valid JSON in this exact structure:
[
  {{
    "question": "Question text here?",
    "options": ["Option A", "Option B", "Option C", "Option D"],
    "correctAnswer": 0,
    "explanation": "Why this answer is correct and how it helps with the weakness",
    "topic": "Main topic this question covers",
    "weakness_area": "Specific weakness area this addresses"
  }},
  {{
    "question": "Second unique question?",
    "options": ["Option A", "Option B", "Option C", "Option D"],
    "correctAnswer": 1,
    "explanation": "Explanation for second question",
    "topic": "Second topic",
    "weakness_area": "Second weakness area"
  }},
  {{
    "question": "Third unique question?",
    "options": ["Option A", "Option B", "Option C", "Option D"],
    "correctAnswer": 2,
    "explanation": "Explanation for third question",
    "topic": "Third topic", 
    "weakness_area": "Third weakness area"
  }},
  {{
    "question": "Fourth unique question?",
    "options": ["Option A", "Option B", "Option C", "Option D"],
    "correctAnswer": 3,
    "explanation": "Explanation for fourth question",
    "topic": "Fourth topic",
    "weakness_area": "Fourth weakness area"
  }},
  {{
    "question": "Fifth unique question?",
    "options": ["Option A", "Option B", "Option C", "Option D"],
    "correctAnswer": 0,
    "explanation": "Explanation for fifth question",
    "topic": "Fifth topic",
    "weakness_area": "Fifth weakness area"
  }}
]

Generate 5 high-quality, unique questions now:
"""

        # Always try to call Kana AI first - only fallback if absolutely necessary
        questions = []
        kana_error = None
        
        try:
            print("🤖 Calling Kana AI for quiz generation...")
            kana_response = await call_kana_ai(prompt)
            questions = parse_kana_response(kana_response, request, difficulty)
            
            if len(questions) < 5:
                print(f"⚠️ Kana returned {len(questions)} questions, need 5. Retrying...")
                # Try again with more specific prompt
                retry_prompt = prompt + f"\n\nIMPORTANT: The previous response only had {len(questions)} questions. Generate EXACTLY 5 complete questions."
                kana_response = await call_kana_ai(retry_prompt)
                questions = parse_kana_response(kana_response, request, difficulty)
                
        except Exception as e:
            kana_error = str(e)
            print(f"❌ Kana AI failed: {kana_error}")
            
        # Only use fallback if Kana completely failed or returned no questions
        if len(questions) == 0:
            print("🔄 Using fallback generation as Kana AI is unavailable")
            questions = generate_fallback_questions(request, difficulty)
        
        # Ensure we have exactly 5 questions
        if len(questions) < 5:
            print(f"⚠️ Only {len(questions)} questions available, padding with fallback")
            fallback_questions = generate_fallback_questions(request, difficulty)
            questions.extend(fallback_questions[:5-len(questions)])
        
        questions = questions[:5]  # Ensure exactly 5 questions
        
        # Create quiz object
        quiz_id = f"quiz_{request.assignment_id}_{request.student_id}_{int(datetime.now().timestamp())}"
        quiz = {
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
            "attempts": [],  # Initialize empty attempts array
            "generated_by": "kana_ai" if kana_error is None else "fallback",
            "kana_available": kana_error is None
        }
        
        # Save quiz
        generated_quizzes[quiz_id] = quiz
        
        print(f"✅ Quiz {quiz_id} generated successfully with {len(questions)} questions")
        if kana_error:
            print(f"⚠️ Note: Fallback used due to Kana error: {kana_error}")
        
        return quiz
        
    except Exception as e:
        print(f"❌ Failed to generate quiz: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate quiz: {str(e)}"
        )

async def call_kana_ai(prompt: str) -> str:
    """Call Kana AI service to generate quiz questions using the new QuizService."""
    try:
        # Try multiple Kana service URLs/ports with the new quiz generation endpoints
        kana_urls = [
            "https://kana-backend-app.onrender.com",
            # "http://localhost:10000",
        ]
        
        for base_url in kana_urls:
            try:
                print(f"🔗 Trying Kana AI QuizService at: {base_url}")
                
                # First try the new generate-improvement-quiz endpoint (most appropriate)
                improvement_url = f"{base_url}/api/kana/generate-improvement-quiz"
                
                # Extract request info from prompt for the improvement endpoint
                response = requests.post(
                    improvement_url,
                    json={
                        "assignment_id": "temp_assignment",
                        "student_id": "temp_student", 
                        "feedback": prompt,
                        "weakness_areas": ["general understanding", "problem solving"],
                        "subject": "General",
                        "grade": "intermediate",
                        "numQuestions": 5
                    },
                    timeout=30,
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("questions"):
                        print(f"✅ Successfully got quiz from Kana AI QuizService")
                        return json.dumps(data["questions"])
                else:
                    print(f"⚠️ Improvement endpoint returned status {response.status_code}")
                
                # Fallback to description-based generation
                description_url = f"{base_url}/api/kana/generate-quiz-by-description"
                response = requests.post(
                    description_url,
                    json={
                        "description": prompt,
                        "numQuestions": 5,
                        "difficulty": "medium",
                        "subject": "General",
                        "studentLevel": "intermediate"
                    },
                    timeout=30,
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("quiz", {}).get("questions"):
                        print(f"✅ Successfully got quiz from Kana AI description endpoint")
                        return json.dumps(data["quiz"]["questions"])
                else:
                    print(f"⚠️ Description endpoint returned status {response.status_code}")
                
                # Final fallback to chat endpoint
                chat_url = f"{base_url}/api/kana/chat"
                response = requests.post(
                    chat_url,
                    json={
                        "message": prompt,
                        "mode": "quiz_generation",
                        "type": "educational_quiz"
                    },
                    timeout=30,
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("quiz", {}).get("questions"):
                        print(f"✅ Successfully got quiz from Kana AI chat endpoint")
                        return json.dumps(data["quiz"]["questions"])
                    elif data.get("kanaResponse"):
                        print(f"✅ Successfully got response from Kana AI chat")
                        return data["kanaResponse"]
                else:
                    print(f"⚠️ Chat endpoint returned status {response.status_code}")
                    
            except requests.exceptions.ConnectionError:
                print(f"❌ Connection failed to {base_url}")
                continue
            except requests.exceptions.Timeout:
                print(f"⏰ Timeout connecting to {base_url}")
                continue
                
        raise Exception("All Kana AI service endpoints are unavailable")
            
    except Exception as e:
        raise Exception(f"Failed to call Kana AI: {e}")

def parse_kana_response(response: str, request: QuizGenerationRequest, difficulty: str) -> List[Dict]:
    """Parse Kana AI response into quiz questions - handles both new QuizService and legacy formats."""
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
        print(f"⚠️ Failed to parse Kana response: {e}")
        print(f"Response content: {response[:500]}...")  # Log first 500 chars for debugging
    
    # Return fallback if parsing fails
    print("🔄 Falling back to generated questions due to parsing failure")
    return generate_fallback_questions(request, difficulty)

def generate_fallback_questions(request: QuizGenerationRequest, difficulty: str) -> List[Dict]:
    """Generate diverse fallback questions when Kana AI is unavailable."""
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

@router.get("/health/kana-service")
async def check_kana_service_health():
    """Check the health and availability of Kana AI QuizService endpoints."""
    try:
        kana_urls = [
            "https://kana-backend-app.onrender.com",
            "http://localhost:10000",
        ]
        
        service_status = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "services": [],
            "overall_status": "unknown"
        }
        
        available_services = 0
        
        for base_url in kana_urls:
            service_info = {
                "url": base_url,
                "status": "down",
                "endpoints": {},
                "response_time_ms": None
            }
            
            try:
                start_time = datetime.now()
                
                # Test main service
                response = requests.get(f"{base_url}/", timeout=10)
                end_time = datetime.now()
                
                if response.status_code == 200:
                    service_info["status"] = "up"
                    service_info["response_time_ms"] = int((end_time - start_time).total_seconds() * 1000)
                    available_services += 1
                    
                    # Test specific QuizService endpoints
                    endpoints_to_test = [
                        "/api/kana/generate-quiz-by-description",
                        "/api/kana/generate-improvement-quiz",
                        "/api/kana/chat"
                    ]
                    
                    for endpoint in endpoints_to_test:
                        try:
                            test_response = requests.post(
                                f"{base_url}{endpoint}",
                                json={"test": "health_check"},
                                timeout=5
                            )
                            service_info["endpoints"][endpoint] = {
                                "status": "reachable" if test_response.status_code in [200, 400] else "error",
                                "status_code": test_response.status_code
                            }
                        except:
                            service_info["endpoints"][endpoint] = {
                                "status": "unreachable",
                                "status_code": None
                            }
                
            except Exception as e:
                service_info["error"] = str(e)
            
            service_status["services"].append(service_info)
        
        # Determine overall status
        if available_services > 0:
            service_status["overall_status"] = "healthy"
        else:
            service_status["overall_status"] = "unhealthy"
        
        service_status["available_services"] = available_services
        service_status["total_services"] = len(kana_urls)
        
        return service_status
        
    except Exception as e:
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "overall_status": "error",
            "error": str(e)
        }

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
