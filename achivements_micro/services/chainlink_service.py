# import asyncio
# import aiohttp
# import logging
# from typing import List, Dict, Optional, Any
# from sqlalchemy.orm import Session
# from models.tournament_models import TournamentQuestion
# from datetime import datetime
# import random
# from config import Config

# logger = logging.getLogger(__name__)

# class KanaAIQuestionService:
#     """Service to interface with Kana AI question generation API"""
    
#     def __init__(self, ai_api_url: Optional[str] = None):
#         # This will connect to your other repo's question generation endpoint
#         self.ai_api_url = ai_api_url or Config.KANA_AI_API_URL
#         self.fallback_questions = self._load_fallback_questions()
    
#     async def generate_dynamic_quiz(self, topic: str, difficulty: str = "medium", question_count: int = 1) -> Dict[str, Any]:
#         """
#         Generate quiz using Kana AI - compatible with your React component's expected format
        
#         Args:
#             topic: Subject topic (e.g., 'mathematics', 'physics', 'computer-science')
#             difficulty: Difficulty level ('easy', 'medium', 'hard')
#             question_count: Number of questions to generate
            
#         Returns:
#             Dict with success, question, options, correctAnswer, xpReward, generatedAt, source
#         """
#         try:
#             async with aiohttp.ClientSession() as session:
#                 payload = {
#                     "topic": topic,
#                     "difficulty": difficulty,
#                     "questionCount": question_count,
#                     "format": "multiple_choice"
#                 }
                
#                 async with session.post(
#                     self.ai_api_url,
#                     json=payload,
#                     timeout=aiohttp.ClientTimeout(total=30)
#                 ) as response:
                    
#                     if response.status == 200:
#                         data = await response.json()
                        
#                         # Format response to match your React component expectations
#                         if question_count == 1:
#                             # Single question format (for daily challenges)
#                             question_data = data.get('questions', [{}])[0] if data.get('questions') else data
#                             return {
#                                 "success": True,
#                                 "question": question_data.get('question', ''),
#                                 "options": question_data.get('options', []),
#                                 "correctAnswer": question_data.get('correctAnswer', 0),
#                                 "xpReward": self._calculate_xp_reward(difficulty),
#                                 "generatedAt": datetime.utcnow().isoformat(),
#                                 "source": "Kana AI",
#                                 "topic": topic,
#                                 "difficulty": difficulty
#                             }
#                         else:
#                             # Multiple questions format (for tournaments)
#                             return {
#                                 "success": True,
#                                 "questions": data.get('questions', []),
#                                 "generatedAt": datetime.utcnow().isoformat(),
#                                 "source": "Kana AI",
#                                 "topic": topic,
#                                 "difficulty": difficulty
#                             }
#                     else:
#                         logger.warning(f"AI API returned status {response.status}")
#                         return await self._get_fallback_response(topic, difficulty, question_count)
                        
#         except Exception as e:
#             logger.error(f"Error calling Kana AI API: {e}")
#             return await self._get_fallback_response(topic, difficulty, question_count)
    
#     async def generate_tournament_questions(
#         self,
#         db: Session,
#         tournament_id: int,
#         topics: List[str],
#         difficulty_level: str,
#         question_count: int,
#         subject_category: Optional[str] = None,
#         time_limit_minutes: int = 60
#     ) -> List[TournamentQuestion]:
#         """Generate questions for tournament using Kana AI"""
        
#         generated_questions = []
#         questions_per_topic = max(1, question_count // len(topics))
        
#         for topic in topics:
#             try:
#                 # Generate questions for this topic
#                 response = await self.generate_dynamic_quiz(
#                     topic=topic,
#                     difficulty=difficulty_level,
#                     question_count=questions_per_topic
#                 )
                
