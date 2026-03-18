from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect
from typing import Optional, List
import sys
import os
import time
import base64
import json
import uuid
from datetime import datetime
from collections import defaultdict
import asyncio

# Add the speech_micro directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

from services.speech_services import SpeechService 
from schemas.speech_schemas import *
from schemas.speech_schemas import AnalyzeSessionRequest
from utils.speech_flags import WHISPER_AVAILABLE, SPEECH_RECOGNITION_AVAILABLE
from services.ai_analysis_service import AIAnalysisService, MeetingType, Speaker, DebateAnalysis

router = APIRouter(prefix="/speech", tags=["Live Speech-to-Text"])

# Live transcription manager for handling real-time sessions
class LiveTranscriptionManager:
    def __init__(self):
        self.active_sessions = {}
        self.session_buffers = defaultdict(list)
        self.audio_accumulators = defaultdict(bytearray)  # Accumulate audio data
        self.session_segments = defaultdict(list)  # Store completed segments
        self.segment_duration = 120  # 2 minutes per segment for better content analysis
        self.min_segment_duration = 30  # Minimum 30 seconds before allowing new segment
    
    def create_session(self) -> str:
        session_id = str(uuid.uuid4())
        self.active_sessions[session_id] = {
            "status": "created",
            "created_at": datetime.utcnow(),
            "last_activity": datetime.utcnow(),
            "chunks_processed": 0,
            "total_text": "",  # Current segment text
            "session_full_text": "",  # Full session text across all segments
            "language": None,
            "current_segment": 1,
            "segment_start_time": datetime.utcnow(),
            "current_speaker": None,  # Track current active speaker
            "all_transcriptions": []  # Store all transcriptions for analysis
        }
        return session_id
    
    def update_session(self, session_id: str, **kwargs):
        if session_id in self.active_sessions:
            self.active_sessions[session_id].update(kwargs)
            self.active_sessions[session_id]["last_activity"] = datetime.utcnow()
    
    def add_audio_chunk(self, session_id: str, audio_data: bytes, chunk_id: int):
        """Add audio chunk to session accumulator"""
        if session_id not in self.active_sessions:
            return False
            
        # Always accumulate all audio data to maintain valid WebM stream
        self.audio_accumulators[session_id].extend(audio_data)
        
        return True
    
    def _save_current_segment(self, session_id: str):
        """Save current segment data"""
        if session_id in self.active_sessions:
            session_data = self.active_sessions[session_id]
            segment_data = {
                "segment_number": session_data["current_segment"],
                "start_time": session_data["segment_start_time"],
                "end_time": datetime.utcnow(),
                "text": session_data.get("total_text", ""),
                "language": session_data.get("language"),
                "transcriptions": session_data.get("all_transcriptions", []).copy()
            }
            self.session_segments[session_id].append(segment_data)
    
    def _start_new_segment(self, session_id: str):
        """Start a new segment while preserving audio stream continuity"""
        if session_id in self.active_sessions:
            self.active_sessions[session_id].update({
                "current_segment": self.active_sessions[session_id]["current_segment"] + 1,
                "segment_start_time": datetime.utcnow(),
                "total_text": "",  # Reset segment text for new segment
                "all_transcriptions": []  # Reset for new segment
            })
            # Note: session_full_text is NOT reset - it accumulates across segments
            # Note: audio_accumulators is NOT reset - preserves WebM stream continuity
            # Segmentation is now handled through transcription timestamps and text processing
            print(f"Started new segment {self.active_sessions[session_id]['current_segment']} for session {session_id} (audio stream preserved)")
    
    def should_start_new_segment(self, session_id: str) -> bool:
        """Check if we should start a new segment based on content length and time"""
        if session_id not in self.active_sessions:
            return False
        
        session_data = self.active_sessions[session_id]
        time_elapsed = (datetime.utcnow() - session_data["segment_start_time"]).total_seconds()
        
        # Only create new segments if:
        # 1. We've reached the maximum segment duration (2 minutes), OR
        # 2. We have substantial content AND minimum time has passed AND there's a topic shift
        current_text = session_data.get("total_text", "")
        word_count = len(current_text.split()) if current_text else 0
        
        # Force new segment after max duration
        if time_elapsed >= self.segment_duration:
            return True
            
        # Allow new segment if we have enough content and minimum time has passed
        if (time_elapsed >= self.min_segment_duration and 
            word_count >= 50 and  # At least 50 words
            self._detect_topic_shift(current_text)):
            return True
            
        return False
    
    def check_speaker_change(self, session_id: str, speaker_info: dict) -> bool:
        """Check if the speaker has changed from the current speaker"""
        if session_id not in self.active_sessions or not speaker_info:
            return False
        
        current_speaker = self.active_sessions[session_id].get("current_speaker")
        new_speaker_id = speaker_info.get("speaker_id") if speaker_info else None
        
        # If this is the first speaker or speaker has changed
        if current_speaker is None:
            # First speaker - no change yet
            self.active_sessions[session_id]["current_speaker"] = new_speaker_id
            return False
        elif current_speaker != new_speaker_id:
            # Speaker changed
            print(f"Speaker change detected in session {session_id}: {current_speaker} -> {new_speaker_id}")
            return True
        
        return False
    
    def update_current_speaker(self, session_id: str, speaker_info: dict):
        """Update the current speaker for the session"""
        if session_id in self.active_sessions and speaker_info:
            new_speaker_id = speaker_info.get("speaker_id")
            self.active_sessions[session_id]["current_speaker"] = new_speaker_id
            print(f"Updated current speaker for session {session_id} to: {new_speaker_id}")
    
    def _detect_topic_shift(self, text: str) -> bool:
        """Simple topic shift detection based on discourse markers"""
        if not text:
            return False
            
        text_lower = text.lower()
        topic_shift_markers = [
            "now let's talk about", "moving on to", "on the other hand",
            "however", "but", "in contrast", "meanwhile", "next",
            "now", "additionally", "furthermore", "moreover",
            "let me address", "switching topics", "another point"
        ]
        
        # Check if any topic shift markers appear in the last 100 characters
        recent_text = text_lower[-100:] if len(text_lower) > 100 else text_lower
        return any(marker in recent_text for marker in topic_shift_markers)
    
    def get_accumulated_audio_for_transcription(self, session_id: str) -> bytes:
        """Get the complete accumulated audio for transcription"""
        if session_id not in self.active_sessions:
            return b''
        
        total_audio = bytes(self.audio_accumulators.get(session_id, bytearray()))
        
        # Always return the complete accumulated audio to maintain WebM stream integrity
        # Segmentation will be handled at the text level, not audio level
        if len(total_audio) > 1000:  # Minimum viable audio size
            return total_audio
        else:
            return b''
    

    
    def get_all_segments(self, session_id: str) -> list:
        """Get all completed segments for a session"""
        return self.session_segments.get(session_id, [])
    
    def add_transcription(self, session_id: str, transcription_data: dict):
        """Add transcription to current session"""
        if session_id in self.active_sessions:
            self.active_sessions[session_id]["all_transcriptions"].append(transcription_data)
    
    def close_session(self, session_id: str):
        # Save final segment before closing
        if session_id in self.active_sessions:
            self._save_current_segment(session_id)
            del self.active_sessions[session_id]
        if session_id in self.session_buffers:
            del self.session_buffers[session_id]
        if session_id in self.audio_accumulators:
            del self.audio_accumulators[session_id]

