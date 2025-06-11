from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Query, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError, DisconnectionError
from typing import List, Optional
import sys
import os
import tempfile  # Add this import
import time      # Add this import

# Add the speech_micro directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

from db.connection import db_dependency
from services.speech_services import SpeechService 
from schemas.speech_schemas import *  
from schemas.speech_schemas import process_audio_buffer
from sqlalchemy import text
from datetime import datetime
import asyncio

# Add these imports for quick transcription
from utils.speech_flags import WHISPER_AVAILABLE, SPEECH_RECOGNITION_AVAILABLE

from fastapi import WebSocket, WebSocketDisconnect
import base64
import json
import threading
from collections import defaultdict
import uuid

# Add after your existing imports
try:
    import pyaudio
    PYAUDIO_AVAILABLE = True
except ImportError:
    PYAUDIO_AVAILABLE = False
    print("PyAudio not available. Real-time recording won't work.")

router = APIRouter(prefix="/speech", tags=["Speech-to-Text"])

# Add this class for managing live sessions
class LiveTranscriptionManager:
    def __init__(self):
        self.active_sessions = {}
        self.session_buffers = defaultdict(list)
    
    def create_session(self) -> str:
        session_id = str(uuid.uuid4())
        self.active_sessions[session_id] = {
            "status": "created",
            "created_at": datetime.utcnow(),
            "last_activity": datetime.utcnow(),
            "chunks_processed": 0,
            "duration": 0.0
        }
        return session_id
    
    def update_session(self, session_id: str, **kwargs):
        if session_id in self.active_sessions:
            self.active_sessions[session_id].update(kwargs)
            self.active_sessions[session_id]["last_activity"] = datetime.utcnow()
    
    def close_session(self, session_id: str):
        if session_id in self.active_sessions:
            del self.active_sessions[session_id]
        if session_id in self.session_buffers:
            del self.session_buffers[session_id]

# Create global manager instance
live_manager = LiveTranscriptionManager()


