from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from enum import Enum
import io
import os
import tempfile
import librosa
import soundfile as sf
from pydub import AudioSegment
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

# Import Whisper if available
if WHISPER_AVAILABLE:
    import whisper

# Import SpeechRecognition if available
if SPEECH_RECOGNITION_AVAILABLE:
    import speech_recognition as sr

executor = ThreadPoolExecutor(max_workers=2)

# Use environment variable for Whisper model size
WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "tiny")

# Enums
class TranscriptionEngine(str, Enum):
    WHISPER = "whisper"
    GOOGLE = "google"
    MOCK = "mock"

class ProcessingStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class AudioFormat(str, Enum):
    MP3 = "mp3"
    WAV = "wav"
    M4A = "m4a"
    FLAC = "flac"
    OGG = "ogg"
    MP4 = "mp4"

# Request Models
class TranscriptionSettings(BaseModel):
    language: Optional[str] = Field(None, description="Language code (e.g., 'en', 'es')")
    engine: str = Field(default="whisper", description="Transcription engine to use")
    include_timestamps: bool = Field(default=False, description="Include timestamps in transcription")
    confidence_threshold: float = Field(default=0.5, ge=0.0, le=1.0, description="Minimum confidence threshold")
    max_speakers: Optional[int] = Field(None, gt=0, le=20, description="Maximum number of speakers for diarization")
    noise_reduction: bool = Field(default=False, description="Apply noise reduction")
    enhance_audio: bool = Field(default=False, description="Enhance audio quality")
    
    @field_validator('language')
    @classmethod
    def validate_language(cls, v):
        if v and len(v) < 2:
            raise ValueError('Language code must be at least 2 characters')
        return v

class QuickTranscriptionRequest(BaseModel):
    language: Optional[str] = None
    engine: TranscriptionEngine = TranscriptionEngine.WHISPER
    include_timestamps: bool = False

# Response Models
class AudioInfo(BaseModel):
    duration_seconds: Optional[float] = None
    sample_rate: Optional[int] = None
    channels: Optional[int] = None
    file_size: int
    format: str
    bitrate: Optional[int] = None

class TranscriptionSegment(BaseModel):
    start_time: float
    end_time: float
    text: str
    confidence: Optional[float] = None
    speaker: Optional[str] = None

class TranscriptionResponse(BaseModel):
    id: int
    user_id: int
    original_filename: str
    file_path: Optional[str] = None
    file_size: int
    duration_seconds: Optional[float] = None
    sample_rate: Optional[int] = None
    channels: Optional[int] = None
    format: str
    processing_status: str
    processing_engine: str
    transcription_text: Optional[str] = None
    confidence_score: Optional[float] = None
    language_detected: Optional[str] = None
    processing_time_seconds: Optional[float] = None
    settings_json: Optional[str] = None
    error_message: Optional[str] = None
    segments: Optional[List[TranscriptionSegment]] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class TranscriptionListResponse(BaseModel):
    transcriptions: List[TranscriptionResponse]
    total_count: int
    page: int
    page_size: int
    has_next: bool
    has_previous: bool = Field(default=False)
    
    @field_validator('has_previous')
    @classmethod
    def calculate_has_previous(cls, v, info):
        page = info.data.get('page', 1)
        return page > 1

class QuickTranscriptionResponse(BaseModel):
    text: str
    language_detected: Optional[str] = None
    confidence_score: Optional[float] = None
    processing_time_seconds: float
    audio_duration_seconds: Optional[float] = None
    engine_used: str
    segments: Optional[List[TranscriptionSegment]] = None

class UserTranscriptionStats(BaseModel):
    total_transcriptions: int = 0
    total_duration_minutes: float = 0.0
    total_file_size_mb: float = 0.0
    average_confidence: float = 0.0
    success_rate: float = 0.0
    this_month_count: int = 0
    favorite_language: Optional[str] = None
    most_used_engine: Optional[str] = None
    processing_time_stats: Dict[str, float] = Field(default_factory=dict)

class SupportedLanguage(BaseModel):
    code: str = Field(..., description="Language code (e.g., 'en', 'es')")
    name: str = Field(..., description="Language name in English")
    native_name: str = Field(..., description="Language name in native script")
    supported_engines: List[str] = Field(default_factory=list)
    quality_score: Optional[float] = Field(None, ge=0.0, le=1.0)

class ServiceCapabilities(BaseModel):
    supported_formats: List[str] = Field(default_factory=list)
    supported_languages: List[SupportedLanguage] = Field(default_factory=list)
    available_engines: List[str] = Field(default_factory=list)
    max_file_size_mb: int = 100
    max_duration_minutes: int = 30
    features: List[str] = Field(default_factory=list)
    version: str = "1.0.0"
    uptime: Optional[str] = None