#                 if response.get("success") and response.get("questions"):
#                     for q_data in response["questions"]:
#                         question = TournamentQuestion(
#                             tournament_id=tournament_id,
#                             question_text=q_data.get("question", ""),
#                             option_a=q_data.get("options", ["", "", "", ""])[0],
#                             option_b=q_data.get("options", ["", "", "", ""])[1],
#                             option_c=q_data.get("options", ["", "", "", ""])[2],
#                             option_d=q_data.get("options", ["", "", "", ""])[3],
#                             correct_answer=chr(65 + q_data.get("correctAnswer", 0)),  # Convert 0,1,2,3 to A,B,C,D
#                             difficulty_level=difficulty_level,
#                             topic=topic,
#                             time_limit_seconds=time_limit_minutes * 60,
#                             points_value=self._calculate_points(difficulty_level),
#                             explanation=q_data.get("explanation", ""),
#                             source="Kana AI"
#                         )
#                         generated_questions.append(question)
#                         db.add(question)
                
#             except Exception as e:
#                 logger.error(f"Failed to generate questions for topic {topic}: {e}")
#                 # Add fallback questions for this topic
#                 fallback_questions = self.create_fallback_questions(
#                     db, tournament_id, questions_per_topic, [topic], difficulty_level
#                 )
#                 generated_questions.extend(fallback_questions)
        
#         # If we didn't get enough questions, fill with random topics
#         if len(generated_questions) < question_count:
#             remaining = question_count - len(generated_questions)
#             random_topics = self._get_random_topics(remaining)
            
#             for topic in random_topics:
#                 try:
#                     response = await self.generate_dynamic_quiz(topic, difficulty_level, 1)
#                     if response.get("success"):
#                         question = TournamentQuestion(
#                             tournament_id=tournament_id,
#                             question_text=response.get("question", ""),
#                             option_a=response.get("options", ["", "", "", ""])[0],
#                             option_b=response.get("options", ["", "", "", ""])[1],
#                             option_c=response.get("options", ["", "", "", ""])[2],
#                             option_d=response.get("options", ["", "", "", ""])[3],
#                             correct_answer=chr(65 + response.get("correctAnswer", 0)),
#                             difficulty_level=difficulty_level,
#                             topic=topic,
#                             time_limit_seconds=time_limit_minutes * 60,
#                             points_value=self._calculate_points(difficulty_level),
#                             source="Kana AI"
#                         )
#                         generated_questions.append(question)
#                         db.add(question)
#                 except Exception as e:
#                     logger.error(f"Failed to generate additional question for {topic}: {e}")
        
#         try:
#             db.commit()
#             logger.info(f"Successfully saved {len(generated_questions)} AI-generated questions for tournament {tournament_id}")
#         except Exception as e:
#             db.rollback()
#             logger.error(f"Failed to save questions to database: {e}")
        
#         return generated_questions
    
#     def create_fallback_questions(
#         self,
#         db: Session,
#         tournament_id: int,
#         question_count: int,
#         topics: List[str],
#         difficulty_level: str
#     ) -> List[TournamentQuestion]:
#         """Create fallback questions when AI generation fails"""
        
#         questions = []
#         for i in range(question_count):
#             topic = topics[i % len(topics)] if topics else "general_knowledge"
#             fallback_q = random.choice(self.fallback_questions.get(topic, self.fallback_questions["general_knowledge"]))
            
#             question = TournamentQuestion(
#                 tournament_id=tournament_id,
#                 question_text=fallback_q["question"],
#                 option_a=fallback_q["options"][0],
#                 option_b=fallback_q["options"][1],
#                 option_c=fallback_q["options"][2],
#                 option_d=fallback_q["options"][3],
#                 correct_answer=chr(65 + fallback_q["correctAnswer"]),
#                 difficulty_level=difficulty_level,
#                 topic=topic,
#                 time_limit_seconds=60,
#                 points_value=self._calculate_points(difficulty_level),
#                 source="Fallback"
#             )
#             questions.append(question)
#             db.add(question)
        
#         return questions
    