# Create global manager instance
live_manager = LiveTranscriptionManager()
ai_analysis_service = AIAnalysisService()

# Process streaming audio chunks
async def process_streaming_audio(audio_data, session_id, chunk_id, language, engine, previous_text="", audio_format="audio/webm", **kwargs):
    """Process accumulated audio for real-time transcription"""
    try:
        if engine == "whisper" and WHISPER_AVAILABLE:
            # Check if this is raw PCM data
            if audio_format == "audio/pcm":
                # Extract PCM parameters
                sample_rate = kwargs.get('sample_rate', 16000)
                channels = kwargs.get('channels', 1)
                bits_per_sample = kwargs.get('bits_per_sample', 16)
                
                # Run PCM Whisper processing in thread pool
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None, 
                    SpeechService.process_pcm_audio_with_whisper,
                    audio_data, language, session_id, chunk_id, previous_text,
                    sample_rate, channels, bits_per_sample
                )
                return result
            else:
                # Run accumulated Whisper processing in thread pool
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None, 
                    SpeechService.process_streaming_audio_with_whisper,
                    audio_data, language, session_id, chunk_id, previous_text, audio_format
                )
                return result
        elif engine == "google" and SPEECH_RECOGNITION_AVAILABLE:
            # Run Google processing in thread pool
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                SpeechService.process_webm_audio_with_google,
                audio_data, language, session_id, chunk_id
            )
            return result
        else:
            return None
    except Exception as e:
        print(f"Error in process_streaming_audio: {e}")
        return None