class TranscriptionHistoryEntry(BaseModel):
    id: int
    user_id: int
    transcription_id: int
    action: str
    action_details: Optional[str] = None
    timestamp: datetime
    
    class Config:
        from_attributes = True

class BatchTranscriptionRequest(BaseModel):
    user_id: int
    files: List[str] = Field(..., description="List of file paths or identifiers")
    settings: TranscriptionSettings
    priority: int = Field(default=0, ge=0, le=10)
    callback_url: Optional[str] = None

class BatchTranscriptionResponse(BaseModel):
    batch_id: str
    status: str
    total_files: int
    completed_files: int
    failed_files: int
    estimated_completion_time: Optional[datetime] = None
    transcriptions: List[TranscriptionResponse] = Field(default_factory=list)

class ErrorResponse(BaseModel):
    error: str
    detail: str
    timestamp: datetime
    request_id: Optional[str] = None

class HealthCheckResponse(BaseModel):
    status: str
    service: str
    database: str
    database_test: Optional[str] = None
    upload_directory: Optional[str] = None
    whisper_available: bool = False
    speech_recognition_available: bool = False
    timestamp: str
    error: Optional[str] = None

# Webhook Models
class WebhookEvent(BaseModel):
    event_type: str = Field(..., description="Type of event (transcription_completed, transcription_failed, etc.)")
    transcription_id: int
    user_id: int
    timestamp: datetime
    data: Dict[str, Any] = Field(default_factory=dict)

class WebhookConfiguration(BaseModel):
    url: str = Field(..., description="Webhook URL")
    events: List[str] = Field(default_factory=list, description="Events to subscribe to")
    secret: Optional[str] = None
    active: bool = True

# Advanced Features
class SpeakerDiarizationSettings(BaseModel):
    enabled: bool = False
    min_speakers: int = Field(default=1, ge=1, le=20)
    max_speakers: int = Field(default=5, ge=1, le=20)
    
    @field_validator('max_speakers')
    @classmethod
    def validate_max_speakers(cls, v, info):
        min_speakers = info.data.get('min_speakers', 1)
        if v < min_speakers:
            raise ValueError('max_speakers must be greater than or equal to min_speakers')
        return v

class AudioPreprocessingSettings(BaseModel):
    noise_reduction: bool = False
    normalize_volume: bool = False
    remove_silence: bool = False
    enhance_speech: bool = False

class AdvancedTranscriptionSettings(TranscriptionSettings):
    speaker_diarization: SpeakerDiarizationSettings = Field(default_factory=SpeakerDiarizationSettings)
    audio_preprocessing: AudioPreprocessingSettings = Field(default_factory=AudioPreprocessingSettings)
    custom_vocabulary: List[str] = Field(default_factory=list)
    profanity_filter: bool = False
    output_format: str = Field(default="text", pattern=r"^(text|srt|vtt|json)$")  # Fixed: changed regex to pattern

# Analytics Models
class TranscriptionAnalytics(BaseModel):
    transcription_id: int
    word_count: int
    sentence_count: int
    speaking_rate_wpm: Optional[float] = None
    silence_ratio: Optional[float] = None
    sentiment_score: Optional[float] = None
    readability_score: Optional[float] = None
    language_confidence: Optional[float] = None
    topics: List[str] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)

class UsageMetrics(BaseModel):
    user_id: int
    date: datetime
    transcriptions_count: int
    total_duration_minutes: float
    total_file_size_mb: float
    api_calls: int
    errors_count: int
    success_rate: float

# Search and Filter Models
class TranscriptionSearchRequest(BaseModel):
    query: str
    user_id: int
    filters: Dict[str, Any] = Field(default_factory=dict)
    sort_by: str = Field(default="created_at")
    sort_order: str = Field(default="desc", pattern=r"^(asc|desc)$")  # Fixed: changed regex to pattern
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)

class TranscriptionSearchResponse(BaseModel):
    results: List[TranscriptionResponse]
    total_matches: int
    query: str
    search_time_ms: float
    suggestions: List[str] = Field(default_factory=list)

class LiveTranscriptionSettings(BaseModel):
    language: Optional[str] = None
    engine: TranscriptionEngine = TranscriptionEngine.WHISPER
    sample_rate: int = Field(default=16000, description="Audio sample rate")
    chunk_duration: float = Field(default=1.0, ge=0.5, le=5.0, description="Chunk duration in seconds")
    silence_threshold: float = Field(default=0.01, description="Silence detection threshold")
    auto_stop_timeout: int = Field(default=30, description="Auto-stop after seconds of silence")

class LiveTranscriptionResponse(BaseModel):
    text: str
    is_partial: bool = False
    is_final: bool = False
    confidence_score: Optional[float] = None
    language_detected: Optional[str] = None
    timestamp: datetime
    chunk_id: int
    session_id: str