#     async def _get_fallback_response(self, topic: str, difficulty: str, question_count: int) -> Dict[str, Any]:
#         """Get fallback response when AI API fails"""
#         if question_count == 1:
#             fallback_q = random.choice(self.fallback_questions.get(topic, self.fallback_questions["general_knowledge"]))
#             return {
#                 "success": True,
#                 "question": fallback_q["question"],
#                 "options": fallback_q["options"],
#                 "correctAnswer": fallback_q["correctAnswer"],
#                 "xpReward": self._calculate_xp_reward(difficulty),
#                 "generatedAt": datetime.utcnow().isoformat(),
#                 "source": "Fallback",
#                 "topic": topic,
#                 "difficulty": difficulty
#             }
#         else:
#             questions = []
#             for _ in range(question_count):
#                 fallback_q = random.choice(self.fallback_questions.get(topic, self.fallback_questions["general_knowledge"]))
#                 questions.append(fallback_q)
            
#             return {
#                 "success": True,
#                 "questions": questions,
#                 "generatedAt": datetime.utcnow().isoformat(),
#                 "source": "Fallback",
#                 "topic": topic,
#                 "difficulty": difficulty
#             }
    
#     def _calculate_xp_reward(self, difficulty: str) -> int:
#         """Calculate XP reward based on difficulty"""
#         xp_map = {
#             "easy": 25,
#             "medium": 50,
#             "hard": 75,
#             "elementary": 20,
#             "middle_school": 35,
#             "high_school": 50,
#             "university": 65,
#             "professional": 80
#         }
#         return xp_map.get(difficulty.lower(), 50)
    
#     def _calculate_points(self, difficulty: str) -> int:
#         """Calculate tournament points based on difficulty"""
#         points_map = {
#             "easy": 10,
#             "medium": 15,
#             "hard": 20,
#             "elementary": 8,
#             "middle_school": 12,
#             "high_school": 15,
#             "university": 18,
#             "professional": 25
#         }
#         return points_map.get(difficulty.lower(), 15)
    
#     def _get_random_topics(self, count: int) -> List[str]:
#         """Get random topics for question generation"""
#         topics = [
#             'mathematics', 'physics', 'chemistry', 'biology', 'history', 'geography',
#             'literature', 'computer-science', 'psychology', 'economics', 'astronomy',
#             'art-history', 'philosophy', 'environmental-science', 'anatomy', 'genetics',
#             'world-languages', 'music-theory', 'engineering', 'archaeology', 'neuroscience',
#             'statistics', 'geology', 'political-science', 'sociology'
#         ]
#         return random.sample(topics, min(count, len(topics)))
    
#     def _load_fallback_questions(self) -> Dict[str, List[Dict]]:
#         """Load fallback questions for when AI generation fails"""
#         return {
#             "general_knowledge": [
#                 {
#                     "question": "What is the capital of France?",
#                     "options": ["London", "Paris", "Berlin", "Madrid"],
#                     "correctAnswer": 1
#                 },
#                 {
#                     "question": "Which planet is closest to the Sun?",
#                     "options": ["Venus", "Earth", "Mercury", "Mars"],
#                     "correctAnswer": 2
#                 }
#             ],
#             "mathematics": [
#                 {
#                     "question": "What is 7 × 8?",
#                     "options": ["54", "56", "58", "64"],
#                     "correctAnswer": 1
#                 },
#                 {
#                     "question": "What is the square root of 64?",
#                     "options": ["6", "7", "8", "9"],
#                     "correctAnswer": 2
#                 }
#             ],
#             "physics": [
#                 {
#                     "question": "What is the speed of light in vacuum?",
#                     "options": ["299,792,458 m/s", "300,000,000 m/s", "299,000,000 m/s", "298,792,458 m/s"],
#                     "correctAnswer": 0
#                 }
#             ]
#         }


# # For backward compatibility, keep the old name as an alias
# ChainlinkQuestionService = KanaAIQuestionService