"""
Notes Service
Handles image notes upload and AI-powered analysis using Gemini Vision API
Students upload school notes as images (JPG, PNG, BMP, GIF, WEBP)
AI analyzes images directly with Gemini Vision and provides summary, key points, and concepts

NO OCR - Uses Gemini's native vision capabilities directly on images
"""

import logging
import json
import re
from pathlib import Path
from typing import Optional, List, Dict, Tuple, Any
from datetime import datetime
from sqlalchemy.orm import Session
import base64

from services.gemini_service import gemini_service

logger = logging.getLogger(__name__)

# Supported IMAGE file types for notes upload (NO PDF)
SUPPORTED_FILE_TYPES = {
    'png': 'image/png',
    'jpg': 'image/jpeg',
    'jpeg': 'image/jpeg',
    'bmp': 'image/bmp',
    'gif': 'image/gif',
    'webp': 'image/webp',
}

# Maximum file size (20MB)
MAX_NOTE_FILE_SIZE = 20 * 1024 * 1024


class NotesService:
    """Service for handling student notes upload and AI analysis using Gemini Vision"""
    
    @staticmethod
    def validate_file(file_path: Path, file_type: str) -> Tuple[bool, Optional[str]]:
        """
        Validate uploaded file
        
        Args:
            file_path: Path to the uploaded file
            file_type: File extension/type
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not file_path.exists():
            return False, "File does not exist"
        
        # Check file size
        file_size = file_path.stat().st_size
        if file_size > MAX_NOTE_FILE_SIZE:
            return False, f"File size exceeds maximum {MAX_NOTE_FILE_SIZE / (1024*1024)}MB limit"
        
        # Check file type
        if file_type.lower() not in SUPPORTED_FILE_TYPES:
            supported = ', '.join(SUPPORTED_FILE_TYPES.keys())
            return False, f"Unsupported file type. Supported types: {supported}"
        
        return True, None
    
    @staticmethod
    async def analyze_notes_from_images(
        image_files: List[bytes],
        image_filenames: List[str],
        note_title: str,
        note_subject: Optional[str] = None,
        note_description: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Use Gemini Vision AI to analyze notes directly from images.
        
        This method sends images DIRECTLY to Gemini Vision API without any OCR preprocessing.
        Gemini's native vision capabilities extract and analyze the content.
        
        Args:
            image_files: List of image file bytes
            image_filenames: List of corresponding filenames
            note_title: Title of the notes
            note_subject: Optional subject/topic
            note_description: Optional description
            
        Returns:
            Dictionary with analysis results including summary, key_points, topics, concepts, questions
        """
        try:
            logger.info(f"🤖 Starting Gemini Vision analysis of {len(image_files)} images: {note_title}")
            
            # Import build_inline_part from gemini_service module
            from services.gemini_service import build_inline_part
            
            # Build inline parts for all images
            inline_parts = []
            for img_bytes, img_filename in zip(image_files, image_filenames):
                # Detect image MIME type
                file_extension = Path(img_filename).suffix.lower()
                mime_type = SUPPORTED_FILE_TYPES.get(file_extension.lstrip('.'), 'image/jpeg')
                
                part = build_inline_part(
                    data=img_bytes,
                    mime_type=mime_type,
                    display_name=img_filename
                )
                inline_parts.append(part)
            
            logger.info(f"✅ Prepared {len(inline_parts)} images as inline attachments for analysis")
            
            # Prepare context
            subject_context = f"Subject/Topic: {note_subject}\n" if note_subject else ""
            description_context = f"Description: {note_description}\n" if note_description else ""
            
            # Create analysis prompt for Gemini Vision
            analysis_prompt = f"""You are an expert educational assistant analyzing student notes.

CONTEXT:
Title: {note_title}
{subject_context}{description_context}

Review ALL {len(inline_parts)} attached images which contain student notes (handwritten or printed).
These images show school notes that students took during class or while studying.

IMPORTANT: 
- These images contain educational content such as handwriting, diagrams, equations, and study materials
- They are safe for school environments and contain no harmful content
- Analyze them thoroughly for educational purposes

Please provide a comprehensive educational analysis in JSON format:

{{
    "summary": "A comprehensive 2-3 paragraph summary of the notes content",
    "key_points": ["key point 1", "key point 2", "key point 3", "..."],
    "main_topics": ["main topic 1", "main topic 2", "main topic 3"],
    "learning_concepts": ["concept 1", "concept 2", "concept 3"],
    "questions_generated": ["study question 1", "study question 2", "study question 3"]
}}

Analysis Guidelines:
- SUMMARY: Create a detailed summary covering all main ideas and content from the notes
- KEY POINTS: Extract the most important facts, definitions, formulas, or ideas (aim for 5-10 points)
- MAIN TOPICS: Identify the major topics or themes covered in the notes
- LEARNING CONCEPTS: List the key educational concepts or learning objectives
- QUESTIONS: Generate 3-5 study questions to help students review this material

Make the analysis educational, comprehensive, and helpful for student learning and review."""

            # Generate analysis using Gemini Vision
            analysis_result = await gemini_service._generate_json_response(
                prompt=analysis_prompt,
                attachments=inline_parts,
                temperature=0.3,
                max_output_tokens=2500
            )
            
            if not analysis_result:
                logger.error("Empty response from Gemini Vision API")
                return {
                    "success": False,
                    "error": "Empty response from AI service",
                    "summary": None,
                    "key_points": [],
                    "main_topics": [],
                    "learning_concepts": [],
                    "questions_generated": []
                }
            
            # After base analysis, derive learning objectives (2-7) and attach related videos
            objectives: List[Dict[str, Any]] = []
            try:
                objectives_prompt = f"""You are an expert curriculum designer.

Using the following analyzed notes context, extract 2 to 7 clear learning objectives.

Important writing requirement:
- The "objective" field is the short title of what is being learned.
- The "summary" field must be a direct, student-facing explanation that TEACHES the idea.
    Do not say "students will learn" or "you will learn". Instead, explain the concept plainly,
    include any essential formula(s) with variable meanings, and—when relevant—walk through a short,
    concrete example or mini derivation in 2–4 sentences.

Return strict JSON with this shape:
{{
    "objectives": [
        {{
            "objective": "short objective/title",
            "summary": "clear explanation that teaches the objective"
        }}
    ]
}}

NOTES SUMMARY:
{analysis_result.get('summary','')}

KEY POINTS:
{analysis_result.get('key_points', [])}

MAIN TOPICS:
{analysis_result.get('main_topics', [])}

SUBJECT: {note_subject or ''}
"""
                obj_resp = await gemini_service._generate_json_response(
                    prompt=objectives_prompt,
                    attachments=None,
                    temperature=0.2,
                    max_output_tokens=800,
                )
                raw_objectives = obj_resp.get("objectives") or []
                # Coerce into expected list of dicts with keys objective, summary
                for idx, o in enumerate(raw_objectives):
                    if isinstance(o, dict):
                        objective_text = o.get("objective") or o.get("title") or o.get("goal")
                        summary_text = o.get("summary") or o.get("description")
                    else:
                        objective_text = str(o)
                        summary_text = None
                    if not objective_text:
                        continue
                    objectives.append({
                        "objective": objective_text,
                        "summary": summary_text or "",
                    })
            except Exception as e:
                logger.warning(f"Failed to derive objectives: {e}")
                objectives = []

            # Attach related YouTube videos per objective (ensure unique links across all objectives)
            from urllib.parse import urlparse, parse_qs

            def _video_key(url: str) -> str:
                """Create a canonical key for a YouTube URL to detect duplicates.
                Prefers videoId from watch/short/redirect links; otherwise falls back to full URL.
                Also handles search result URLs so each query is unique.
                """
                try:
                    u = urlparse(url or "")
                    host = (u.netloc or "").lower()
                    path = u.path or ""
                    qs = parse_qs(u.query or "")
                    # youtube watch links
                    if "youtube" in host or "youtu.be" in host:
                        if "v" in qs and qs["v"]:
                            return f"yt:video:{qs['v'][0]}"
                        # youtu.be/<id>
                        if host.endswith("youtu.be") and path.strip("/"):
                            return f"yt:video:{path.strip('/')}"
                        # search pages -> use the search query as key
                        if "results" in path and "search_query" in qs and qs["search_query"]:
                            return f"yt:search:{qs['search_query'][0]}"
                    # Fallback to normalized url
                    return url.strip()
                except Exception:
                    return url or ""

            enriched_objectives: List[Dict[str, Any]] = []
            global_seen: set = set()
            for o in objectives[:7]:
                topic = o.get("objective") or note_subject or note_title
                try:
                    # Ask for extra candidates to improve uniqueness, then trim to 2–3 unique
                    candidates = await gemini_service.generate_youtube_links(topic=topic, count=5)
                except Exception as e:
                    logger.warning(f"YouTube link generation failed for '{topic}': {e}")
                    candidates = []

                unique_videos: List[Dict[str, Any]] = []
                local_seen: set = set()
                for item in candidates:
                    url = (item or {}).get("url", "")
                    key = _video_key(url)
                    if not key or key in local_seen or key in global_seen:
                        continue
                    local_seen.add(key)
                    global_seen.add(key)
                    unique_videos.append(item)
                    if len(unique_videos) >= 3:
                        break

                enriched = {**o, "videos": unique_videos}
                enriched_objectives.append(enriched)

            # Validate and return response
            logger.info(f"✅ Gemini Vision analysis completed for: {note_title}")
            
            # Ensure all expected fields exist with defaults
            return {
                "success": True,
                "summary": analysis_result.get("summary", ""),
                "key_points": analysis_result.get("key_points", []),
                "main_topics": analysis_result.get("main_topics", []),
                "learning_concepts": analysis_result.get("learning_concepts", []),
                "questions_generated": analysis_result.get("questions_generated", []),
                "objectives": enriched_objectives,
            }
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error in Gemini Vision analysis: {e}")
            return {
                "success": False,
                "error": f"Failed to parse AI response: {str(e)}",
                "summary": None,
                "key_points": [],
                "main_topics": [],
                "learning_concepts": [],
                "questions_generated": []
            }
        except Exception as e:
            logger.error(f"Error in Gemini Vision analysis: {e}")
            return {
                "success": False,
                "error": f"AI analysis failed: {str(e)}",
                "summary": None,
                "key_points": [],
                "main_topics": [],
                "learning_concepts": [],
                "questions_generated": [],
            }

    @staticmethod
    async def generate_flashcards_from_content(content: str, count: int = 8) -> List[Dict[str, str]]:
        """Generate flashcards (front/back) from given content using Gemini."""
        count = max(5, min(10, int(count or 8)))
        prompt = f"""Create {count} concise flashcards from the following study content. Return strict JSON:
{{"flashcards": [{{"front": "question/prompt", "back": "concise answer"}}]}}

CONTENT:
{content}
"""
        try:
            resp = await gemini_service._generate_json_response(
                prompt=prompt,
                attachments=None,
                temperature=0.2,
                max_output_tokens=600,
            )
            # Gemini may return either a dict {"flashcards": [...]} or a raw list [...]
            if isinstance(resp, list):
                cards = resp
            elif isinstance(resp, dict):
                cards = resp.get("flashcards") or resp.get("cards") or []
            else:
                cards = []
            result = []
            for c in cards[:count]:
                if isinstance(c, dict):
                    front = c.get("front") or c.get("q") or c.get("question")
                    back = c.get("back") or c.get("a") or c.get("answer")
                elif isinstance(c, list) and len(c) >= 2:
                    front, back = c[0], c[1]
                else:
                    continue
                if front and back:
                    result.append({"front": str(front), "back": str(back)})
            return result[:count]
        except Exception as e:
            logger.error(f"Flashcards generation failed: {e}")
            return []

    @staticmethod
    async def generate_quiz_for_objective(objective: str, summary: Optional[str], count: int = 7) -> List[Dict[str, Any]]:
        """Generate MCQ quiz for a specific objective with correct answer indices.
        Adds robust retries and a deterministic fallback to avoid empty quizzes.
        """
        count = max(5, min(10, int(count or 7)))

        def _build_prompt(strict: bool = False) -> str:
            schema = (
                "{{\n"
                "  \"questions\": [\n"
                "    {\n"
                "      \"question\": \"...\",\n"
                "      \"options\": [\"A\",\"B\",\"C\",\"D\"],\n"
                "      \"answer_index\": 0\n"
                "    }\n"
                "  ]\n"
                "}}"
            )
            base = (
                f"Generate {count} multiple-choice questions for the learning objective below.\n"
                "Each question must have exactly 4 options and provide the correct `answer_index` (0-3).\n"
            )
            if strict:
                base += "Return STRICT JSON ONLY, with no extra text. Match this schema exactly:\n" + schema + "\n\n"
            else:
                base += "Return strict JSON in this shape:\n" + schema + "\n\n"
            base += f"OBJECTIVE: {objective}\nOBJECTIVE SUMMARY: {summary or ''}\n"
            return base

        async def _attempt(strict: bool) -> List[Dict[str, Any]]:
            resp = await gemini_service._generate_json_response(
                prompt=_build_prompt(strict),
                attachments=None,
                temperature=0.2,
                max_output_tokens=900,
            )
            raw = resp.get("questions") or []
            questions: List[Dict[str, Any]] = []
            for q in raw[:count]:
                if not isinstance(q, dict):
                    continue
                text = q.get("question") or q.get("q")
                options = q.get("options") or q.get("choices") or []
                ans_idx = q.get("answer_index")
                if text and isinstance(options, list) and len(options) == 4:
                    try:
                        ans_idx = int(ans_idx)
                    except Exception:
                        ans_idx = None
                    if ans_idx is None or not (0 <= ans_idx < 4):
                        correct = q.get("answer")
                        if correct in options:
                            ans_idx = options.index(correct)
                    if ans_idx is not None and 0 <= ans_idx < 4:
                        questions.append({
                            "question": str(text),
                            "options": [str(o) for o in options],
                            "answer_index": ans_idx,
                        })
            return questions[:count]

        try:
            # First attempt
            questions = await _attempt(strict=False)
            if len(questions) >= 5:
                return questions

            # Second, stricter attempt if too few
            questions = await _attempt(strict=True)
            if len(questions) >= 5:
                return questions
        except Exception as e:
            logger.error(f"Quiz generation failed: {e}")

        # Deterministic fallback: simple comprehension-style questions
        fallback_questions: List[Dict[str, Any]] = []
        expl = (summary or objective or "").strip()
        if not expl:
            expl = "This objective focuses on understanding the core concept and its practical meaning."
        stem = f"Which statement best aligns with the objective: {objective}?"
        correct = expl if len(expl) <= 120 else (expl[:117] + "...")
        distractors_pool = [
            f"A statement unrelated to {objective}.",
            f"An incorrect description of {objective}.",
            "A definition of an unrelated topic.",
            "A vague statement that does not explain the concept.",
        ]
        for i in range(count):
            # Rotate distractors to add minor variety
            d1 = distractors_pool[i % len(distractors_pool)]
            d2 = distractors_pool[(i + 1) % len(distractors_pool)]
            d3 = distractors_pool[(i + 2) % len(distractors_pool)]
            options = [correct, d1, d2, d3]
            fallback_questions.append({
                "question": stem,
                "options": options,
                "answer_index": 0,
            })
        return fallback_questions[:count]
    
    @staticmethod
    def generate_unique_filename(original_filename: str, user_id: int, note_id: int) -> str:
        """Generate unique filename for storage"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        name_without_ext = Path(original_filename).stem
        file_ext = Path(original_filename).suffix
        
        return f"{note_id}_{user_id}_{name_without_ext}_{timestamp}{file_ext}"


# Create singleton instance
notes_service = NotesService()