# Real-time WebSocket endpoint for live transcription
@router.websocket("/live-transcribe")
async def live_transcribe_websocket(
    websocket: WebSocket,
    language: Optional[str] = Query(None),
    engine: str = Query("whisper")
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
            "message": "Live transcription ready. Start speaking!",
            "supported_languages": ["en", "es", "fr", "de", "it", "pt", "ru", "zh", "ja", "ko", "ar", "sw", "af"]
        })
        
        chunk_id = 0
        processing_lock = asyncio.Lock()
        
        while True:
            try:
                # Receive data from client
                data = await websocket.receive_text()
                message = json.loads(data)
                
                if message["type"] == "audio_chunk":
                    chunk_id += 1
                    try:
                        # Decode audio data
                        audio_data = base64.b64decode(message["audio_data"])
                        
                        # Extract speaker information if provided
                        speaker_info = message.get("speaker_info")
                        
                        # Extract audio format if provided
                        audio_format = message.get("audio_format", "audio/webm")
                        
                        # Extract PCM parameters if provided
                        pcm_params = {}
                        if audio_format == "audio/pcm":
                            pcm_params['sample_rate'] = message.get("sample_rate", 16000)
                            pcm_params['channels'] = message.get("channels", 1)
                            pcm_params['bits_per_sample'] = message.get("bits_per_sample", 16)
                        
                        # Skip very small chunks
                        if len(audio_data) < 1000:
                            continue

                        # Check for speaker change FIRST - this is the most important trigger for new segments
                        speaker_changed = live_manager.check_speaker_change(session_id, speaker_info)
                        
                        if speaker_changed:
                            # Save current segment and start new one due to speaker change
                            current_segment = live_manager.active_sessions[session_id]["current_segment"]
                            print(f"Speaker change detected! Completing segment {current_segment} and starting new segment")
                            
                            live_manager._save_current_segment(session_id)
                            live_manager._start_new_segment(session_id)
                            live_manager.update_current_speaker(session_id, speaker_info)
                            
                            new_segment = live_manager.active_sessions[session_id]["current_segment"]
                            
                            # Send segment completed notification
                            await websocket.send_json({
                                "type": "segment_completed",
                                "session_id": session_id,
                                "segment_number": current_segment,
                                "message": f"Speaker changed! Segment {current_segment} completed. Starting segment {new_segment}.",
                                "timestamp": datetime.utcnow().isoformat(),
                                "reason": "speaker_change",
                                "previous_speaker": live_manager.active_sessions[session_id]["current_speaker"],
                                "new_speaker": speaker_info.get("speaker_id") if speaker_info else None
                            })
                        elif live_manager.should_start_new_segment(session_id):
                            # Check if we need to start a new segment based on time/content
                            current_segment = live_manager.active_sessions[session_id]["current_segment"]
                            print(f"Time/content-based segment completion for segment {current_segment}")
                            
                            live_manager._save_current_segment(session_id)
                            live_manager._start_new_segment(session_id)
                            
                            new_segment = live_manager.active_sessions[session_id]["current_segment"]
                            
                            # Send segment completed notification
                            await websocket.send_json({
                                "type": "segment_completed",
                                "session_id": session_id,
                                "segment_number": current_segment,
                                "message": f"Segment {current_segment} completed. Starting segment {new_segment}.",
                                "timestamp": datetime.utcnow().isoformat(),
                                "reason": "time_content"
                            })

                        # Add chunk to session accumulator
                        live_manager.add_audio_chunk(session_id, audio_data, chunk_id)

                        # Process accumulated audio every few chunks or after enough data
                        if chunk_id % 3 == 0 or len(live_manager.audio_accumulators[session_id]) > 50000:
                            async with processing_lock:
                                print(f"Processing new audio for chunk {chunk_id}")
                                
                                # Get only the new audio data that hasn't been transcribed
                                new_audio_data = live_manager.get_accumulated_audio_for_transcription(session_id)
                                
                                if not new_audio_data or len(new_audio_data) < 1000:
                                    print("Not enough new audio data to transcribe, skipping")
                                    continue
                                
                                # Get previous text for deduplication
                                # Get current session-wide text for proper deduplication
                                current_session_text = live_manager.active_sessions[session_id].get("session_full_text", "")
                                
                                # Process only the new audio
                                transcription = await process_streaming_audio(
                                    new_audio_data,
                                    session_id,
                                    chunk_id,
                                    language,
                                    engine,
                                    current_session_text,  # Pass session-wide text for deduplication
                                    audio_format,  # Pass the audio format
                                    **pcm_params  # Pass PCM parameters if present
                                )
                                
                                if transcription and transcription.get("text", "").strip():
                                    text = transcription["text"].strip()
                                    
                                    # Store transcription data
                                    transcription_data = {
                                        "chunk_id": chunk_id,
                                        "text": text,
                                        "timestamp": datetime.utcnow(),
                                        "language": transcription.get("language"),
                                        "confidence": transcription.get("confidence"),
                                        "speaker_info": speaker_info  # Include speaker information
                                    }
                                    live_manager.add_transcription(session_id, transcription_data)
                                    
                                    # Update session with new text
                                    # Always add to session-wide text accumulator
                                    current_session_text = live_manager.active_sessions[session_id].get("session_full_text", "")
                                    new_session_text = current_session_text + " " + text if current_session_text else text
                                    
                                    # For segment text - just add to current segment
                                    current_total = live_manager.active_sessions[session_id].get("total_text", "")
                                    new_total = current_total + " " + text if current_total else text
                                    
                                    print(f"Session {session_id}: new_text='{text[:50]}...', segment_total='{new_total[:50]}...', session_total='{new_session_text[:100]}...'")
                                    
                                    live_manager.update_session(
                                        session_id,
                                        chunks_processed=chunk_id,
                                        total_text=new_total,
                                        session_full_text=new_session_text,  # Update session-wide text
                                        language=transcription.get("language", language)
                                    )
                                    
                                    # Send transcription result
                                    await websocket.send_json({
                                        "type": "transcription",
                                        "session_id": session_id,
                                        "chunk_id": chunk_id,
                                        "text": text,
                                        "language_detected": transcription.get("language"),
                                        "confidence": transcription.get("confidence"),
                                        "is_partial": True,
                                        "segment_number": live_manager.active_sessions[session_id]["current_segment"],
                                        "timestamp": datetime.utcnow().isoformat(),
                                        "speaker_info": speaker_info  # Include speaker information in response
                                    })
                                else:
                                    # Send empty result for silence/noise
                                    await websocket.send_json({
                                        "type": "silence",
                                        "session_id": session_id,
                                        "chunk_id": chunk_id,
                                        "segment_number": live_manager.active_sessions[session_id]["current_segment"],
                                        "timestamp": datetime.utcnow().isoformat()
                                    })
                        else:
                            # Just acknowledge the chunk without processing
                            await websocket.send_json({
                                "type": "chunk_received",
                                "session_id": session_id,
                                "chunk_id": chunk_id,
                                "accumulated_size": len(live_manager.audio_accumulators.get(session_id, bytearray())),
                                "audio_size": len(live_manager.get_accumulated_audio_for_transcription(session_id)),
                                "segment_number": live_manager.active_sessions[session_id]["current_segment"],
                                "timestamp": datetime.utcnow().isoformat()
                            })
                                
                    except Exception as e:
                        print(f"Error processing audio chunk: {e}")
                        await websocket.send_json({
                            "type": "processing_error",
                            "session_id": session_id,
                            "error": str(e),
                            "chunk_id": chunk_id
                        })
                        continue
                
                elif message["type"] == "stop_recording":
                    # Get final session data
                    session_data = live_manager.active_sessions.get(session_id, {})
                    final_text = session_data.get("total_text", "").strip()
                    
                    # Send final results
                    await websocket.send_json({
                        "type": "session_ended",
                        "session_id": session_id,
                        "final_text": final_text,
                        "total_chunks": chunk_id,
                        "language_detected": session_data.get("language"),
                        "duration_seconds": (datetime.utcnow() - session_data.get("created_at", datetime.utcnow())).total_seconds(),
                        "message": "Live transcription session completed."
                    })
                    break
                
                elif message["type"] == "ping":
                    await websocket.send_json({
                        "type": "pong", 
                        "session_id": session_id,
                        "timestamp": datetime.utcnow().isoformat()
                    })
            
            except WebSocketDisconnect:
                print(f"WebSocket disconnected for session: {session_id}")
                break
            except Exception as e:
                print(f"Error in live transcription: {e}")
                try:
                    await websocket.send_json({
                        "type": "error",
                        "session_id": session_id,
                        "error": str(e)
                    })
                except:
                    pass
                break
    
    finally:
        live_manager.close_session(session_id)
        print(f"Closed live transcription session: {session_id}")


