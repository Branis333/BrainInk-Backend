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
            
            # Validate and return response
            logger.info(f"✅ Gemini Vision analysis completed for: {note_title}")
            
            # Ensure all expected fields exist with defaults
            return {
                "success": True,
                "summary": analysis_result.get("summary", ""),
                "key_points": analysis_result.get("key_points", []),
                "main_topics": analysis_result.get("main_topics", []),
                "learning_concepts": analysis_result.get("learning_concepts", []),
                "questions_generated": analysis_result.get("questions_generated", [])
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
                "questions_generated": []
            }
    
    @staticmethod
    def generate_unique_filename(original_filename: str, user_id: int, note_id: int) -> str:
        """Generate unique filename for storage"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        name_without_ext = Path(original_filename).stem
        file_ext = Path(original_filename).suffix
        
        return f"{note_id}_{user_id}_{name_without_ext}_{timestamp}{file_ext}"


# Create singleton instance
notes_service = NotesService()