@router.post("/quick-transcribe", response_model=QuickTranscriptionResponse)
async def quick_transcribe(
    file: UploadFile = File(...),
    language: Optional[str] = Query(None),
    engine: TranscriptionEngine = Query(TranscriptionEngine.WHISPER)
):
    """Quick transcription without saving to database"""
    start_time = time.time()
    temp_file_path = None
    converted_file_path = None
    
    try:
        # Validate file type
        allowed_types = ['audio/mpeg', 'audio/wav', 'audio/mp4', 'audio/m4a', 'audio/flac', 'audio/ogg', 'audio/opus', 'audio/webm']
        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported file type: {file.content_type}. Allowed types: {', '.join(allowed_types)}"
            )
        
        # Check file size (10MB limit for quick transcription)
        file_content = await file.read()
        file_size = len(file_content)
        
        if file_size > 10 * 1024 * 1024:  # 10MB limit
            raise HTTPException(
                status_code=400,
                detail="File too large for quick transcription. Maximum size: 10MB"
            )
        
        # Get original file extension
        original_extension = os.path.splitext(file.filename)[1].lower() if file.filename else '.mp3'
        print(f"Original file extension: {original_extension}")
        
        # Create temporary file with original extension
        temp_fd, temp_file_path = tempfile.mkstemp(suffix=original_extension)
        try:
            with os.fdopen(temp_fd, 'wb') as temp_file:
                temp_file.write(file_content)
        except:
            os.close(temp_fd)
            raise
        
        print(f"Created temp file: {temp_file_path}")
        print(f"Temp file size: {os.path.getsize(temp_file_path)} bytes")
        
        # Verify file exists and has content
        if not os.path.exists(temp_file_path):
            raise HTTPException(
                status_code=500,
                detail="Failed to create temporary file"
            )
        
        if os.path.getsize(temp_file_path) == 0:
            raise HTTPException(
                status_code=400,
                detail="Empty audio file received"
            )
        
        # Check if FFmpeg is available
        ffmpeg_available = False
        try:
            import subprocess
            result = subprocess.run(['ffmpeg', '-version'], 
                                  capture_output=True, text=True, timeout=5)
            ffmpeg_available = result.returncode == 0
            print(f"FFmpeg available: {ffmpeg_available}")
        except (FileNotFoundError, subprocess.TimeoutExpired):
            print("FFmpeg not found in PATH")
            ffmpeg_available = False
        
        # Set working file path
        working_file_path = temp_file_path
        
        # Handle format conversion for problematic formats
        if original_extension in ['.opus', '.webm', '.ogg'] and ffmpeg_available:
            print(f"Converting {original_extension} to WAV for better compatibility...")
            try:
                if SPEECH_RECOGNITION_AVAILABLE:
                    from pydub import AudioSegment
                    
                    # Create converted file
                    converted_fd, converted_file_path = tempfile.mkstemp(suffix='.wav')
                    os.close(converted_fd)  # Close the file descriptor
                    
                    # Load and convert audio
                    audio = AudioSegment.from_file(temp_file_path)
                    audio = audio.set_frame_rate(16000).set_channels(1)  # Optimize for speech
                    audio.export(converted_file_path, format="wav")
                    
                    working_file_path = converted_file_path
                    print(f"Successfully converted to WAV: {working_file_path}")
                    print(f"Converted file size: {os.path.getsize(working_file_path)} bytes")
                else:
                    print("pydub not available, using original file")
            except Exception as e:
                print(f"Audio conversion failed: {e}")
                print("Continuing with original file...")
                working_file_path = temp_file_path
        elif original_extension in ['.opus', '.webm', '.ogg'] and not ffmpeg_available:
            print(f"FFmpeg not available - cannot convert {original_extension}. Install FFmpeg for better format support.")
            # For OPUS without FFmpeg, we'll let Whisper try to handle it directly
            working_file_path = temp_file_path
        
        # Get audio duration (optional, don't fail if it doesn't work)
        audio_duration = None
        try:
            if SPEECH_RECOGNITION_AVAILABLE and ffmpeg_available:
                from pydub import AudioSegment
                audio = AudioSegment.from_file(working_file_path)
                audio_duration = len(audio) / 1000.0  # Convert to seconds
                print(f"Audio duration: {audio_duration} seconds")
        except Exception as e:
            print(f"Could not get audio duration (continuing anyway): {e}")
            # Set a reasonable default duration
            audio_duration = 60.0  # Assume 1 minute if we can't detect
        
        # Check duration limit (5 minutes for quick transcription)
        if audio_duration and audio_duration > 300:  # 5 minutes
            raise HTTPException(
                status_code=400,
                detail="Audio too long for quick transcription. Maximum duration: 5 minutes"
            )
        
        # Perform transcription based on engine
        transcription_text = ""
        confidence_score = None
        language_detected = language
        segments = []
        
        if engine == TranscriptionEngine.WHISPER and WHISPER_AVAILABLE:
            # Use Whisper
            try:
                print(f"Starting Whisper transcription for file: {working_file_path}")
                print(f"File exists: {os.path.exists(working_file_path)}")
                print(f"File size: {os.path.getsize(working_file_path) if os.path.exists(working_file_path) else 'N/A'} bytes")
                
                # Verify working file exists and has content
                if not os.path.exists(working_file_path):
                    raise Exception(f"Working file not found: {working_file_path}")
                
                if os.path.getsize(working_file_path) == 0:
                    raise Exception(f"Working file is empty: {working_file_path}")
                
                # Load Whisper model
                print("Loading Whisper model...")
                model = whisper.load_model("base")
                print("Whisper model loaded successfully")
                
                # Set language parameter correctly
                whisper_language = None
                if language and language.lower() not in ['english', 'en']:
                    # Convert common language names to codes
                    lang_map = {
                        'spanish': 'es',
                        'french': 'fr',
                        'german': 'de',
                        'italian': 'it',
                        'portuguese': 'pt',
                        'russian': 'ru',
                        'chinese': 'zh',
                        'japanese': 'ja',
                        'korean': 'ko'
                    }
                    whisper_language = lang_map.get(language.lower(), language.lower()[:2])
                
                print(f"Starting transcription with language: {whisper_language or 'auto-detect'}")
                
                # Transcribe using the working file with more options
                result = model.transcribe(
                    working_file_path,
                    language=whisper_language,
                    verbose=False,
                    fp16=False,  # Disable FP16 to avoid CPU warnings
                    condition_on_previous_text=False,  # Better for short clips
                    temperature=0.0  # More deterministic output
                )
                
                transcription_text = result["text"].strip()
                language_detected = result.get("language", language or "en")
                
                print(f"Whisper transcription completed successfully!")
                print(f"Detected language: {language_detected}")
                print(f"Transcription: {transcription_text[:100]}...")
                
                # Extract segments if available
                if "segments" in result and result["segments"]:
                    segments = []
                    total_confidence = 0
                    confidence_count = 0
                    
                    for seg in result["segments"]:
                        segment_confidence = None
                        if "avg_logprob" in seg and seg["avg_logprob"] is not None:
                            # Convert log probability to confidence (approximate)
                            segment_confidence = max(0.0, min(1.0, (seg["avg_logprob"] + 1.0) / 2.0))
                            total_confidence += segment_confidence
                            confidence_count += 1
                        
                        segments.append(TranscriptionSegment(
                            start_time=seg["start"],
                            end_time=seg["end"],
                            text=seg["text"].strip(),
                            confidence=segment_confidence
                        ))
                    
                    # Calculate average confidence
                    if confidence_count > 0:
                        confidence_score = total_confidence / confidence_count
            
            except Exception as e:
                print(f"Whisper transcription failed: {e}")
                import traceback
                traceback.print_exc()
                
                # Provide more helpful error messages
                error_msg = str(e)
                if "ffmpeg" in error_msg.lower() or "ffprobe" in error_msg.lower():
                    error_msg = "FFmpeg not found. Please install FFmpeg to process this audio format."
                elif "No such file or directory" in error_msg or "cannot find the file" in error_msg.lower():
                    error_msg = "Audio file processing failed. This may be due to unsupported format or missing dependencies."
                
                raise HTTPException(
                    status_code=500,
                    detail=f"Whisper transcription failed: {error_msg}"
                )
        
        else:
            # Engine not available or other engine selected
            if not WHISPER_AVAILABLE and engine == TranscriptionEngine.WHISPER:
                raise HTTPException(
                    status_code=503,
                    detail="Whisper engine not available. Please install openai-whisper: pip install openai-whisper"
                )
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported transcription engine: {engine}"
                )
        
        # Calculate processing time
        processing_time = time.time() - start_time
        
        # Return response
        return QuickTranscriptionResponse(
            text=transcription_text,
            language_detected=language_detected,
            confidence_score=confidence_score,
            processing_time_seconds=round(processing_time, 2),
            audio_duration_seconds=round(audio_duration, 2) if audio_duration else None,
            engine_used=engine.value,
            segments=segments if segments else None
        )
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"Unexpected error in quick_transcribe: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500, 
            detail=f"An unexpected error occurred: {str(e)}"
        )
    
    finally:
        # Clean up temporary files
        try:
            if temp_file_path and os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
                print(f"Cleaned up original temp file: {temp_file_path}")
        except Exception as e:
            print(f"Failed to clean up temp file: {e}")
        
        try:
            if converted_file_path and os.path.exists(converted_file_path):
                os.unlink(converted_file_path)
                print(f"Cleaned up converted file: {converted_file_path}")
        except Exception as e:
            print(f"Failed to clean up converted file: {e}")