# Get session status
@router.get("/live-sessions/{session_id}")
async def get_live_session_status(session_id: str):
    """Get status of a live transcription session"""
    if session_id not in live_manager.active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session_data = live_manager.active_sessions[session_id]
    return {
        "session_id": session_id,
        "status": session_data["status"],
        "duration_seconds": (datetime.utcnow() - session_data["created_at"]).total_seconds(),
        "chunks_processed": session_data["chunks_processed"],
        "total_text": session_data.get("total_text", ""),
        "language": session_data.get("language"),
        "created_at": session_data["created_at"].isoformat(),
        "last_activity": session_data["last_activity"].isoformat()
    }

# List active sessions
@router.get("/live-sessions")
async def get_active_sessions():
    """Get all active live transcription sessions"""
    sessions = []
    for session_id, data in live_manager.active_sessions.items():
        sessions.append({
            "session_id": session_id,
            "status": data["status"],
            "created_at": data["created_at"].isoformat(),
            "chunks_processed": data["chunks_processed"],
            "language": data.get("language")
        })
    
    return {"active_sessions": sessions, "total_count": len(sessions)}

# Health check
@router.get("/health")
async def health_check():
    """Simple health check for live transcription service"""
    return {
        "status": "healthy",
        "service": "live-speech-to-text",
        "whisper_available": WHISPER_AVAILABLE,
        "speech_recognition_available": SPEECH_RECOGNITION_AVAILABLE,
        "active_sessions": len(live_manager.active_sessions),
        "timestamp": datetime.utcnow().isoformat()
    }

