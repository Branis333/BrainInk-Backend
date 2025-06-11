import os
import tempfile
import librosa
import soundfile as sf
# import speech_recognition as sr
from pydub import AudioSegment
from sqlalchemy.orm import Session
from models.speech_models import SpeechTranscription, TranscriptionHistory
from schemas.speech_schemas import TranscriptionSettings, ProcessingStatus
from typing import Optional, Tuple, Dict, Any, List
from datetime import datetime, timedelta
import json
import time
import asyncio
import aiofiles
import io
import threading
from concurrent.futures import ThreadPoolExecutor
import numpy as np

from utils.speech_flags import WHISPER_AVAILABLE, SPEECH_RECOGNITION_AVAILABLE

executor = ThreadPoolExecutor(max_workers=2)

class SpeechService:
    def __init__(self, db: Session):
        self.db = db
        self.upload_dir = os.getenv("UPLOAD_DIR", "uploads/audio")
        self.max_file_size = int(os.getenv("MAX_FILE_SIZE_MB", 100)) * 1024 * 1024  # Convert to bytes
        self.max_duration = int(os.getenv("MAX_DURATION_MINUTES", 30)) * 60  # Convert to seconds
        
        # Create upload directory if it doesn't exist
        os.makedirs(self.upload_dir, exist_ok=True)
        
        # Initialize speech recognition
        self.recognizer = sr.Recognizer()
        
        # Initialize Whisper if available
        self.whisper_model = None
        if WHISPER_AVAILABLE:
            try:
                self.whisper_model = whisper.load_model("base")
            except Exception as e:
                print(f"Failed to load Whisper model: {e}")
    
    async def save_audio_file(self, file, user_id: int) -> Tuple[bool, str, Optional[str]]:
        """Save uploaded audio file and return file path"""
        try:
            # Check file size
            file_content = await file.read()
            if len(file_content) > self.max_file_size:
                return False, f"File too large. Maximum size: {self.max_file_size // (1024*1024)}MB", None
            
            # Generate unique filename
            timestamp = int(time.time())
            file_extension = os.path.splitext(file.filename)[1].lower()
            safe_filename = f"user_{user_id}_{timestamp}_{file.filename}"
            file_path = os.path.join(self.upload_dir, safe_filename)
            
            # Save file
            async with aiofiles.open(file_path, 'wb') as f:
                await f.write(file_content)
            
            return True, "File saved successfully", file_path
            
        except Exception as e:
            return False, f"Failed to save file: {str(e)}", None
    
    def get_audio_info(self, file_path: str) -> Dict[str, Any]:
        """Extract audio file information"""
        try:
            # Use librosa to get audio info
            y, sr = librosa.load(file_path, sr=None)
            duration = librosa.get_duration(y=y, sr=sr)
            
            # Get file size
            file_size = os.path.getsize(file_path)
            
            # Try to get more detailed info with pydub
            try:
                audio = AudioSegment.from_file(file_path)
                channels = audio.channels
                sample_rate = audio.frame_rate
                format_name = file_path.split('.')[-1].lower()
            except:
                channels = 1
                sample_rate = sr
                format_name = file_path.split('.')[-1].lower()
            
            return {
                "duration_seconds": duration,
                "sample_rate": sample_rate,
                "channels": channels,
                "file_size": file_size,
                "format": format_name
            }
            
        except Exception as e:
            print(f"Error getting audio info: {e}")
            return {
                "duration_seconds": None,
                "sample_rate": None,
                "channels": None,
                "file_size": os.path.getsize(file_path) if os.path.exists(file_path) else 0,
                "format": file_path.split('.')[-1].lower() if '.' in file_path else "unknown"
            }
    
    def create_transcription_record(self, user_id: int, filename: str, file_path: str, audio_info: Dict[str, Any], settings: TranscriptionSettings) -> SpeechTranscription:
        """Create initial transcription record in database"""
        try:
            transcription = SpeechTranscription(
                user_id=user_id,
                original_filename=filename,
                file_path=file_path,
                file_size=audio_info["file_size"],
                duration_seconds=audio_info["duration_seconds"],
                sample_rate=audio_info["sample_rate"],
                channels=audio_info["channels"],
                format=audio_info["format"],
                processing_status="pending",
                processing_engine=settings.engine,
                settings_json=json.dumps(settings.dict()),
                language_detected=settings.language
            )
            
            self.db.add(transcription)
            self.db.commit()
            self.db.refresh(transcription)
            
            # Log history
            self.log_transcription_action(user_id, transcription.id, "created", "Transcription job created")
            
            return transcription
            
        except Exception as e:
            self.db.rollback()
            print(f"Error creating transcription record: {e}")
            raise e
    
    async def process_transcription(self, transcription_id: int) -> bool:
        """Process audio transcription"""
        try:
            # Get transcription record
            transcription = self.db.query(SpeechTranscription).filter(
                SpeechTranscription.id == transcription_id
            ).first()
            
            if not transcription:
                return False
            
            # Update status to processing
            transcription.processing_status = "processing"
            self.db.commit()
            
            start_time = time.time()
            
            # Get settings
            settings = json.loads(transcription.settings_json) if transcription.settings_json else {}
            engine = settings.get("engine", "whisper")
            
            # Process based on engine
            if engine == "whisper" and self.whisper_model:
                result = await self._transcribe_with_whisper(transcription.file_path, settings)
            else:
                result = await self._transcribe_with_speech_recognition(transcription.file_path, settings)
            
            processing_time = time.time() - start_time
            
            if result["success"]:
                # Update transcription with results
                transcription.transcription_text = result["text"]
                transcription.confidence_score = result.get("confidence")
                transcription.language_detected = result.get("language") or transcription.language_detected
                transcription.processing_status = "completed"
                transcription.processing_time_seconds = processing_time
                transcription.completed_at = datetime.utcnow()
                transcription.error_message = None
            else:
                # Update with error
                transcription.processing_status = "failed"
                transcription.error_message = result["error"]
                transcription.processing_time_seconds = processing_time
            
            transcription.updated_at = datetime.utcnow()
            self.db.commit()
            
            # Log completion
            action = "completed" if result["success"] else "failed"
            self.log_transcription_action(
                transcription.user_id, 
                transcription_id, 
                action, 
                f"Processing {action} in {processing_time:.2f}s"
            )
            
            return result["success"]
            
        except Exception as e:
            # Update transcription with error
            try:
                transcription = self.db.query(SpeechTranscription).filter(
                    SpeechTranscription.id == transcription_id
                ).first()
                if transcription:
                    transcription.processing_status = "failed"
                    transcription.error_message = str(e)
                    transcription.updated_at = datetime.utcnow()
                    self.db.commit()
            except:
                pass
            
            print(f"Error processing transcription {transcription_id}: {e}")
            return False
    
    async def _transcribe_with_whisper(self, file_path: str, settings: Dict[str, Any]) -> Dict[str, Any]:
        """Transcribe using Whisper"""
        try:
            if not self.whisper_model:
                return {"success": False, "error": "Whisper model not available"}
            
            # Transcribe
            result = self.whisper_model.transcribe(
                file_path,
                language=settings.get("language"),
                verbose=False
            )
            
            return {
                "success": True,
                "text": result["text"].strip(),
                "language": result.get("language"),
                "confidence": None  # Whisper doesn't return confidence scores
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _transcribe_with_speech_recognition(self, file_path: str, settings: Dict[str, Any]) -> Dict[str, Any]:
        """Transcribe using SpeechRecognition library"""
        try:
            # Convert to WAV if needed
            wav_path = await self._convert_to_wav(file_path)
            
            # Load audio
            with sr.AudioFile(wav_path) as source:
                audio = self.recognizer.record(source)
            
            # Transcribe
            try:
                # Try Google Web Speech API (free tier)
                text = self.recognizer.recognize_google(
                    audio,
                    language=settings.get("language", "en-US")
                )
                
                return {
                    "success": True,
                    "text": text,
                    "language": settings.get("language", "en-US"),
                    "confidence": None
                }
                
            except sr.UnknownValueError:
                return {"success": False, "error": "Could not understand audio"}
            except sr.RequestError as e:
                return {"success": False, "error": f"Recognition service error: {e}"}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _convert_to_wav(self, file_path: str) -> str:
        """Convert audio file to WAV format"""
        try:
            if file_path.lower().endswith('.wav'):
                return file_path
            
            # Create temporary WAV file
            wav_path = file_path.rsplit('.', 1)[0] + '_converted.wav'
            
            # Convert using pydub
            audio = AudioSegment.from_file(file_path)
            audio.export(wav_path, format="wav")
            
            return wav_path
            
        except Exception as e:
            print(f"Error converting to WAV: {e}")
            raise e
    
    def get_transcription_by_id(self, transcription_id: int, user_id: int) -> Optional[SpeechTranscription]:
        """Get transcription by ID for specific user"""
        return self.db.query(SpeechTranscription).filter(
            SpeechTranscription.id == transcription_id,
            SpeechTranscription.user_id == user_id
        ).first()
    
    def get_user_transcriptions(self, user_id: int, page: int = 1, page_size: int = 20) -> Tuple[List[SpeechTranscription], int]:
        """Get user's transcriptions with pagination"""
        try:
            # Get total count
            total_count = self.db.query(SpeechTranscription).filter(
                SpeechTranscription.user_id == user_id
            ).count()
            
            # Get paginated results
            offset = (page - 1) * page_size
            transcriptions = self.db.query(SpeechTranscription).filter(
                SpeechTranscription.user_id == user_id
            ).order_by(SpeechTranscription.created_at.desc()).offset(offset).limit(page_size).all()
            
            return transcriptions, total_count
            
        except Exception as e:
            print(f"Error getting user transcriptions: {e}")
            return [], 0
    
    def log_transcription_action(self, user_id: int, transcription_id: int, action: str, details: str = None):
        """Log transcription action to history"""
        try:
            history = TranscriptionHistory(
                user_id=user_id,
                transcription_id=transcription_id,
                action=action,
                action_details=details
            )
            
            self.db.add(history)
            self.db.commit()
            
        except Exception as e:
            print(f"Error logging transcription action: {e}")
    
    def delete_transcription(self, transcription_id: int, user_id: int) -> Tuple[bool, str]:
        """Delete transcription and associated files"""
        try:
            transcription = self.get_transcription_by_id(transcription_id, user_id)
            if not transcription:
                return False, "Transcription not found"
            
            # Delete file from filesystem
            try:
                if os.path.exists(transcription.file_path):
                    os.remove(transcription.file_path)
                
                # Also delete converted WAV file if exists
                wav_path = transcription.file_path.rsplit('.', 1)[0] + '_converted.wav'
                if os.path.exists(wav_path):
                    os.remove(wav_path)
            except Exception as e:
                print(f"Error deleting files: {e}")
            
            # Delete from database
            self.db.delete(transcription)
            self.db.commit()
            
            # Log deletion
            self.log_transcription_action(user_id, transcription_id, "deleted", "Transcription deleted by user")
            
            return True, "Transcription deleted successfully"
            
        except Exception as e:
            self.db.rollback()
            print(f"Error deleting transcription: {e}")
            return False, f"Failed to delete transcription: {str(e)}"
    
    def get_user_stats(self, user_id: int) -> Dict[str, Any]:
        """Get user's transcription statistics"""
        try:
            from sqlalchemy import func
            
            # Basic stats
            stats = self.db.query(
                func.count(SpeechTranscription.id).label('total_count'),
                func.sum(SpeechTranscription.duration_seconds).label('total_duration'),
                func.sum(SpeechTranscription.file_size).label('total_size'),
                func.avg(SpeechTranscription.confidence_score).label('avg_confidence')
            ).filter(SpeechTranscription.user_id == user_id).first()
            
            # This month count
            this_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            this_month_count = self.db.query(SpeechTranscription).filter(
                SpeechTranscription.user_id == user_id,
                SpeechTranscription.created_at >= this_month
            ).count()
            
            # Success rate
            completed_count = self.db.query(SpeechTranscription).filter(
                SpeechTranscription.user_id == user_id,
                SpeechTranscription.processing_status == "completed"
            ).count()
            
            success_rate = (completed_count / stats.total_count * 100) if stats.total_count > 0 else 0
            
            return {
                "total_transcriptions": stats.total_count or 0,
                "total_duration_minutes": round((stats.total_duration or 0) / 60, 2),
                "total_file_size_mb": round((stats.total_size or 0) / (1024*1024), 2),
                "average_confidence": round(stats.avg_confidence or 0, 2),
                "success_rate": round(success_rate, 2),
                "this_month_count": this_month_count
            }
            
        except Exception as e:
            print(f"Error getting user stats: {e}")
            return {
                "total_transcriptions": 0,
                "total_duration_minutes": 0,
                "total_file_size_mb": 0,
                "average_confidence": 0,
                "success_rate": 0,
                "this_month_count": 0
            }
    
    async def process_audio_buffer(audio_buffer, session_id, chunk_id, language, engine):
        """Process accumulated audio buffer for transcription without temporary files"""
        
        try:
            # Combine audio chunks
            combined_audio = b''.join(audio_buffer)
            
            if len(combined_audio) < 1000:  # Skip very small buffers
                return None
            
            print(f"Processing {len(combined_audio)} bytes of audio data for session {session_id}")
            
            # Use thread executor to avoid blocking
            loop = asyncio.get_event_loop()
            
            if engine == TranscriptionEngine.WHISPER and WHISPER_AVAILABLE:
                result = await loop.run_in_executor(
                    executor,
                    process_webm_audio_with_whisper,
                    combined_audio,
                    language,
                    session_id,
                    chunk_id
                )
                
                if result and result.get("text", "").strip():
                    return {
                        "text": result["text"].strip(),
                        "confidence": 0.8,
                        "language": result.get("language", language)
                    }
            
            elif engine == TranscriptionEngine.GOOGLE and SPEECH_RECOGNITION_AVAILABLE:
                result = await loop.run_in_executor(
                    executor,
                    process_webm_audio_with_google,
                    combined_audio,
                    language,
                    session_id,
                    chunk_id
                )
                
                if result and result.get("text", "").strip():
                    return {
                        "text": result["text"],
                        "confidence": 0.8,
                        "language": language or "en"
                    }
        
        except Exception as e:
            print(f"Error processing audio buffer: {e}")
            return None
        
        return None

    def process_webm_audio_with_whisper(audio_data, language, session_id, chunk_id):
        """Process WebM audio with Whisper - runs in thread executor"""
        
        try:
            print(f"Whisper processing session {session_id}, chunk {chunk_id}")
            
            # Convert WebM to numpy array using pydub
            if not SPEECH_RECOGNITION_AVAILABLE:
                print("pydub not available")
                return None
            
            from pydub import AudioSegment
            
            # Load WebM data directly into AudioSegment
            try:
                audio_segment = AudioSegment.from_file(
                    io.BytesIO(audio_data), 
                    format="webm"
                )
            except Exception as e:
                print(f"Failed to load WebM data: {e}")
                # Try as raw audio data
                try:
                    # Assume it's raw PCM data
                    audio_segment = AudioSegment(
                        data=audio_data,
                        sample_width=2,  # 16-bit
                        frame_rate=16000,
                        channels=1
                    )
                except Exception as e2:
                    print(f"Failed to load as raw PCM: {e2}")
                    return None
            
            # Convert to optimal format for Whisper
            audio_segment = audio_segment.set_frame_rate(16000).set_channels(1)
            
            # Convert to numpy array
            audio_samples = np.array(audio_segment.get_array_of_samples())
            
            # Normalize to [-1, 1] range (Whisper expects this)
            if audio_samples.dtype == np.int16:
                audio_samples = audio_samples.astype(np.float32) / 32768.0
            elif audio_samples.dtype == np.int32:
                audio_samples = audio_samples.astype(np.float32) / 2147483648.0
            
            # Load model (with caching)
            if not hasattr(process_webm_audio_with_whisper, '_model'):
                print("Loading Whisper model...")
                process_webm_audio_with_whisper._model = whisper.load_model("base")
                print("Whisper model cached")
            
            model = process_webm_audio_with_whisper._model
            
            # Set language
            whisper_language = None
            if language and language.lower() not in ['english', 'en']:
                lang_map = {
                    'spanish': 'es', 'french': 'fr', 'german': 'de',
                    'italian': 'it', 'portuguese': 'pt', 'russian': 'ru',
                    'chinese': 'zh', 'japanese': 'ja', 'korean': 'ko'
                }
                whisper_language = lang_map.get(language.lower(), language.lower()[:2])
            
            # Transcribe directly from numpy array (no file needed!)
            result = model.transcribe(
                audio_samples,  # Pass numpy array directly
                language=whisper_language,
                verbose=False,
                fp16=False,
                condition_on_previous_text=False,
                temperature=0.0,
                no_speech_threshold=0.6,
                logprob_threshold=-1.0
            )
            
            print(f"Whisper result: '{result['text'][:50]}...'")
            return result
        
        except Exception as e:
            print(f"Whisper processing error: {e}")
            import traceback
            traceback.print_exc()
            return None

    def process_webm_audio_with_google(audio_data, language, session_id, chunk_id):
        """Process WebM audio with Google Speech Recognition - runs in thread executor"""
        try:
            print(f"Google processing session {session_id}, chunk {chunk_id}")

            if not SPEECH_RECOGNITION_AVAILABLE:
                return None

            import speech_recognition as sr
            from pydub import AudioSegment

            # Convert WebM to AudioSegment
            try:
                audio_segment = AudioSegment.from_file(
                    io.BytesIO(audio_data), 
                    format="webm"
                )
            except Exception as e:
                print(f"Failed to load WebM: {e}")
                return None

            # Optimize for Google Speech Recognition
            audio_segment = audio_segment.set_frame_rate(16000).set_channels(1)

            # Export to BytesIO buffer instead of temp file
            wav_buffer = io.BytesIO()
            audio_segment.export(wav_buffer, format="wav")
            wav_buffer.seek(0)

            # Now open the buffer for reading
            recognizer = sr.Recognizer()
            with sr.AudioFile(wav_buffer) as source:
                audio_data_sr = recognizer.record(source)

            # Set language
            google_language = 'en-US'
            if language:
                lang_map = {
                    'english': 'en-US', 'spanish': 'es-ES', 'french': 'fr-FR',
                    'german': 'de-DE', 'italian': 'it-IT', 'portuguese': 'pt-PT',
                    'russian': 'ru-RU', 'chinese': 'zh-CN', 'japanese': 'ja-JP',
                    'korean': 'ko-KR'
                }
                google_language = lang_map.get(language.lower(), 'en-US')

            text = recognizer.recognize_google(audio_data_sr, language=google_language)
            print(f"Google result: '{text[:50]}...'")

            return {"text": text}

        except Exception as e:
            print(f"Google processing error: {e}")
            return None
    
    import tempfile
    import os

    def process_streaming_audio_with_whisper(audio_data, language, session_id, chunk_id):
        import tempfile
        import os
        import numpy as np
        from pydub import AudioSegment

        try:
            print(f"Whisper processing streaming session {session_id}, chunk {chunk_id}")

            # Only try to decode as WebM if header is present
            if audio_data[:4] != b'\x1A\x45\xDF\xA3':
                print("Buffer does not start with WebM header, skipping decode.")
                return None

            # Write accumulated audio to a temp file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as tmp:
                tmp.write(audio_data)
                tmp_path = tmp.name

            try:
                audio_segment = AudioSegment.from_file(tmp_path, format="webm")
                print("Successfully loaded as WebM via temp file")
            except Exception as e:
                print(f"WebM loading failed: {e}")
                os.unlink(tmp_path)
                return None

            os.unlink(tmp_path)

            # Downsample to 16kHz mono for Whisper
            audio_segment = audio_segment.set_frame_rate(16000).set_channels(1)

            duration_ms = len(audio_segment)
            duration_seconds = duration_ms / 1000.0
            print(f"Audio duration: {duration_seconds:.2f} seconds")

            if duration_seconds < 0.3:
                print("Audio too short, skipping")
                return None

            # Always output float32 for Whisper
            audio_samples = np.array(audio_segment.get_array_of_samples()).astype(np.float32)
            if audio_segment.sample_width == 2:  # 16-bit PCM
                audio_samples /= 32768.0
            elif audio_segment.sample_width == 4:  # 32-bit PCM
                audio_samples /= 2147483648.0
            elif audio_segment.sample_width == 1:  # 8-bit PCM
                audio_samples = (audio_samples - 128) / 128.0

            # Load model (with caching)
            if not hasattr(process_streaming_audio_with_whisper, '_model'):
                print("Loading Whisper model...")
                import whisper
                process_streaming_audio_with_whisper._model = whisper.load_model("base")
                print("Whisper model cached")

            model = process_streaming_audio_with_whisper._model

            # Set language parameter
            whisper_language = None
            if language and language.lower() not in ['english', 'en']:
                lang_map = {
                    'spanish': 'es', 'french': 'fr', 'german': 'de',
                    'italian': 'it', 'portuguese': 'pt', 'russian': 'ru',
                    'chinese': 'zh', 'japanese': 'ja', 'korean': 'ko'
                }
                whisper_language = lang_map.get(language.lower(), language.lower()[:2])

            print(f"Starting Whisper transcription (language: {whisper_language or 'auto'})")

            result = model.transcribe(
                audio_samples,
                language=whisper_language,
                verbose=False,
                fp16=False,
                condition_on_previous_text=False,
                temperature=0.0,
                no_speech_threshold=0.5,
                logprob_threshold=-0.8,
                compression_ratio_threshold=2.4,
                word_timestamps=False,
            )

            text = result['text'].strip()
            print(f"Whisper result ({duration_seconds:.1f}s): '{text[:100]}{'...' if len(text) > 100 else ''}'")

            if text and len(text) > 1 and text not in ['...', '.', ' ']:
                return {
                    'text': text,
                    'language': result.get('language', language or 'en'),
                    'duration': duration_seconds
                }
            else:
                print("No meaningful transcription result")
                return None

        except Exception as e:
            print(f"Whisper streaming processing error: {e}")
            import traceback
            traceback.print_exc()
            return None