import os
import time
import json
import re
from typing import Optional, Dict, Any, List
from datetime import datetime
import google.generativeai as genai
from sqlalchemy.orm import Session
from models.notes_models import StudyNotes


class GeminiService:
    """Stateless Gemini service for AI analysis operations (no database dependency)"""
    
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable is required")
        
        # Configure Gemini
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel('models/gemini-1.5-pro-latest')
    
    def generate_content(self, prompt: str) -> str:
        """Generate content using Gemini AI"""
        try:
            response = self.model.generate_content(prompt)
            if not response.text:
                raise Exception("Gemini returned empty response")
            return response.text
        except Exception as e:
            print(f"Error generating content with Gemini: {e}")
            raise e


class GeminiNotesService:
    def __init__(self, db: Session):
        self.db = db
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable is required")
        
        # Configure Gemini
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel('models/gemini-1.5-pro-latest')
        
    def generate_study_notes(
        self, 
        transcription_text: str, 
        user_id: int,
        subject: Optional[str] = None,
        language: str = "en"
    ) -> Dict[str, Any]:
        """Generate study notes from transcription text using Gemini"""
        
        start_time = time.time()
        
        try:
            # Create the prompt for Gemini
            prompt = self._create_notes_prompt(transcription_text, subject, language)
            
            print(f"Generating notes for user {user_id} using Gemini...")
            
            # Generate content using Gemini
            response = self.model.generate_content(prompt)
            
            if not response.text:
                raise Exception("Gemini returned empty response")
            
            # Parse the response
            notes_data = self._parse_gemini_response(response.text)
            
            # Generate title if not provided
            if not notes_data.get('title'):
                notes_data['title'] = self._generate_title(transcription_text)
            
            # Calculate processing time
            processing_time = time.time() - start_time
            
            # Save to database
            study_notes = self._save_notes_to_db(
                user_id=user_id,
                original_text=transcription_text,
                notes_data=notes_data,
                subject=subject,
                language=language,
                processing_time=processing_time
            )
            
            return {
                "success": True,
                "notes_id": study_notes.id,
                "title": study_notes.title,
                "brief_notes": study_notes.brief_notes,
                "key_points": json.loads(study_notes.key_points) if study_notes.key_points else [],
                "summary": study_notes.summary,
                "processing_time_seconds": processing_time,
                "word_count_original": len(transcription_text.split()),
                "word_count_notes": len(study_notes.brief_notes.split()),
                "created_at": study_notes.created_at.isoformat()
            }
            
        except Exception as e:
            print(f"Error generating study notes: {e}")
            return {
                "success": False,
                "error": str(e),
                "processing_time_seconds": time.time() - start_time
            }
    
    def _create_notes_prompt(self, text: str, subject: Optional[str], language: str) -> str:
        """Create a prompt for Gemini to generate study notes"""
        
        subject_context = f" about {subject}" if subject else ""
        
        if language.lower() in ['ar', 'arabic']:
            prompt = f"""
            قم بتحويل النص التالي إلى ملاحظات دراسية موجزة ومفيدة{subject_context}:

            النص الأصلي:
            {text}

            يرجى تقديم:
            1. العنوان: عنوان وصفي للموضوع
            2. الملاحظات الموجزة: ملاحظات دراسية منظمة ومختصرة
            3. النقاط الرئيسية: قائمة بأهم النقاط (5-7 نقاط كحد أقصى)
            4. الملخص: ملخص مختصر في 2-3 جمل

            تنسيق الإجابة:
            العنوان: [العنوان هنا]
            
            الملاحظات الموجزة:
            [الملاحظات المنظمة هنا]
            
            النقاط الرئيسية:
            • [النقطة الأولى]
            • [النقطة الثانية]
            • [النقطة الثالثة]
            
            الملخص:
            [الملخص هنا]
            """
        elif language.lower() in ['sw', 'swahili']:
            prompt = f"""
            Badilisha maandishi haya kuwa vidokezo vya kujifunzia vilivyo fupishwa na vyenye maana{subject_context}:

            Maandishi asilia:
            {text}

            Tafadhali toa:
            1. Kichwa: Kichwa cha kuelezea mada
            2. Vidokezo vilivyo fupishwa: Vidokezo vilivyo pangwa na vya ufupi
            3. Mambo muhimu: Orodha ya mambo muhimu (5-7 mambo)
            4. Muhtasari: Muhtasari mfupi wa sentensi 2-3

            Mpangilio wa jibu:
            Kichwa: [Kichwa hapa]
            
            Vidokezo vilivyo fupishwa:
            [Vidokezo vilivyo pangwa hapa]
            
            Mambo muhimu:
            • [Jambo la kwanza]
            • [Jambo la pili]
            • [Jambo la tatu]
            
            Muhtasari:
            [Muhtasari hapa]
            """
        elif language.lower() in ['af', 'afrikaans']:
            prompt = f"""
            Omskep die volgende teks in bondige en nuttige studienotas{subject_context}:

            Oorspronklike teks:
            {text}

            Verskaf asseblief:
            1. Titel: 'n Beskrywende titel vir die onderwerp
            2. Bondige notas: Georganiseerde en bondige studienotas
            3. Sleutelpunte: Lys van belangrikste punte (maksimum 5-7 punte)
            4. Opsomming: Kort opsomming in 2-3 sinne

            Formaat van antwoord:
            Titel: [Titel hier]
            
            Bondige notas:
            [Georganiseerde notas hier]
            
            Sleutelpunte:
            • [Eerste punt]
            • [Tweede punt]
            • [Derde punt]
            
            Opsomming:
            [Opsomming hier]
            """
        else:
            prompt = f"""
            Transform the following text into concise and useful study notes{subject_context}:

            Original text:
            {text}

            Please provide:
            1. Title: A descriptive title for the topic
            2. Brief notes: Organized and concise study notes
            3. Key points: List of most important points (maximum 5-7 points)
            4. Summary: Brief summary in 2-3 sentences

            Format the response as:
            Title: [Title here]
            
            Brief notes:
            [Organized notes here]
            
            Key points:
            • [First point]
            • [Second point]
            • [Third point]
            
            Summary:
            [Summary here]
            """
        
        return prompt
    
    def _parse_gemini_response(self, response_text: str) -> Dict[str, Any]:
        """Parse Gemini's response into structured data"""
        
        try:
            result = {
                'title': '',
                'brief_notes': '',
                'key_points': [],
                'summary': ''
            }
            
            lines = response_text.strip().split('\n')
            current_section = None
            current_content = []
            
            for line in lines:
                line = line.strip()
                
                if any(keyword in line.lower() for keyword in ['title:', 'titel:', 'kichwa:', 'العنوان:']):
                    if current_section:
                        result[current_section] = self._process_section_content(current_section, current_content)
                    current_section = 'title'
                    current_content = [line.split(':', 1)[-1].strip()]
                    
                elif any(keyword in line.lower() for keyword in ['brief notes:', 'bondige notas:', 'vidokezo vilivyo fupishwa:', 'الملاحظات الموجزة:']):
                    if current_section:
                        result[current_section] = self._process_section_content(current_section, current_content)
                    current_section = 'brief_notes'
                    current_content = []
                    
                elif any(keyword in line.lower() for keyword in ['key points:', 'sleutelpunte:', 'mambo muhimu:', 'النقاط الرئيسية:']):
                    if current_section:
                        result[current_section] = self._process_section_content(current_section, current_content)
                    current_section = 'key_points'
                    current_content = []
                    
                elif any(keyword in line.lower() for keyword in ['summary:', 'opsomming:', 'muhtasari:', 'الملخص:']):
                    if current_section:
                        result[current_section] = self._process_section_content(current_section, current_content)
                    current_section = 'summary'
                    current_content = []
                    
                else:
                    if current_section and line:
                        current_content.append(line)
            
            if current_section:
                result[current_section] = self._process_section_content(current_section, current_content)
            
            return result
            
        except Exception as e:
            print(f"Error parsing Gemini response: {e}")
            return {
                'title': 'Study Notes',
                'brief_notes': response_text,
                'key_points': [],
                'summary': ''
            }
    
    def _process_section_content(self, section: str, content: List[str]) -> Any:
        """Process content for specific sections"""
        
        if section == 'title':
            return content[0] if content else 'Study Notes'
        
        elif section == 'key_points':
            points = []
            for line in content:
                clean_line = re.sub(r'^[•\-\*\d\.\)\s]+', '', line).strip()
                if clean_line:
                    points.append(clean_line)
            return points
        
        else:  # brief_notes, summary
            return '\n'.join(content).strip()
    
    def _generate_title(self, text: str) -> str:
        """Generate a title from the text if none provided"""
        title = text[:50]
        if len(text) > 50:
            last_period = title.rfind('.')
            last_space = title.rfind(' ')
            
            if last_period > 20:
                title = title[:last_period]
            elif last_space > 20:
                title = title[:last_space]
            
            title += "..."
        
        return title.strip()
    
    def _save_notes_to_db(
        self,
        user_id: int,
        original_text: str,
        notes_data: Dict[str, Any],
        subject: Optional[str],
        language: str,
        processing_time: float
    ) -> StudyNotes:
        """Save generated notes to database"""
        
        try:
            study_notes = StudyNotes(
                user_id=user_id,
                title=notes_data['title'],
                original_text=original_text,
                brief_notes=notes_data['brief_notes'],
                key_points=json.dumps(notes_data['key_points']) if notes_data['key_points'] else None,
                summary=notes_data['summary'],
                subject=subject,
                language=language,
                word_count_original=len(original_text.split()),
                word_count_notes=len(notes_data['brief_notes'].split()),
                processing_time_seconds=processing_time,
                gemini_model_used='gemini-pro'
            )
            
            self.db.add(study_notes)
            self.db.commit()
            self.db.refresh(study_notes)
            
            return study_notes
            
        except Exception as e:
            self.db.rollback()
            print(f"Error saving notes to database: {e}")
            raise e
    
    def get_user_notes(self, user_id: int, page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        """Get user's study notes with pagination"""
        try:
            total_count = self.db.query(StudyNotes).filter(
                StudyNotes.user_id == user_id
            ).count()
            
            offset = (page - 1) * page_size
            notes = self.db.query(StudyNotes).filter(
                StudyNotes.user_id == user_id
            ).order_by(StudyNotes.created_at.desc()).offset(offset).limit(page_size).all()
            
            return {
                "success": True,
                "notes": [self._format_notes_response(note) for note in notes],
                "total_count": total_count,
                "page": page,
                "page_size": page_size,
                "has_next": (page * page_size) < total_count
            }
            
        except Exception as e:
            print(f"Error getting user notes: {e}")
            return {"success": False, "error": str(e)}
    
    def get_notes_by_id(self, notes_id: int, user_id: int) -> Dict[str, Any]:
        """Get specific notes by ID"""
        try:
            notes = self.db.query(StudyNotes).filter(
                StudyNotes.id == notes_id,
                StudyNotes.user_id == user_id
            ).first()
            
            if not notes:
                return {"success": False, "error": "Notes not found"}
            
            notes.view_count += 1
            notes.last_viewed = datetime.utcnow()
            self.db.commit()
            
            return {
                "success": True,
                "notes": self._format_notes_response(notes)
            }
            
        except Exception as e:
            print(f"Error getting notes by ID: {e}")
            return {"success": False, "error": str(e)}
    
    def _format_notes_response(self, notes: StudyNotes) -> Dict[str, Any]:
        """Format notes for API response"""
        return {
            "id": notes.id,
            "title": notes.title,
            "brief_notes": notes.brief_notes,
            "key_points": json.loads(notes.key_points) if notes.key_points else [],
            "summary": notes.summary,
            "subject": notes.subject,
            "language": notes.language,
            "word_count_original": notes.word_count_original,
            "word_count_notes": notes.word_count_notes,
            "processing_time_seconds": notes.processing_time_seconds,
            "is_favorite": notes.is_favorite,
            "view_count": notes.view_count,
            "created_at": notes.created_at.isoformat(),
            "updated_at": notes.updated_at.isoformat(),
            "last_viewed": notes.last_viewed.isoformat() if notes.last_viewed else None
        }
    
    def delete_notes(self, notes_id: int, user_id: int) -> Dict[str, Any]:
        """Delete study notes"""
        try:
            notes = self.db.query(StudyNotes).filter(
                StudyNotes.id == notes_id,
                StudyNotes.user_id == user_id
            ).first()
            
            if not notes:
                return {"success": False, "error": "Notes not found"}
            
            self.db.delete(notes)
            self.db.commit()
            
            return {"success": True, "message": "Notes deleted successfully"}
            
        except Exception as e:
            self.db.rollback()
            print(f"Error deleting notes: {e}")
            return {"success": False, "error": str(e)}