class LiveSessionStatus(BaseModel):
    session_id: str
    status: str  # "recording", "processing", "stopped", "error"
    duration_seconds: float
    chunks_processed: int
    error_message: Optional[str] = None
    created_at: datetime
    last_activity: datetime

class AudioStreamData(BaseModel):
    audio_data: str  # base64 encoded audio
    session_id: str
    chunk_id: int
    is_final: bool = False

# Add this at module level
executor = ThreadPoolExecutor(max_workers=2)

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
        import os
        
        # Load WebM data directly into AudioSegment
        try:
            audio_segment = AudioSegment.from_file(
                io.BytesIO(audio_data), 
                format="webm"
            )
        except Exception as e:
            print(f"Failed to load WebM data: {e}")
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
        
        # Load model (with caching) using environment variable
        if not hasattr(process_webm_audio_with_whisper, '_model'):
            print(f"Loading Whisper model ({os.getenv('WHISPER_MODEL_SIZE', 'tiny')})...")
            import whisper
            process_webm_audio_with_whisper._model = whisper.load_model(os.getenv('WHISPER_MODEL_SIZE', 'tiny'))
            print("Whisper model cached")
        
        model = process_webm_audio_with_whisper._model
        
        # Set language with Afrikaans support
        whisper_language = None
        if language and language.lower() not in ['english', 'en']:
            lang_map = {
                'spanish': 'es', 'french': 'fr', 'german': 'de',
                'italian': 'it', 'portuguese': 'pt', 'russian': 'ru',
                'chinese': 'zh', 'japanese': 'ja', 'korean': 'ko',
                'arabic': 'ar', 'swahili': 'sw', 'afrikaans': 'af'  # Added Afrikaans
            }
            whisper_language = lang_map.get(language.lower(), language.lower()[:2])
        
        # Transcribe directly from numpy array
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

def process_streaming_audio_with_whisper(audio_data, language, session_id, chunk_id):
    """Process streaming audio with Whisper - handles accumulated audio data"""
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

        # Load model (with caching) using environment variable
        if not hasattr(process_streaming_audio_with_whisper, '_model'):
            print(f"Loading Whisper model ({os.getenv('WHISPER_MODEL_SIZE', 'tiny')})...")
            import whisper
            process_streaming_audio_with_whisper._model = whisper.load_model(os.getenv('WHISPER_MODEL_SIZE', 'tiny'))
            print("Whisper model cached")

        model = process_streaming_audio_with_whisper._model

        # Set language parameter with Afrikaans support
        whisper_language = None
        if language and language.lower() not in ['english', 'en']:
            lang_map = {
                'spanish': 'es', 'french': 'fr', 'german': 'de',
                'italian': 'it', 'portuguese': 'pt', 'russian': 'ru',
                'chinese': 'zh', 'japanese': 'ja', 'korean': 'ko',
                'arabic': 'ar', 'swahili': 'sw', 'afrikaans': 'af'  # Added Afrikaans
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

def process_streaming_audio_with_google(audio_data, language, session_id, chunk_id):
    """Process streaming audio with Google Speech Recognition"""
    try:
        print(f"Google processing streaming session {session_id}, chunk {chunk_id}")

        if not SPEECH_RECOGNITION_AVAILABLE:
            return None

        import speech_recognition as sr
        from pydub import AudioSegment

        # Similar logic as Whisper version for loading audio
        try:
            audio_segment = AudioSegment.from_file(
                io.BytesIO(audio_data), 
                format="webm"
            )
        except Exception as e:
            print(f"WebM loading failed, trying raw PCM: {e}")
            try:
                audio_segment = AudioSegment(
                    data=audio_data,
                    sample_width=2,
                    frame_rate=16000,
                    channels=1
                )
            except Exception as e2:
                print(f"Raw PCM failed: {e2}")
                return None

        # Optimize for Google Speech Recognition
        audio_segment = audio_segment.set_frame_rate(16000).set_channels(1)
        
        if len(audio_segment) < 500:  # Skip very short audio
            return None

        # Export to BytesIO buffer
        wav_buffer = io.BytesIO()
        audio_segment.export(wav_buffer, format="wav")
        wav_buffer.seek(0)

        # Use Google Speech Recognition
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
                'korean': 'ko-KR', 'arabic': 'ar-SA', 'swahili': 'sw-KE',
                'afrikaans': 'af-ZA'  # Added Afrikaans
            }
            google_language = lang_map.get(language.lower(), 'en-US')

        text = recognizer.recognize_google(audio_data_sr, language=google_language)
        print(f"Google result: '{text[:50]}...'")

        return {"text": text}

    except Exception as e:
        print(f"Google streaming processing error: {e}")
        return None


# Request/Response models for analysis endpoints
class SpeakerRequest(BaseModel):
    id: str
    name: str
    role: str = "participant"

class AnalyzeSessionRequest(BaseModel):
    speakers: Optional[List[SpeakerRequest]] = None

