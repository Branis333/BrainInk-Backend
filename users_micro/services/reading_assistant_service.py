import os
import json
import asyncio
import tempfile
import wave
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
import re
import google.generativeai as genai
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

# Optional audio processing imports
try:
    import librosa
    import numpy as np
    AUDIO_PROCESSING_AVAILABLE = True
except ImportError:
    AUDIO_PROCESSING_AVAILABLE = False
    print("⚠️ Audio processing libraries not available. Install librosa and numpy for advanced audio analysis.")

from services.gemini_service import gemini_service
from models.reading_assistant_models import (
    ReadingContent, ReadingSession, ReadingAttempt, 
    WordFeedback, ReadingFeedback, ReadingProgress,
    ReadingLevel, DifficultyLevel
)
from schemas.reading_assistant_schemas import (
    ReadingAttemptResult, WordAnalysis, PronunciationAnalysis,
    FluentReadingAnalysis
)

class ReadingAssistantService:
    """
    AI-powered reading assistant service that analyzes speech,
    provides pronunciation feedback, and tracks learning progress
    """
    
    def __init__(self):
        self.gemini_service = gemini_service
        
    # ===============================
    # CONTENT GENERATION & MANAGEMENT
    # ===============================
    
    async def generate_reading_content(
        self,
        reading_level: ReadingLevel,
        difficulty_level: DifficultyLevel,
        content_type: str,
        topic: Optional[str] = None,
        vocabulary_focus: Optional[List[str]] = None,
        phonics_patterns: Optional[List[str]] = None,
        word_count_target: Optional[int] = None
    ) -> Dict[str, Any]:
        """Generate age-appropriate reading content using AI"""
        
        # Determine appropriate parameters based on reading level
        level_config = self._get_level_configuration(reading_level, difficulty_level)
        
        if not word_count_target:
            word_count_target = level_config["default_word_count"]
        
        content_prompt = f"""
        Create engaging reading content for early readers.
        
        TARGET AUDIENCE:
        - Reading Level: {reading_level.value.replace('_', ' ').title()}
        - Difficulty: {difficulty_level.value}
        - Age Range: {level_config['age_range']}
        
        CONTENT SPECIFICATIONS:
        - Type: {content_type}
        - Topic: {topic or 'age-appropriate general topic'}
        - Target Word Count: {word_count_target}
        - Vocabulary Focus: {vocabulary_focus or ['basic sight words']}
        - Phonics Patterns: {phonics_patterns or level_config['default_phonics']}
        
        REQUIREMENTS:
        1. Use simple, clear sentences appropriate for the reading level
        2. Include repetitive patterns to build confidence
        3. Focus on high-frequency sight words
        4. Incorporate the specified phonics patterns naturally
        5. Make content engaging and relatable to young children
        6. Ensure proper punctuation for reading practice
        
        READING LEVEL GUIDELINES:
        - Kindergarten: 3-10 words per sentence, simple CVC words, basic sight words
        - Grade 1: 5-15 words per sentence, simple compound words, common phonics patterns
        - Grade 2: 10-20 words per sentence, more complex vocabulary, longer stories
        - Grade 3: 15-25 words per sentence, chapter-like content, varied sentence structures
        
        Generate content in JSON format:
        {{
            "title": "Engaging title for the content",
            "content": "The actual text content for reading",
            "vocabulary_words": {{
                "word1": "simple definition",
                "word2": "simple definition"
            }},
            "learning_objectives": [
                "Students will practice reading CVC words",
                "Students will recognize sight words"
            ],
            "phonics_focus": ["short vowels", "consonant blends"],
            "complexity_analysis": {{
                "sentence_count": 5,
                "average_sentence_length": 8,
                "vocabulary_level": "kindergarten",
                "estimated_reading_time": 60
            }},
            "engagement_features": [
                "Repetitive patterns",
                "Relatable characters",
                "Simple plot progression"
            ]
        }}
        """
        
        try:
            # Use the real Gemini AI service for content generation
            result = await self.gemini_service.generate_reading_content_ai(
                reading_level=reading_level.value,
                difficulty_level=difficulty_level.value,
                content_type=content_type,
                topic=topic,
                word_count=word_count_target,
                phonics_focus=phonics_patterns
            )
            
            # Add complexity analysis
            result['complexity_analysis'] = {
                'sentence_count': len(result['content'].split('.')),
                'average_sentence_length': len(result['content'].split()) // max(len(result['content'].split('.')), 1),
                'vocabulary_level': reading_level.value.lower(),
                'estimated_reading_time': result.get('estimated_reading_time', word_count_target * 2)
            }
            
            return result
            
        except Exception as e:
            print(f"❌ AI content generation failed: {e}")
            # Fallback content generation
            return self._generate_fallback_content(reading_level, difficulty_level, content_type)
    
    def _get_level_configuration(self, reading_level: ReadingLevel, difficulty: DifficultyLevel) -> Dict[str, Any]:
        """Get configuration parameters for different reading levels"""
        
        base_config = {
            ReadingLevel.KINDERGARTEN: {
                "age_range": "4-5 years",
                "default_word_count": 15,
                "default_phonics": ["short vowels", "simple consonants"],
                "max_sentence_length": 10,
                "vocabulary_complexity": "basic"
            },
            ReadingLevel.GRADE_1: {
                "age_range": "5-6 years", 
                "default_word_count": 25,
                "default_phonics": ["consonant blends", "digraphs", "long vowels"],
                "max_sentence_length": 15,
                "vocabulary_complexity": "elementary"
            },
            ReadingLevel.GRADE_2: {
                "age_range": "6-7 years",
                "default_word_count": 40,
                "default_phonics": ["r-controlled vowels", "vowel teams", "silent letters"],
                "max_sentence_length": 20,
                "vocabulary_complexity": "intermediate"
            },
            ReadingLevel.GRADE_3: {
                "age_range": "7-8 years",
                "default_word_count": 60,
                "default_phonics": ["multisyllabic words", "prefixes", "suffixes"],
                "max_sentence_length": 25,
                "vocabulary_complexity": "advanced elementary"
            }
        }
        
        config = base_config[reading_level].copy()
        
        # Adjust based on difficulty level
        if difficulty == DifficultyLevel.ELEMENTARY:
            config["default_word_count"] = int(config["default_word_count"] * 0.7)
        elif difficulty == DifficultyLevel.ADVANCED:
            config["default_word_count"] = int(config["default_word_count"] * 1.3)
            
        return config
    
    def _generate_fallback_content(self, reading_level: ReadingLevel, difficulty: DifficultyLevel, content_type: str) -> Dict[str, Any]:
        """Generate simple fallback content if AI generation fails"""
        
        fallback_content = {
            ReadingLevel.KINDERGARTEN: {
                "sentence": "The cat sat on the mat. It is a big cat. The cat likes to play.",
                "story": "Sam has a dog. The dog is brown. Sam and the dog play in the park. They run and jump. It is fun to play with the dog."
            },
            ReadingLevel.GRADE_1: {
                "sentence": "My friend likes to read books about animals in the forest.",
                "story": "Emma found a special book in the library. The book had pictures of magical animals. She read about a brave rabbit who helped other forest friends. Emma loved the story so much that she read it three times."
            }
        }
        
        content = fallback_content.get(reading_level, {}).get(content_type, "The sun is bright today.")
        
        return {
            "title": f"Reading Practice: {content_type.title()}",
            "content": content,
            "vocabulary_words": {"the": "a word that comes before nouns", "cat": "a furry pet animal"},
            "learning_objectives": ["Practice reading simple words", "Improve reading fluency"],
            "phonics_focus": ["short vowels", "simple consonants"],
            "complexity_analysis": {
                "sentence_count": len(content.split('.')),
                "average_sentence_length": len(content.split()) // max(len(content.split('.')), 1),
                "vocabulary_level": reading_level.value,
                "estimated_reading_time": len(content.split()) * 2  # 2 seconds per word for beginners
            }
        }
    
    # ===============================
    # AUDIO PROCESSING & SPEECH ANALYSIS
    # ===============================
    
    async def process_reading_audio(
        self,
        audio_file_path: str,
        target_text: str,
        reading_level: ReadingLevel,
        session_id: int,
        db: Session
    ) -> ReadingAttemptResult:
        """
        Process uploaded audio file and analyze reading performance
        """
        
        try:
            print(f"🎤 DEBUG: Processing audio file: {audio_file_path}")
            print(f"🎯 DEBUG: Target text: '{target_text}'")
            
            # Step 1: Transcribe audio using Gemini's speech capabilities
            try:
                transcribed_text = await self._transcribe_audio_with_gemini(audio_file_path)
                print(f"✅ Transcription successful: '{transcribed_text}'")
                transcription_successful = True
            except Exception as e:
                print(f"❌ Transcription failed: {e}")
                transcribed_text = "Transcription not available - please try again"
                transcription_successful = False
            
            # Step 2: Only do analysis if transcription was successful
            if transcription_successful:
                print(f"🔍 DEBUG: Running AI analysis...")
                analysis_result = await self._analyze_reading_performance(
                    target_text=target_text,
                    transcribed_text=transcribed_text,
                    reading_level=reading_level,
                    audio_file_path=audio_file_path
                )
                print(f"✅ AI analysis completed")
            else:
                print(f"⚠️ Skipping AI analysis due to transcription failure")
                # Generate neutral analysis when transcription fails
                analysis_result = self._generate_neutral_analysis(target_text)
            
            # Step 3: Generate personalized feedback
            feedback = await self._generate_reading_feedback(
                analysis_result, target_text, reading_level
            )
            
            # Convert word accuracy dictionaries to WordAnalysis objects
            from schemas.reading_assistant_schemas import WordAnalysis
            
            word_accuracy_objects = []
            for word_dict in analysis_result["word_accuracy"]:
                word_accuracy_objects.append(WordAnalysis(
                    target_word=word_dict["target_word"],
                    spoken_word=word_dict["spoken_word"],
                    word_position=word_dict["word_position"],
                    is_correct=word_dict["is_correct"],
                    pronunciation_accuracy=word_dict["pronunciation_accuracy"],
                    phonetic_errors=word_dict.get("phonetic_errors", []),
                    pronunciation_tip=word_dict.get("pronunciation_tip", "")
                ))
            
            return ReadingAttemptResult(
                transcribed_text=transcribed_text,
                word_accuracy=word_accuracy_objects,
                pronunciation_errors=analysis_result["pronunciation_errors"],
                reading_speed=analysis_result["reading_speed"],
                pauses_analysis=analysis_result["pauses_analysis"],
                accuracy_percentage=analysis_result["accuracy_percentage"],
                fluency_score=analysis_result["fluency_score"],
                pronunciation_score=analysis_result["pronunciation_score"]
            )
            
        except Exception as e:
            raise Exception(f"Error processing reading audio: {str(e)}")
    
    async def _transcribe_audio_with_gemini(self, audio_file_path: str) -> str:
        """Use Gemini to transcribe audio file"""
        
        try:
            print(f"🎤 DEBUG: Starting transcription for: {audio_file_path}")
            
            # Check if file exists and has content
            if not os.path.exists(audio_file_path):
                print(f"❌ Audio file not found: {audio_file_path}")
                raise Exception("Audio file not found")
            
            file_size = os.path.getsize(audio_file_path)
            if file_size == 0:
                print(f"❌ Empty audio file: {audio_file_path}")
                raise Exception("Empty audio file")
            
            print(f"📄 Audio file size: {file_size} bytes")
            
            # Upload audio file to Gemini
            print("🔄 Uploading to Gemini...")
            uploaded_file = genai.upload_file(path=audio_file_path, display_name="reading_audio")
            print(f"✅ File uploaded to Gemini: {uploaded_file.name}")
            
            # Wait for processing with timeout
            import time
            max_wait_time = 30  # 30 seconds timeout
            start_time = time.time()
            
            while uploaded_file.state.name == "PROCESSING":
                if time.time() - start_time > max_wait_time:
                    print("❌ Gemini processing timeout")
                    raise Exception("Gemini processing timeout")
                time.sleep(2)
                uploaded_file = genai.get_file(uploaded_file.name)
                print(f"🔄 Gemini processing status: {uploaded_file.state.name}")
            
            if uploaded_file.state.name == "FAILED":
                print("❌ Gemini processing failed")
                raise Exception("Gemini audio processing failed")
            
            # Generate transcription with STRICT PHONETIC instructions
            transcription_prompt = """
            CRITICAL INSTRUCTIONS FOR TRANSCRIBING CHILD READING:
            
            You are transcribing audio of a young student learning to read.
            This is for PRONUNCIATION ASSESSMENT - phonetic accuracy is ESSENTIAL.
            
            STRICT PHONETIC TRANSCRIPTION RULES:
            
            1. LISTEN TO ACTUAL SOUNDS - Write what you HEAR, not what you think they meant
            2. CAPTURE MISPRONUNCIATIONS - If pronunciation is wrong, transcribe the wrong pronunciation
            3. DO NOT AUTO-CORRECT - Do not fix words to their "correct" spelling
            4. PHONETIC ERRORS MATTER - These examples show what we need:
            
            PHONETIC EXAMPLES (READ CAREFULLY):
            
            Example 1 - Vowel Sound Errors:
            - Text says "leaf" (pronounced "leef")
            - Child says "leh-aff" (wrong vowel sound)
            - You write: "leff" or "laff" (NOT "leaf")
            
            Example 2 - Consonant Blend Errors:
            - Text says "through" (pronounced "throo")  
            - Child says "troo" (missing 'th' sound)
            - You write: "troo" or "trew" (NOT "through")
            
            Example 3 - Long vs Short Vowels:
            - Text says "see" (long e sound)
            - Child says "seh" (short e sound)
            - You write: "seh" (NOT "see")
            
            Example 4 - Missing Sounds:
            - Text says "slide"
            - Child says "slide" but drops the 'd' → "sly"
            - You write: "sly" (NOT "slide")
            
            Example 5 - Added Sounds:
            - Text says "run"
            - Child adds extra sound → "runnin"
            - You write: "runnin" (NOT "run")
            
            MORE RULES:
            5. If child skips a word entirely, don't add it
            6. If child repeats or stutters, include it once
            7. If pronunciation is slightly off but recognizable, write phonetically what you heard
            8. DO NOT fix grammar (write "I seen" not "I saw", write "he go" not "he goes")
            
            REMEMBER: This is pronunciation assessment. We NEED to know when sounds are wrong.
            If the child mispronounces "leaf" as "leff", we must catch that error.
            DO NOT help the student by correcting their pronunciation in the transcription.
            
            YOUR TASK:
            Listen carefully to each word's ACTUAL PRONUNCIATION.
            Transcribe what was SAID, not what should have been said.
            Write phonetically if needed to capture mispronunciation.
            
            Return ONLY the transcribed text, nothing else.
            If audio is completely unclear, return: "TRANSCRIPTION_FAILED"
            """
            
            print("🤖 Requesting transcription from Gemini...")
            
            try:
                response = await asyncio.to_thread(
                    self.gemini_service.config.model.generate_content,
                    [uploaded_file, transcription_prompt],
                    generation_config=genai.types.GenerationConfig(
                        temperature=0.0,  # Maximum literal transcription
                        max_output_tokens=512
                    )
                )
                
                transcribed_text = response.text.strip()
                
            except Exception as e:
                if "finish_reason" in str(e) and "2" in str(e):
                    # Safety filter blocked - try with minimal prompt
                    print(f"⚠️ Detailed prompt blocked by safety filter. Retrying with simple prompt...")
                    
                    simple_prompt = """
                    Transcribe this audio of a child reading aloud.
                    Write exactly what you hear, including any mispronunciations.
                    Do not correct errors. This is for educational assessment.
                    Return only the transcribed text.
                    """
                    
                    response = await asyncio.to_thread(
                        self.gemini_service.config.model.generate_content,
                        [uploaded_file, simple_prompt],
                        generation_config=genai.types.GenerationConfig(
                            temperature=0.0,
                            max_output_tokens=512
                        )
                    )
                    transcribed_text = response.text.strip()
                else:
                    raise e
            
            print(f"🎯 Gemini transcription result: '{transcribed_text}'")
            
            # Cleanup uploaded file
            try:
                genai.delete_file(uploaded_file.name)
                print("🧹 Cleaned up Gemini file")
            except:
                pass
            
            # Check if transcription actually worked
            if transcribed_text == "TRANSCRIPTION_FAILED" or len(transcribed_text) < 2:
                print("❌ Transcription failed or empty")
                raise Exception("Transcription failed")
            
            return transcribed_text
            
        except Exception as e:
            print(f"❌ Critical error in transcription: {e}")
            raise Exception(f"Audio transcription failed: {str(e)}")
    
    def _generate_neutral_analysis(self, target_text: str) -> Dict[str, Any]:
        """Generate neutral analysis when transcription fails"""
        
        target_words = target_text.lower().split()
        word_accuracy = []
        
        for i, word in enumerate(target_words):
            # Clean punctuation from word
            clean_word = word.strip('.,!?;:')
            word_accuracy.append({
                "target_word": clean_word,
                "spoken_word": "analysis_not_available",
                "is_correct": False,  # Set to False since no analysis available
                "pronunciation_accuracy": 50,  # Neutral score
                "word_position": i + 1,
                "phonetic_errors": [],
                "pronunciation_tip": ""
            })
        
        return {
            "word_accuracy": word_accuracy,
            "pronunciation_errors": [],
            "reading_speed": 32.0,  # Default reading speed
            "pauses_analysis": {"total_pauses": 0, "fluency_impact": "unknown"},
            "accuracy_percentage": 0.0,  # 0% since no real analysis
            "fluency_score": 60.0,  # Default neutral score
            "pronunciation_score": 0.0,  # 0% since no real analysis
            "overall_assessment": {
                "strengths": ["Audio recording completed"],
                "areas_for_improvement": ["Try recording again in a quiet environment"],
                "specific_recommendations": ["Ensure microphone is working", "Speak clearly and loudly"]
            }
        }

    async def _analyze_reading_performance(
        self,
        target_text: str,
        transcribed_text: str,
        reading_level: ReadingLevel,
        audio_file_path: str
    ) -> Dict[str, Any]:
        """Analyze reading performance using AI"""
        
        analysis_prompt = f"""
        Analyze this child's reading performance for educational assessment.
        
        TARGET TEXT (what they should read):
        "{target_text}"
        
        ACTUAL TRANSCRIPTION (what they said):
        "{transcribed_text}"
        
        READING LEVEL: {reading_level.value}
        
        Please provide a detailed analysis in JSON format:
        {{
            "word_accuracy": [
                {{
                    "target_word": "word1",
                    "spoken_word": "what_they_said",
                    "is_correct": true,
                    "pronunciation_accuracy": 95.0,
                    "phonetic_errors": ["specific sound issues"],
                    "word_position": 1
                }}
            ],
            "pronunciation_errors": [
                {{
                    "word": "difficult_word",
                    "error_type": "vowel_substitution",
                    "correction": "proper pronunciation guide",
                    "practice_tip": "specific advice for improvement"
                }}
            ],
            "reading_speed": 45.0,
            "pauses_analysis": {{
                "total_pauses": 3,
                "long_pauses": 1,
                "pause_locations": ["after word 5", "before word 12"],
                "fluency_impact": "moderate"
            }},
            "accuracy_percentage": 85.5,
            "fluency_score": 78.0,
            "pronunciation_score": 82.0,
            "overall_assessment": {{
                "strengths": ["good phonetic awareness", "clear consonants"],
                "areas_for_improvement": ["vowel sounds", "reading pace"],
                "specific_recommendations": ["practice short vowel sounds", "use finger tracking"]
            }}
        }}
        
        Focus on:
        1. Word-by-word accuracy comparison
        2. Pronunciation quality for age level
        3. Reading fluency and pace
        4. Specific phonetic challenges
        5. Constructive, encouraging feedback
        """
        
        try:
            # Use the real Gemini AI service for speech performance analysis
            print(f"🤖 DEBUG: Calling Gemini with target='{target_text}', transcribed='{transcribed_text}'")
            analysis_result = await self.gemini_service.analyze_speech_performance(
                expected_text=target_text,
                transcribed_text=transcribed_text,
                reading_level=reading_level.value
            )
            print(f"🤖 DEBUG: Gemini returned accuracy_score: {analysis_result.get('accuracy_score', 'MISSING')}")
            
            # Convert to expected format for the reading assistant
            word_feedback = analysis_result.get("word_feedback", [])
            print(f"🤖 DEBUG: Word feedback count: {len(word_feedback)}")
            word_accuracy = []
            
            for i, word_data in enumerate(word_feedback):
                expected = word_data.get("expected", word_data.get("word", ""))
                said = word_data.get("said", word_data.get("word", ""))
                feedback = word_data.get("feedback", "")
                
                # Make pronunciation tip more helpful - show what they should say
                pronunciation_tip = feedback
                if expected and said and expected != said:
                    # Add clear "should say" instruction
                    pronunciation_tip = f"🎯 You should say '{expected}' (you said '{said}'). {feedback}"
                elif expected and not said:
                    pronunciation_tip = f"⚠️ Missing word: You should say '{expected}'. {feedback}"
                elif expected == said:
                    pronunciation_tip = f"✅ Perfect! You said '{expected}' correctly."
                
                word_accuracy.append({
                    "target_word": expected,
                    "spoken_word": said,
                    "word_position": i + 1,
                    "is_correct": word_data.get("pronunciation_score", 0.0) >= 0.8,
                    "pronunciation_accuracy": word_data.get("pronunciation_score", 0.0) * 100,
                    "phonetic_errors": word_data.get("sound_errors", []),
                    "pronunciation_tip": pronunciation_tip
                })
            
            final_accuracy = analysis_result.get("accuracy_score", 0.8) * 100
            print(f"🎯 DEBUG: Final accuracy being returned: {final_accuracy}%")
            
            return {
                "word_accuracy": word_accuracy,
                "pronunciation_errors": [
                    {
                        "word": w["word"],
                        "error_type": "pronunciation", 
                        "correction": w["feedback"],
                        "practice_tip": w["feedback"]
                    }
                    for w in word_feedback
                    if w.get("pronunciation_score", 1.0) < 0.8
                ],
                "reading_speed": 60.0,  # Default estimate
                "pauses_analysis": {"total_pauses": 0, "long_pauses": 0, "pause_locations": [], "fluency_impact": "minimal"},
                "accuracy_percentage": final_accuracy,
                "fluency_score": final_accuracy,
                "pronunciation_score": final_accuracy,
                "overall_assessment": {
                    "strengths": ["Reading attempt completed"],
                    "areas_for_improvement": analysis_result.get("suggestions", []),
                    "specific_recommendations": analysis_result.get("suggestions", [])
                }
            }
            
        except Exception as e:
            # Fallback analysis
            print(f"❌ DEBUG: AI analysis failed, using fallback. Error: {e}")
            return self._generate_fallback_analysis(target_text, transcribed_text)
    
    def _generate_fallback_analysis(self, target_text: str, transcribed_text: str) -> Dict[str, Any]:
        """Generate basic analysis if AI analysis fails"""
        
        print(f"⚠️ DEBUG: Using fallback analysis - Target: '{target_text}', Transcribed: '{transcribed_text}'")
        target_words = target_text.lower().split()
        transcribed_words = transcribed_text.lower().split()
        
        # Simple word-by-word comparison
        word_accuracy = []
        correct_words = 0
        
        for i, target_word in enumerate(target_words):
            spoken_word = transcribed_words[i] if i < len(transcribed_words) else ""
            is_correct = target_word == spoken_word
            if is_correct:
                correct_words += 1
            
            word_accuracy.append({
                "target_word": target_word,
                "spoken_word": spoken_word,
                "is_correct": is_correct,
                "pronunciation_accuracy": 100.0 if is_correct else 50.0,
                "word_position": i + 1
            })
        
        accuracy_percentage = (correct_words / len(target_words)) * 100 if target_words else 0
        
        return {
            "word_accuracy": word_accuracy,
            "pronunciation_errors": [],
            "reading_speed": len(target_words) * 2,  # Estimate 2 seconds per word
            "pauses_analysis": {"total_pauses": 0, "fluency_impact": "unknown"},
            "accuracy_percentage": accuracy_percentage,
            "fluency_score": max(60.0, accuracy_percentage * 0.8),
            "pronunciation_score": accuracy_percentage,
            "overall_assessment": {
                "strengths": ["completed the reading"],
                "areas_for_improvement": ["continue practicing"],
                "specific_recommendations": ["read aloud daily", "practice sight words"]
            }
        }
    
    async def _generate_reading_feedback(
        self,
        analysis_result: Dict[str, Any],
        target_text: str,
        reading_level: ReadingLevel
    ) -> str:
        """Generate encouraging, personalized feedback for the student"""
        
        feedback_prompt = f"""
        Generate encouraging, age-appropriate feedback for a {reading_level.value} student based on their reading performance.
        
        PERFORMANCE ANALYSIS:
        - Accuracy: {analysis_result.get('accuracy_percentage', 0)}%
        - Fluency Score: {analysis_result.get('fluency_score', 0)}
        - Pronunciation Score: {analysis_result.get('pronunciation_score', 0)}
        
        STRENGTHS: {analysis_result.get('overall_assessment', {}).get('strengths', [])}
        AREAS FOR IMPROVEMENT: {analysis_result.get('overall_assessment', {}).get('areas_for_improvement', [])}
        
        Create a warm, encouraging message that:
        1. Celebrates what they did well
        2. Gently addresses areas for improvement
        3. Provides specific, actionable suggestions
        4. Uses language appropriate for young children
        5. Maintains a positive, supportive tone
        
        Keep the message between 2-4 sentences and focus on growth mindset.
        """
        
        try:
            response = await asyncio.to_thread(
                self.gemini_service.config.model.generate_content,
                feedback_prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.7,
                    max_output_tokens=256
                )
            )
            
            return response.text.strip()
            
        except Exception as e:
            # Fallback feedback
            accuracy = analysis_result.get('accuracy_percentage', 0)
            if accuracy >= 80:
                return "Great job reading! You did really well with most of the words. Keep practicing to make your reading even smoother!"
            elif accuracy >= 60:
                return "Nice work! You're getting better at reading. Try to slow down a little and sound out each word carefully."
            else:
                return "You're doing great by practicing reading! Remember to take your time with each word. Reading gets easier with practice!"
    
    # ===============================
    # PROGRESS TRACKING & ANALYTICS
    # ===============================
    
    async def update_reading_progress(
        self,
        student_id: int,
        session_data: Dict[str, Any],
        db: Session
    ) -> None:
        """Update student's overall reading progress"""
        
        progress = db.query(ReadingProgress).filter_by(student_id=student_id).first()
        
        if not progress:
            progress = ReadingProgress(
                student_id=student_id,
                current_reading_level=ReadingLevel.KINDERGARTEN,
                current_difficulty=DifficultyLevel.ELEMENTARY
            )
            db.add(progress)
        
        # Update statistics
        progress.total_sessions += 1
        if session_data.get('duration'):
            progress.total_reading_time += session_data['duration']
        
        if session_data.get('words_read_correctly'):
            progress.words_read_correctly += session_data['words_read_correctly']
        
        # Calculate rolling averages
        recent_sessions = db.query(ReadingSession).filter_by(
            student_id=student_id
        ).order_by(ReadingSession.started_at.desc()).limit(10).all()
        
        if recent_sessions:
            accuracy_scores = [s.accuracy_score for s in recent_sessions if s.accuracy_score]
            fluency_scores = [s.fluency_score for s in recent_sessions if s.fluency_score]
            
            if accuracy_scores:
                progress.average_accuracy = sum(accuracy_scores) / len(accuracy_scores)
            if fluency_scores:
                progress.average_fluency = sum(fluency_scores) / len(fluency_scores)
        
        # Check for level advancement
        await self._check_level_advancement(progress, db)
        
        db.commit()
    
    async def _check_level_advancement(self, progress: ReadingProgress, db: Session) -> None:
        """Check if student is ready to advance to next level"""
        
        # Criteria for advancement (can be customized)
        advancement_criteria = {
            "accuracy_threshold": 85.0,
            "fluency_threshold": 75.0,
            "min_sessions": 5,
            "consistency_sessions": 3  # Must meet criteria for X consecutive sessions
        }
        
        if (progress.average_accuracy and progress.average_accuracy >= advancement_criteria["accuracy_threshold"] and
            progress.average_fluency and progress.average_fluency >= advancement_criteria["fluency_threshold"] and
            progress.total_sessions >= advancement_criteria["min_sessions"]):
            
            # Check if ready for next difficulty level or reading level
            await self._advance_student_level(progress)
    
    async def _advance_student_level(self, progress: ReadingProgress) -> None:
        """Advance student to next appropriate level"""
        
        # First try advancing difficulty within same reading level
        if progress.current_difficulty == DifficultyLevel.ELEMENTARY:
            progress.current_difficulty = DifficultyLevel.INTERMEDIATE
        elif progress.current_difficulty == DifficultyLevel.INTERMEDIATE:
            progress.current_difficulty = DifficultyLevel.ADVANCED
        else:
            # Advance to next reading level
            level_progression = {
                ReadingLevel.KINDERGARTEN: ReadingLevel.GRADE_1,
                ReadingLevel.GRADE_1: ReadingLevel.GRADE_2,
                ReadingLevel.GRADE_2: ReadingLevel.GRADE_3,
                ReadingLevel.GRADE_3: ReadingLevel.GRADE_3  # Stay at Grade 3
            }
            
            next_level = level_progression.get(progress.current_reading_level)
            if next_level != progress.current_reading_level:
                progress.current_reading_level = next_level
                progress.current_difficulty = DifficultyLevel.ELEMENTARY
        
        progress.last_level_up = datetime.utcnow()
    
    # ===============================
    # CONTENT RECOMMENDATION ENGINE
    # ===============================
    
    async def get_recommended_content(
        self,
        student_id: int,
        db: Session,
        limit: int = 5
    ) -> List[ReadingContent]:
        """Get personalized content recommendations for student"""
        
        progress = db.query(ReadingProgress).filter_by(student_id=student_id).first()
        
        if not progress:
            # Default recommendations for new students
            return db.query(ReadingContent).filter(
                ReadingContent.reading_level == ReadingLevel.KINDERGARTEN,
                ReadingContent.difficulty_level == DifficultyLevel.ELEMENTARY,
                ReadingContent.is_active == True
            ).limit(limit).all()
        
        # Get content matching current level
        base_query = db.query(ReadingContent).filter(
            ReadingContent.reading_level == progress.current_reading_level,
            ReadingContent.is_active == True
        )
        
        # Prioritize based on student's challenges and strengths
        recommendations = []
        
        # Add current difficulty level content
        current_level_content = base_query.filter(
            ReadingContent.difficulty_level == progress.current_difficulty
        ).limit(3).all()
        recommendations.extend(current_level_content)
        
        # Add some easier content for confidence building
        if progress.current_difficulty != DifficultyLevel.ELEMENTARY:
            easier_content = base_query.filter(
                ReadingContent.difficulty_level == DifficultyLevel.ELEMENTARY
            ).limit(1).all()
            recommendations.extend(easier_content)
        
        # Add challenging content if student is performing well
        if (progress.average_accuracy and progress.average_accuracy > 85 and 
            progress.current_difficulty != DifficultyLevel.ADVANCED):
            
            challenging_content = base_query.filter(
                ReadingContent.difficulty_level == DifficultyLevel.ADVANCED
            ).limit(1).all()
            recommendations.extend(challenging_content)
        
        return recommendations[:limit]
    
    async def get_ai_personalized_recommendations(
        self,
        student_id: int,
        db: Session,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Get AI-generated personalized content recommendations"""
        
        try:
            # Get student progress and reading history
            progress = db.query(ReadingProgress).filter_by(student_id=student_id).first()
            recent_attempts = db.query(ReadingAttempt).filter_by(student_id=student_id).order_by(desc(ReadingAttempt.created_at)).limit(10).all()
            
            # Build student profile for AI
            student_profile = {
                "reading_level": progress.current_reading_level.value if progress else "KINDERGARTEN",
                "current_accuracy": progress.average_accuracy if progress else 0.8,
                "struggle_areas": self._identify_struggle_areas(recent_attempts),
                "interests": ["animals", "colors", "family"],  # Could be expanded with user preferences
                "completed_content_ids": [attempt.content_id for attempt in recent_attempts]
            }
            
            # Use AI to generate personalized recommendations
            ai_recommendations = await self.gemini_service.generate_personalized_recommendations(student_profile)
            
            return ai_recommendations[:limit]
            
        except Exception as e:
            print(f"❌ AI recommendations failed: {e}")
            # Fallback to rule-based recommendations
            content_recs = await self.get_recommended_content(student_id, db, limit)
            return [
                {
                    "title": content.title,
                    "content_type": content.content_type,
                    "topic": "general",
                    "difficulty_justification": f"Appropriate for {content.reading_level.value}",
                    "why_recommended": "Based on your reading level",
                    "expected_benefit": "Will help improve reading skills"
                }
                for content in content_recs
            ]
    
    def _identify_struggle_areas(self, recent_attempts: List[ReadingAttempt]) -> List[str]:
        """Identify areas where student struggles based on recent attempts"""
        struggle_areas = []
        
        if not recent_attempts:
            return ["pronunciation", "fluency"]
        
        # Analyze recent performance
        low_accuracy_count = sum(1 for attempt in recent_attempts if attempt.accuracy_score and attempt.accuracy_score < 0.8)
        
        if low_accuracy_count > len(recent_attempts) * 0.5:
            struggle_areas.append("pronunciation")
        
        # Add more analysis based on attempt data
        avg_accuracy = sum(attempt.accuracy_score or 0.8 for attempt in recent_attempts) / len(recent_attempts)
        if avg_accuracy < 0.75:
            struggle_areas.extend(["fluency", "sight_words"])
        
        return struggle_areas or ["general_practice"]
    
    # ===============================
    # TEXT-TO-SPEECH FEEDBACK
    # ===============================
    
    async def generate_audio_feedback(
        self,
        feedback_text: str,
        output_path: str,
        voice_style: str = "friendly"
    ) -> str:
        """Generate audio feedback using text-to-speech"""
        
        # This would integrate with a TTS service like Google Cloud TTS
        # For now, return the path where audio would be saved
        
        tts_prompt = f"""
        Convert this educational feedback to natural, encouraging speech for a young child:
        "{feedback_text}"
        
        Use a {voice_style}, warm tone appropriate for ages 4-8.
        Speak clearly and at a moderate pace suitable for children learning to read.
        """
        
        # In a real implementation, you would:
        # 1. Use Google Cloud TTS or similar service
        # 2. Generate audio file
        # 3. Save to specified path
        # 4. Return the file path
        
        return output_path

# Singleton instance
reading_assistant_service = ReadingAssistantService()