# AI Analysis endpoints for debates and meetings
@router.post("/analyze-session/{session_id}")
async def analyze_session(
    session_id: str,
    request: AnalyzeSessionRequest,
    meeting_type: MeetingType = MeetingType.DISCUSSION
):
    """
    Analyze a completed transcription session for debate/meeting insights
    """
    try:
        # Get session segments
        segments = live_manager.get_all_segments(session_id)
        session_full_text = ""
        
        if not segments:
            # Check if session is still active
            if session_id in live_manager.active_sessions:
                # Include current session data
                current_session = live_manager.active_sessions[session_id]
                session_full_text = current_session.get("session_full_text", "")
                segments = [{
                    "segment_number": current_session.get("current_segment", 1),
                    "text": current_session.get("total_text", ""),
                    "transcriptions": current_session.get("all_transcriptions", []),
                    "start_time": current_session.get("segment_start_time", datetime.utcnow()),
                    "end_time": datetime.utcnow()
                }]
            else:
                raise HTTPException(status_code=404, detail="Session not found or no data available")
        else:
            # Get session-wide text if available
            if session_id in live_manager.active_sessions:
                current_session = live_manager.active_sessions[session_id]
                session_full_text = current_session.get("session_full_text", "")
                
                # Also add current segment if it has text
                if current_session.get("total_text"):
                    segments.append({
                        "segment_number": current_session.get("current_segment", 1),
                        "text": current_session.get("total_text", ""),
                        "transcriptions": current_session.get("all_transcriptions", []),
                        "start_time": current_session.get("segment_start_time", datetime.utcnow()),
                        "end_time": datetime.utcnow()
                    })
        
        print(f"Analysis: session_full_text='{session_full_text[:100]}...', segments={len(segments)}")
        
        # Convert speaker dicts to Speaker objects if provided
        speaker_objects = []
        if request.speakers:
            for i, speaker_data in enumerate(request.speakers):
                speaker_objects.append(Speaker(
                    id=speaker_data.id,
                    name=speaker_data.name,
                    role=speaker_data.role
                ))
        else:
            # Default single speaker
            speaker_objects = [Speaker(id="speaker_1", name="Participant 1")]
        
        # Perform AI analysis
        analysis = await ai_analysis_service.analyze_session(
            session_id=session_id,
            segments=segments,
            meeting_type=meeting_type,
            speakers=speaker_objects,
            session_full_text=session_full_text  # Pass the session-wide text
        )
        
        # Create AI user summary
        ai_summary = await ai_analysis_service.create_ai_user_summary(analysis, meeting_type)
        
        return {
            "session_id": session_id,
            "meeting_type": meeting_type.value,
            "analysis": {
                "overall_summary": analysis.overall_summary,
                "key_arguments": analysis.key_arguments,
                "argument_strength": analysis.argument_strength,
                "speaking_time_analysis": analysis.speaking_time_analysis,
                "debate_flow": analysis.debate_flow,
                "winner_analysis": analysis.winner_analysis,
                "improvement_suggestions": analysis.improvement_suggestions
            },
            "ai_observer": ai_summary,
            "segments_analyzed": len(segments),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in session analysis: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

@router.get("/session-segments/{session_id}")
async def get_session_segments(session_id: str):
    """Get all segments for a session"""
    try:
        segments = live_manager.get_all_segments(session_id)
        
        # Include current session if still active
        current_session = None
        if session_id in live_manager.active_sessions:
            session_data = live_manager.active_sessions[session_id]
            current_session = {
                "segment_number": session_data.get("current_segment", 1),
                "start_time": session_data.get("segment_start_time", datetime.utcnow()).isoformat(),
                "current_text": session_data.get("total_text", ""),
                "is_active": True,
                "chunks_processed": session_data.get("chunks_processed", 0)
            }
        
        return {
            "session_id": session_id,
            "completed_segments": [
                {
                    "segment_number": seg["segment_number"],
                    "start_time": seg["start_time"].isoformat(),
                    "end_time": seg["end_time"].isoformat(),
                    "text": seg["text"],
                    "language": seg.get("language"),
                    "duration_seconds": (seg["end_time"] - seg["start_time"]).total_seconds(),
                    "transcription_count": len(seg.get("transcriptions", []))
                }
                for seg in segments
            ],
            "current_segment": current_session,
            "total_segments": len(segments) + (1 if current_session else 0)
        }
        
    except Exception as e:
        print(f"Error getting session segments: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get segments: {str(e)}")

@router.get("/combine-transcription/{session_id}")
async def combine_session_transcription(session_id: str):
    """
    Combine all transcription segments into a single overview
    """
    try:
        # First, try to get the complete session text if available
        combined_text = ""
        
        if session_id in live_manager.active_sessions:
            current_session = live_manager.active_sessions[session_id]
            session_full_text = current_session.get("session_full_text", "")
            
            if session_full_text:
                # Use the session-wide accumulated text
                combined_text = session_full_text
                print(f"Using session_full_text: '{combined_text[:100]}...'")
            else:
                # Fallback to segment-based approach
                print("No session_full_text available, using segment approach")
        
        # If no session-wide text available, fall back to combining segments
        if not combined_text.strip():
            segments = live_manager.get_all_segments(session_id)
            
            # Include current session if active
            if session_id in live_manager.active_sessions:
                current_session = live_manager.active_sessions[session_id]
                if current_session.get("total_text"):
                    segments.append({
                        "segment_number": current_session.get("current_segment", 1),
                        "text": current_session.get("total_text", ""),
                        "start_time": current_session.get("segment_start_time", datetime.utcnow()),
                        "end_time": datetime.utcnow(),
                        "transcriptions": current_session.get("all_transcriptions", [])
                    })
            
            if not segments:
                raise HTTPException(status_code=404, detail="No transcription data found for session")
            
            # Combine all text from segments
            for i, segment in enumerate(segments):
                if segment.get("text"):
                    # Add segment marker
                    combined_text += f"\n[Segment {segment['segment_number']}] "
                    combined_text += segment["text"] + " "
        
        if not combined_text.strip():
            raise HTTPException(status_code=404, detail="No transcription data found for session")
        
        # Calculate stats
        segments = live_manager.get_all_segments(session_id)
        total_duration = 0
        
        # Include current segment duration if active
        if session_id in live_manager.active_sessions:
            current_session = live_manager.active_sessions[session_id]
            segment_start = current_session.get("segment_start_time", datetime.utcnow())
            current_duration = (datetime.utcnow() - segment_start).total_seconds()
            total_duration += current_duration
        
        for segment in segments:
            if segment.get("start_time") and segment.get("end_time"):
                duration = (segment["end_time"] - segment["start_time"]).total_seconds()
                total_duration += duration
        
        word_count = len(combined_text.split())
        
        # Create overview using AI
        overview_prompt = f"""
        Create a comprehensive overview of the following transcribed conversation:

        FULL TRANSCRIPTION:
        {combined_text.strip()}

        Please provide:
        1. A clear summary of the main topics discussed
        2. Key points and highlights
        3. Overall flow of the conversation
        4. Any conclusions or decisions made

        Keep the overview concise but comprehensive.
        """
        
        try:
            from services.gemini_service import GeminiService
            gemini_service = GeminiService()
            overview = gemini_service.generate_content(overview_prompt)
        except Exception as e:
            print(f"AI overview generation failed: {e}")
            overview = "AI overview not available. Please review the combined transcription below."
        
        return {
            "session_id": session_id,
            "combined_transcription": combined_text.strip(),
            "overview": overview,
            "stats": {
                "total_segments": len(segments) + (1 if session_id in live_manager.active_sessions else 0),
                "total_duration_seconds": round(total_duration, 2),
                "total_words": word_count,
                "estimated_speaking_time_minutes": round(word_count / 150, 2)  # 150 words per minute average
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error combining transcription: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to combine transcription: {str(e)}")