@router.get("/health/detailed")
async def detailed_health_check(db: Session = Depends(db_dependency)):  # Fixed: Use Session directly
    """Detailed health check"""
    try:
        # Test database connection
        result = db.execute(text("SELECT 1 as test"))
        db_test = result.fetchone()
        
        # Check if required directories exist
        upload_dir_exists = os.path.exists("uploads/audio")
        
        # Check if Whisper is available
        whisper_available = False
        try:
            import whisper
            whisper_available = True
        except (ImportError, ModuleNotFoundError):
            pass
        
        return {
            "status": "healthy",
            "service": "speech-to-text",
            "database": "connected",
            "database_test": "passed",
            "upload_directory": "exists" if upload_dir_exists else "missing",
            "whisper_available": whisper_available,
            "speech_recognition_available": True,  # Always available if installed
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "service": "speech-to-text",
            "database": "disconnected",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


# Add the WebSocket endpoint after your existing endpoints
@router.websocket("/live-transcribe")
async def live_transcribe_websocket(
    websocket: WebSocket,
    language: Optional[str] = Query(None),
    engine: TranscriptionEngine = Query(TranscriptionEngine.WHISPER)
):
    """Real-time microphone transcription via WebSocket"""
    
    await websocket.accept()
    session_id = live_manager.create_session()
    
    print(f"Started live transcription session: {session_id}")
    
    try:
        # Send initial session info
        await websocket.send_json({
            "type": "session_started",
            "session_id": session_id,
            "message": "Live transcription session started. Send audio data to begin."
        })
        
        chunk_id = 0
        webm_header = None  # Store the first chunk as header
        processing_lock = asyncio.Lock()
        
        while True:
            try:
                # Receive audio data from client
                data = await websocket.receive_text()
                message = json.loads(data)
                
                if message["type"] == "audio_chunk":
                    chunk_id += 1
                    try:
                        audio_data = base64.b64decode(message["audio_data"])
                        if len(audio_data) < 100:
                            continue

                        # Process each chunk independently
                        if webm_header is None:
                            # First chunk contains the header
                            webm_header = audio_data
                            chunk_to_process = audio_data
                        else:
                            # For subsequent chunks, try processing just the chunk
                            # If that fails, fall back to header + chunk
                            chunk_to_process = audio_data

                        async with processing_lock:
                            print(f"Processing audio chunk {chunk_id}: {len(audio_data)} bytes")
                            try:
                                transcription = await process_streaming_audio(
                                    chunk_to_process,
                                    session_id,
                                    chunk_id,
                                    language,
                                    engine
                                )
                                
                                # If processing the chunk alone failed and it's not the first chunk,
                                # try with header prepended as fallback
                                if (not transcription or not transcription["text"].strip()) and webm_header and chunk_id > 1:
                                    print(f"Chunk alone failed, trying with header prepended...")
                                    chunk_to_process = webm_header + audio_data
                                    transcription = await process_streaming_audio(
                                        chunk_to_process,
                                        session_id,
                                        chunk_id,
                                        language,
                                        engine
                                    )
                                
                                if transcription and transcription["text"].strip():
                                    await websocket.send_json({
                                        "type": "transcription",
                                        "session_id": session_id,
                                        "chunk_id": chunk_id,
                                        "text": transcription["text"],
                                        "confidence": transcription.get("confidence"),
                                        "language_detected": transcription.get("language"),
                                        "is_partial": True,
                                        "timestamp": datetime.utcnow().isoformat()
                                    })
                            except Exception as e:
                                print(f"Error in transcription processing: {e}")
                    except Exception as e:
                        print(f"Error processing audio chunk: {e}")
                        continue
                
                elif message["type"] == "stop_recording":
                    # Send session ended message
                    await websocket.send_json({
                        "type": "session_ended",
                        "session_id": session_id,
                        "message": "Live transcription session ended."
                    })
                    break
                
                elif message["type"] == "ping":
                    await websocket.send_json({"type": "pong", "session_id": session_id})
            
            except WebSocketDisconnect:
                print(f"WebSocket disconnected for session: {session_id}")
                break
            except Exception as e:
                print(f"Error in live transcription: {e}")
                await websocket.send_json({
                    "type": "error",
                    "session_id": session_id,
                    "error": str(e)
                })
                break
    
    finally:
        live_manager.close_session(session_id)
        print(f"Closed live transcription session: {session_id}")


# Add endpoint to get session status
@router.get("/live-sessions/{session_id}", response_model=LiveSessionStatus)
async def get_live_session_status(session_id: str):
    """Get status of a live transcription session"""
    if session_id not in live_manager.active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session_data = live_manager.active_sessions[session_id]
    return LiveSessionStatus(
        session_id=session_id,
        status=session_data["status"],
        duration_seconds=(datetime.utcnow() - session_data["created_at"]).total_seconds(),
        chunks_processed=session_data["chunks_processed"],
        created_at=session_data["created_at"],
        last_activity=session_data["last_activity"]
    )

# Add endpoint to list active sessions
@router.get("/live-sessions")
async def get_active_sessions():
    """Get all active live transcription sessions"""
    sessions = []
    for session_id, data in live_manager.active_sessions.items():
        sessions.append({
            "session_id": session_id,
            "status": data["status"],
            "created_at": data["created_at"].isoformat(),
            "chunks_processed": data["chunks_processed"]
        })
    
    return {"active_sessions": sessions, "total_count": len(sessions)}