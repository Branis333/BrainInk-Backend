import os
import tempfile
import librosa
import soundfile as sf
from pydub import AudioSegment
from schemas.speech_schemas import TranscriptionSettings, ProcessingStatus
from typing import Optional, Tuple, Dict, Any, List
import json
import time
import asyncio
import aiofiles
import io
import threading
from concurrent.futures import ThreadPoolExecutor
import numpy as np

from utils.speech_flags import WHISPER_AVAILABLE, SPEECH_RECOGNITION_AVAILABLE

if WHISPER_AVAILABLE:
    import whisper

if SPEECH_RECOGNITION_AVAILABLE:
    import speech_recognition as sr

executor = ThreadPoolExecutor(max_workers=2)
WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "tiny")

class SpeechService:
    _whisper_model = None

    def __init__(self):
        self.upload_dir = os.getenv("UPLOAD_DIR", "uploads/audio")
        self.max_file_size = int(os.getenv("MAX_FILE_SIZE_MB", 100)) * 1024 * 1024
        self.max_duration = int(os.getenv("MAX_DURATION_MINUTES", 30)) * 60
        os.makedirs(self.upload_dir, exist_ok=True)
        if SPEECH_RECOGNITION_AVAILABLE:
            self.recognizer = sr.Recognizer()

    @classmethod
    def get_whisper_model(cls):
        if cls._whisper_model is None and WHISPER_AVAILABLE:
            print(f"Loading Whisper model ({WHISPER_MODEL_SIZE})...")
            cls._whisper_model = whisper.load_model(WHISPER_MODEL_SIZE)
            print("Whisper model loaded successfully")
        return cls._whisper_model

    @classmethod
    def clear_memory(cls):
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass
        import gc
        gc.collect()

    def transcribe_with_whisper(self, audio_path: str, language: Optional[str] = None):
        try:
            model = self.get_whisper_model()
            if not model:
                return {"success": False, "error": "Whisper model not available"}
            whisper_language = None
            if language and language.lower() not in ['english', 'en']:
                lang_map = {
                    'spanish': 'es',
                    'french': 'fr',
                    'german': 'de',
                    'italian': 'it',
                    'portuguese': 'pt',
                    'russian': 'ru',
                    'chinese': 'zh',
                    'japanese': 'ja',
                    'korean': 'ko',
                    'arabic': 'ar',
                    'swahili': 'sw',
                    'afrikaans': 'af'
                }
                whisper_language = lang_map.get(language.lower(), language.lower()[:2])
            result = model.transcribe(
                audio_path,
                language=whisper_language,
                verbose=False,
                fp16=False,
                condition_on_previous_text=False,
                temperature=0.0
            )
            self.clear_memory()
            return {
                "success": True,
                "text": result["text"].strip(),
                "language": result.get("language"),
                "confidence": None
            }
        except Exception as e:
            self.clear_memory()
            return {"success": False, "error": str(e)}

    async def save_audio_file(self, file, user_id: int) -> Tuple[bool, str, Optional[str]]:
        try:
            file_content = await file.read()
            if len(file_content) > self.max_file_size:
                return False, f"File too large. Maximum size: {self.max_file_size // (1024*1024)}MB", None
            timestamp = int(time.time())
            file_extension = os.path.splitext(file.filename)[1].lower()
            safe_filename = f"user_{user_id}_{timestamp}_{file.filename}"
            file_path = os.path.join(self.upload_dir, safe_filename)
            async with aiofiles.open(file_path, 'wb') as f:
                await f.write(file_content)
            return True, "File saved successfully", file_path
        except Exception as e:
            return False, f"Failed to save file: {str(e)}", None

    def get_audio_info(self, file_path: str) -> Dict[str, Any]:
        try:
            y, sr = librosa.load(file_path, sr=None)
            duration = librosa.get_duration(y=y, sr=sr)
            file_size = os.path.getsize(file_path)
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

    # --- Streaming and chunked audio processing methods (no DB required) ---

    @staticmethod
    def process_webm_audio_with_whisper(audio_data, language, session_id, chunk_id):
        try:
            print(f"Whisper processing session {session_id}, chunk {chunk_id}")
            from pydub import AudioSegment
            audio_segment = AudioSegment.from_file(io.BytesIO(audio_data), format="webm")
            audio_segment = audio_segment.set_frame_rate(16000).set_channels(1)
            audio_samples = np.array(audio_segment.get_array_of_samples())
            if audio_samples.dtype == np.int16:
                audio_samples = audio_samples.astype(np.float32) / 32768.0
            elif audio_samples.dtype == np.int32:
                audio_samples = audio_samples.astype(np.float32) / 2147483648.0
            if not hasattr(SpeechService.process_webm_audio_with_whisper, '_model'):
                import whisper
                SpeechService.process_webm_audio_with_whisper._model = whisper.load_model("base")
            model = SpeechService.process_webm_audio_with_whisper._model
            whisper_language = None
            if language and language.lower() not in ['english', 'en']:
                lang_map = {
                    'spanish': 'es', 'french': 'fr', 'german': 'de',
                    'italian': 'it', 'portuguese': 'pt', 'russian': 'ru',
                    'chinese': 'zh', 'japanese': 'ja', 'korean': 'ko'
                }
                whisper_language = lang_map.get(language.lower(), language.lower()[:2])
            result = model.transcribe(
                audio_samples,
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

    @staticmethod
    def process_webm_audio_with_google(audio_data, language, session_id, chunk_id):
        try:
            print(f"Google processing session {session_id}, chunk {chunk_id}")
            if not SPEECH_RECOGNITION_AVAILABLE:
                return None
            import speech_recognition as sr
            from pydub import AudioSegment
            audio_segment = AudioSegment.from_file(io.BytesIO(audio_data), format="webm")
            audio_segment = audio_segment.set_frame_rate(16000).set_channels(1)
            wav_buffer = io.BytesIO()
            audio_segment.export(wav_buffer, format="wav")
            wav_buffer.seek(0)
            recognizer = sr.Recognizer()
            with sr.AudioFile(wav_buffer) as source:
                audio_data_sr = recognizer.record(source)
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

    @staticmethod
    def process_streaming_audio_with_whisper(audio_data, language, session_id, chunk_id, previous_text="", audio_format="audio/webm"):
        """Process streaming audio with Whisper - improved format handling"""
        try:
            print(f"Whisper processing accumulated audio for session {session_id}, chunk {chunk_id}")
            print(f"Audio data size: {len(audio_data)} bytes")
            print(f"Audio format: {audio_format}")
            print(f"Previous text: '{previous_text}' ({len(previous_text)} chars total)")
            
            if len(audio_data) < 2000:  # Skip very small chunks
                print("Audio data too small, skipping")
                return None
            
            # Determine format from audio_format parameter
            format_ext = "webm"  # default
            pydub_format = "webm"
            
            if "webm" in audio_format.lower():
                format_ext = "webm"
                pydub_format = "webm"
            elif "ogg" in audio_format.lower():
                format_ext = "ogg"
                pydub_format = "ogg"
            elif "mp4" in audio_format.lower():
                format_ext = "mp4"
                pydub_format = "mp4"
            elif "wav" in audio_format.lower():
                format_ext = "wav"
                pydub_format = "wav"
            
            print(f"Using format: {pydub_format} (.{format_ext})")
            
            # Check for proper headers based on format
            has_proper_header = False
            if format_ext == "webm":
                has_proper_header = audio_data.startswith(b'\x1a\x45\xdf\xa3') or b'webm' in audio_data[:100].lower()
            elif format_ext == "ogg":
                has_proper_header = audio_data.startswith(b'OggS')
            elif format_ext == "wav":
                has_proper_header = audio_data.startswith(b'RIFF')
            elif format_ext == "mp4":
                has_proper_header = b'ftyp' in audio_data[:32] or b'moov' in audio_data[:100]
            
            print(f"Proper {format_ext} header found: {has_proper_header}")
            
            if not has_proper_header:
                print("No proper header found - attempting direct processing anyway")
                print(f"First 20 bytes: {audio_data[:20]}")
            
            audio_segment = None
            success = False
            
            # Try to process with the specified format first
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=f".{format_ext}") as tmp:
                    tmp.write(audio_data)
                    tmp_path = tmp.name
                
                # Try loading with the specified format
                try:
                    audio_segment = AudioSegment.from_file(tmp_path, format=pydub_format)
                    print(f"Successfully loaded as {pydub_format}")
                    success = True
                except Exception as format_error:
                    print(f"Failed to load as {pydub_format}: {format_error}")
                    
                    # Try without specifying format (let pydub auto-detect)
                    try:
                        audio_segment = AudioSegment.from_file(tmp_path)
                        print("Successfully loaded with auto-detection")
                        success = True
                    except Exception as auto_error:
                        print(f"Auto-detection failed: {auto_error}")
                        
                        # Try all common formats as fallback
                        fallback_formats = ['webm', 'ogg', 'wav', 'mp4', 'm4a']
                        for fmt in fallback_formats:
                            if fmt == pydub_format:
                                continue  # Already tried this one
                            try:
                                # Create new temp file with different extension
                                new_path = tmp_path.replace(f'.{format_ext}', f'.{fmt}')
                                with open(new_path, 'wb') as f:
                                    f.write(audio_data)
                                
                                audio_segment = AudioSegment.from_file(new_path, format=fmt)
                                print(f"Successfully loaded as {fmt} (fallback)")
                                success = True
                                
                                # Clean up the new temp file
                                if os.path.exists(new_path):
                                    os.unlink(new_path)
                                break
                                
                            except Exception as fmt_error:
                                print(f"Failed to load as {fmt}: {fmt_error}")
                                if 'new_path' in locals() and os.path.exists(new_path):
                                    try:
                                        os.unlink(new_path)
                                    except:
                                        pass
                                continue
                
                # Clean up main temp file
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
                    
            except Exception as e:
                print(f"Error creating temp file: {e}")
                return None
            
            if not success or audio_segment is None:
                print("All audio format attempts failed")
                return None
            
            # Downsample to 16kHz mono for Whisper
            audio_segment = audio_segment.set_frame_rate(16000).set_channels(1)
            
            duration_ms = len(audio_segment)
            duration_seconds = duration_ms / 1000.0
            print(f"Audio duration: {duration_seconds:.2f} seconds")
            
            # Skip very short audio segments
            if duration_seconds < 1.0:  # Require at least 1 second for better accuracy
                print("Audio too short for transcription, skipping")
                return None
            
            # Convert to float32 for Whisper
            audio_samples = np.array(audio_segment.get_array_of_samples()).astype(np.float32)
            if audio_segment.sample_width == 2:  # 16-bit PCM
                audio_samples /= 32768.0
            elif audio_segment.sample_width == 4:  # 32-bit PCM
                audio_samples /= 2147483648.0
            elif audio_segment.sample_width == 1:  # 8-bit PCM
                audio_samples = (audio_samples - 128) / 128.0
            
            # Load model (with caching)
            if not hasattr(SpeechService.process_streaming_audio_with_whisper, '_model'):
                print(f"Loading Whisper model ({WHISPER_MODEL_SIZE})...")
                import whisper
                SpeechService.process_streaming_audio_with_whisper._model = whisper.load_model(WHISPER_MODEL_SIZE)
                print("Whisper model cached")
            
            model = SpeechService.process_streaming_audio_with_whisper._model
            
            # Set language parameter with all supported languages
            whisper_language = None
            if language and language.lower() not in ['english', 'en']:
                lang_map = {
                    'spanish': 'es', 'french': 'fr', 'german': 'de',
                    'italian': 'it', 'portuguese': 'pt', 'russian': 'ru',
                    'chinese': 'zh', 'japanese': 'ja', 'korean': 'ko',
                    'arabic': 'ar', 'swahili': 'sw', 'afrikaans': 'af'
                }
                whisper_language = lang_map.get(language.lower(), language.lower()[:2])
            
            print(f"Starting Whisper transcription (language: {whisper_language or 'auto'})")
            
            # Use more sensitive settings for live transcription
            result = model.transcribe(
                audio_samples,
                language=whisper_language,
                verbose=False,
                fp16=False,
                condition_on_previous_text=False,
                temperature=0.0,
                no_speech_threshold=0.4,  # More sensitive to speech
                logprob_threshold=-1.0,   # More lenient
                compression_ratio_threshold=2.4,
                word_timestamps=False,
            )
            
            full_text = result['text'].strip()
            print(f"Full transcription result: '{full_text}'")
            
            # Deduplicate text by removing overlap with previous text
            new_text = SpeechService._extract_new_text(full_text, previous_text)
            print(f"New text after deduplication: '{new_text}'")
            
            # Return result for any meaningful new text
            if new_text and len(new_text) > 0 and new_text not in ['...', '.', ' ', 'you', 'Thank you.']:
                return {
                    'text': new_text,
                    'full_text': full_text,  # Include full text for debugging
                    'language': result.get('language', language or 'en'),
                    'duration': duration_seconds,
                    'confidence': 0.8  # Default confidence for Whisper
                }
            else:
                print("No meaningful transcription result")
                return None
                
        except Exception as e:
            print(f"Whisper streaming processing error: {e}")
            import traceback
            traceback.print_exc()
            return None

    @staticmethod
    def process_webm_audio_with_google(audio_data, language, session_id, chunk_id):
        """Process WebM audio with Google Speech Recognition - runs in thread executor"""
        try:
            print(f"Google processing session {session_id}, chunk {chunk_id}")

            if not SPEECH_RECOGNITION_AVAILABLE:
                return None

            import speech_recognition as sr

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

            # Set language with Afrikaans support
            google_language = 'en-US'
            if language:
                lang_map = {
                    'english': 'en-US', 'spanish': 'es-ES', 'french': 'fr-FR',
                    'german': 'de-DE', 'italian': 'it-IT', 'portuguese': 'pt-PT',
                    'russian': 'ru-RU', 'chinese': 'zh-CN', 'japanese': 'ja-JP',
                    'korean': 'ko-KR', 'arabic': 'ar-SA', 'swahili': 'sw-KE',
                    'afrikaans': 'af-ZA'  # Added Afrikaans
                }
                google_language = lang_map.get(language.lower(), 'en-US')

            text = recognizer.recognize_google(audio_data_sr, language=google_language)
            print(f"Google result: '{text[:50]}...'")

            return {"text": text}

        except Exception as e:
            print(f"Google processing error: {e}")
            return None

    @staticmethod
    def process_incremental_audio_with_whisper(audio_data, language, session_id, chunk_id, previous_text=""):
        """Process incremental audio chunk with Whisper - with text deduplication"""
        try:
            print(f"Whisper processing incremental audio for session {session_id}, chunk {chunk_id}")
            print(f"New audio data size: {len(audio_data)} bytes")
            
            # Check if this looks like a valid WebM file
            if len(audio_data) < 1000:
                print("Audio data too small, skipping")
                return None
                
            # Check for WebM header
            if audio_data[:4] != b'\x1A\x45\xDF\xA3':
                print("No WebM header found - invalid WebM data")
                return None
            
            # Write audio to a temp file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as tmp:
                tmp.write(audio_data)
                tmp_path = tmp.name
            
            try:
                # Load as WebM
                audio_segment = AudioSegment.from_file(tmp_path, format="webm")
                print("Successfully loaded incremental WebM data")
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
            
            # Require at least 0.3 seconds of audio for meaningful transcription
            if duration_seconds < 0.3:
                print("Audio too short for transcription, skipping")
                return None
            
            # Convert to float32 for Whisper
            audio_samples = np.array(audio_segment.get_array_of_samples()).astype(np.float32)
            if audio_segment.sample_width == 2:  # 16-bit PCM
                audio_samples /= 32768.0
            elif audio_segment.sample_width == 4:  # 32-bit PCM
                audio_samples /= 2147483648.0
            elif audio_segment.sample_width == 1:  # 8-bit PCM
                audio_samples = (audio_samples - 128) / 128.0
            
            # Load model (with caching)
            if not hasattr(SpeechService.process_incremental_audio_with_whisper, '_model'):
                print(f"Loading Whisper model ({WHISPER_MODEL_SIZE})...")
                import whisper
                SpeechService.process_incremental_audio_with_whisper._model = whisper.load_model(WHISPER_MODEL_SIZE)
                print("Whisper model cached for incremental processing")
            
            model = SpeechService.process_incremental_audio_with_whisper._model
            
            # Set language parameter
            whisper_language = None
            if language and language.lower() not in ['english', 'en']:
                lang_map = {
                    'spanish': 'es', 'french': 'fr', 'german': 'de',
                    'italian': 'it', 'portuguese': 'pt', 'russian': 'ru',
                    'chinese': 'zh', 'japanese': 'ja', 'korean': 'ko',
                    'arabic': 'ar', 'swahili': 'sw', 'afrikaans': 'af'
                }
                whisper_language = lang_map.get(language.lower(), language.lower()[:2])
            
            print(f"Starting incremental Whisper transcription (language: {whisper_language or 'auto'})")
            
            # Use optimized settings for incremental transcription
            result = model.transcribe(
                audio_samples,
                language=whisper_language,
                verbose=False,
                fp16=False,
                condition_on_previous_text=False,  # Very important: don't condition on previous text
                temperature=0.0,
                no_speech_threshold=0.3,  # More sensitive to speech
                logprob_threshold=-1.0,   # More lenient
                compression_ratio_threshold=2.4,
                word_timestamps=False,
                initial_prompt="",  # No prompt to avoid context bleeding
            )
            
            full_text = result['text'].strip()
            print(f"Full transcription result: '{full_text}'")
            
            # Deduplicate text by removing overlap with previous text
            new_text = SpeechService._extract_new_text(full_text, previous_text)
            
            print(f"New text after deduplication: '{new_text}'")
            
            # Return result for any meaningful new text
            if new_text and len(new_text) > 0 and new_text not in ['...', '.', ' ', 'you', 'Thank you.']:
                return {
                    'text': new_text,
                    'full_text': full_text,  # Include full text for debugging
                    'language': result.get('language', language or 'en'),
                    'duration': duration_seconds,
                    'confidence': 0.8  # Default confidence for Whisper
                }
            else:
                print("No meaningful new text after deduplication")
                return None
                
        except Exception as e:
            print(f"Incremental Whisper processing error: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    @staticmethod
    def _extract_new_text(full_text: str, previous_text: str) -> str:
        """Extract new text from full transcription by removing overlap with previous text"""
        if not previous_text:
            return full_text
        
        # Convert to lowercase for comparison
        full_lower = full_text.lower().strip()
        prev_lower = previous_text.lower().strip()
        
        # If full text is completely contained in previous text, no new content
        if full_lower in prev_lower:
            return ""
        
        # If previous text is completely contained in full text, extract the new part
        if prev_lower in full_lower:
            # Find where the previous text ends in the full text
            prev_end_index = full_lower.find(prev_lower) + len(prev_lower)
            new_text = full_text[prev_end_index:].strip()
            return new_text
        
        # Try to find the best overlap by checking word boundaries
        full_words = full_text.split()
        prev_words = previous_text.split()
        
        if not prev_words:
            return full_text
        
        # Look for the longest suffix of previous_text that matches a prefix of full_text
        best_overlap = 0
        for i in range(1, min(len(prev_words), len(full_words)) + 1):
            if prev_words[-i:] == full_words[:i]:
                best_overlap = i
        
        # Extract new words after the overlap
        if best_overlap > 0:
            new_words = full_words[best_overlap:]
            return " ".join(new_words)
        else:
            # No clear overlap found, return the full text as it might be entirely new
            return full_text
    
    @staticmethod
    def process_pcm_audio_with_whisper(audio_data, language, session_id, chunk_id, previous_text="", sample_rate=16000, channels=1, bits_per_sample=16):
        """Process raw PCM audio with Whisper - direct processing without file format issues"""
        try:
            print(f"Whisper processing PCM audio for session {session_id}, chunk {chunk_id}")
            print(f"PCM data size: {len(audio_data)} bytes")
            print(f"Sample rate: {sample_rate}, Channels: {channels}, Bits: {bits_per_sample}")
            print(f"Previous text: '{previous_text}' ({len(previous_text)} chars total)")
            
            if len(audio_data) < 4000:  # Skip very small chunks (less than ~0.125s at 16kHz)
                print("PCM data too small, skipping")
                return None
            
            # Convert bytes to numpy array based on bits per sample
            if bits_per_sample == 16:
                # Convert from bytes to int16 array
                audio_samples = np.frombuffer(audio_data, dtype=np.int16)
                # Convert to float32 for Whisper (normalize to [-1, 1])
                audio_samples = audio_samples.astype(np.float32) / 32768.0
            elif bits_per_sample == 32:
                # Convert from bytes to int32 array
                audio_samples = np.frombuffer(audio_data, dtype=np.int32)
                # Convert to float32 for Whisper (normalize to [-1, 1])
                audio_samples = audio_samples.astype(np.float32) / 2147483648.0
            else:
                print(f"Unsupported bits per sample: {bits_per_sample}")
                return None
            
            # Handle multi-channel audio by taking the first channel
            if channels > 1:
                # Reshape and take first channel
                audio_samples = audio_samples.reshape(-1, channels)[:, 0]
            
            duration_seconds = len(audio_samples) / sample_rate
            print(f"PCM audio duration: {duration_seconds:.2f} seconds")
            
            # Skip very short audio segments
            if duration_seconds < 0.5:  # Require at least 0.5 seconds
                print("PCM audio too short for transcription, skipping")
                return None
            
            # Resample to 16kHz if needed (Whisper's expected sample rate)
            if sample_rate != 16000:
                # Simple linear interpolation resampling
                target_length = int(len(audio_samples) * 16000 / sample_rate)
                indices = np.linspace(0, len(audio_samples) - 1, target_length)
                audio_samples = np.interp(indices, np.arange(len(audio_samples)), audio_samples)
                print(f"Resampled from {sample_rate}Hz to 16kHz")
            
            # Load model (with caching)
            if not hasattr(SpeechService.process_pcm_audio_with_whisper, '_model'):
                print(f"Loading Whisper model ({WHISPER_MODEL_SIZE})...")
                import whisper
                SpeechService.process_pcm_audio_with_whisper._model = whisper.load_model(WHISPER_MODEL_SIZE)
                print("Whisper model cached for PCM processing")
            
            model = SpeechService.process_pcm_audio_with_whisper._model
            
            # Set language parameter
            whisper_language = None
            if language and language.lower() not in ['english', 'en']:
                lang_map = {
                    'spanish': 'es', 'french': 'fr', 'german': 'de',
                    'italian': 'it', 'portuguese': 'pt', 'russian': 'ru',
                    'chinese': 'zh', 'japanese': 'ja', 'korean': 'ko',
                    'arabic': 'ar', 'swahili': 'sw', 'afrikaans': 'af'
                }
                whisper_language = lang_map.get(language.lower(), language.lower()[:2])
            
            print(f"Starting Whisper transcription on PCM data (language: {whisper_language or 'auto'})")
            
            # Use optimized settings for PCM transcription
            result = model.transcribe(
                audio_samples,
                language=whisper_language,
                verbose=False,
                fp16=False,
                condition_on_previous_text=False,
                temperature=0.0,
                no_speech_threshold=0.4,  # More sensitive to speech
                logprob_threshold=-1.0,   # More lenient
                compression_ratio_threshold=2.4,
                word_timestamps=False,
            )
            
            full_text = result['text'].strip()
            print(f"PCM transcription result: '{full_text}'")
            
            # Deduplicate text by removing overlap with previous text
            new_text = SpeechService._extract_new_text(full_text, previous_text)
            print(f"New text after deduplication: '{new_text}'")
            
            # Return result for any meaningful new text
            if new_text and len(new_text) > 0 and new_text not in ['...', '.', ' ', 'you', 'Thank you.']:
                return {
                    'text': new_text,
                    'full_text': full_text,  # Include full text for debugging
                    'language': result.get('language', language or 'en'),
                    'duration': duration_seconds,
                    'confidence': 0.8  # Default confidence for Whisper
                }
            else:
                print("No meaningful PCM transcription result")
                return None
                
        except Exception as e:
            print(f"PCM Whisper processing error: {e}")
            import traceback
            traceback.print_exc()
            return None