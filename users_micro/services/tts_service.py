"""
Text-to-Speech Service for Reading Assistant
Generates pronunciation audio files for words and phrases
"""

import os
import asyncio
import tempfile
import uuid
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime
import json

# Try to import Google TTS - will use fallback if not available
try:
    from google.cloud import texttospeech
    GOOGLE_TTS_AVAILABLE = True
except ImportError:
    GOOGLE_TTS_AVAILABLE = False

# Try alternative TTS libraries
try:
    import pyttsx3
    PYTTSX3_AVAILABLE = True
except ImportError:
    PYTTSX3_AVAILABLE = False

try:
    import azure.cognitiveservices.speech as speechsdk
    AZURE_TTS_AVAILABLE = True
except ImportError:
    AZURE_TTS_AVAILABLE = False


class TTSService:
    """Text-to-Speech service for pronunciation help"""
    
    def __init__(self):
        self.tts_method = self._detect_available_tts()
        self.audio_cache = {}  # Cache generated audio files
        self.output_dir = Path(tempfile.gettempdir()) / "reading_assistant_tts"
        self.output_dir.mkdir(exist_ok=True)
        
        print(f"🔊 TTS Service initialized using: {self.tts_method}")
    
    def _detect_available_tts(self) -> str:
        """Detect which TTS method is available"""
        
        # Check for Google Cloud TTS (best quality)
        if GOOGLE_TTS_AVAILABLE and os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
            return "google_cloud"
        
        # Check for Azure TTS
        if AZURE_TTS_AVAILABLE and os.getenv("AZURE_SPEECH_KEY"):
            return "azure"
        
        # Check for local pyttsx3
        if PYTTSX3_AVAILABLE:
            return "pyttsx3"
        
        # Fallback to system TTS or mock
        return "system_fallback"
    
    async def generate_pronunciation_audio(
        self,
        text: str,
        voice_type: str = "child_friendly",
        speed: float = 0.8,  # Slower for learning
        cache_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate pronunciation audio for text
        
        Args:
            text: Text to convert to speech
            voice_type: Type of voice (child_friendly, teacher, clear)
            speed: Speech speed (0.5 = slow, 1.0 = normal, 1.5 = fast)
            cache_key: Optional key for caching
            
        Returns:
            {
                "success": bool,
                "audio_url": str,
                "audio_file": str,
                "duration_seconds": float,
                "text": str
            }
        """
        
        try:
            # Generate cache key if not provided
            if not cache_key:
                cache_key = f"{text}_{voice_type}_{speed}".replace(" ", "_").lower()
            
            # Check cache first
            if cache_key in self.audio_cache:
                cached_result = self.audio_cache[cache_key]
                if os.path.exists(cached_result["audio_file"]):
                    print(f"🎯 Using cached TTS for: '{text}'")
                    return cached_result
            
            # Generate new audio based on available method
            if self.tts_method == "google_cloud":
                result = await self._generate_google_cloud_tts(text, voice_type, speed)
            elif self.tts_method == "azure":
                result = await self._generate_azure_tts(text, voice_type, speed)
            elif self.tts_method == "pyttsx3":
                result = await self._generate_pyttsx3_tts(text, voice_type, speed)
            else:
                result = await self._generate_fallback_tts(text, voice_type, speed)
            
            # Cache the result
            self.audio_cache[cache_key] = result
            
            print(f"🔊 Generated TTS audio for: '{text}' ({result['duration_seconds']:.1f}s)")
            return result
            
        except Exception as e:
            print(f"❌ TTS generation failed for '{text}': {e}")
            return {
                "success": False,
                "audio_url": None,
                "audio_file": None,
                "duration_seconds": 0.0,
                "text": text,
                "error": str(e)
            }
    
    async def _generate_google_cloud_tts(
        self,
        text: str,
        voice_type: str,
        speed: float
    ) -> Dict[str, Any]:
        """Generate TTS using Google Cloud Text-to-Speech"""
        
        client = texttospeech.TextToSpeechClient()
        
        # Select voice based on type
        voice_config = {
            "child_friendly": {
                "language_code": "en-US",
                "name": "en-US-Standard-C",  # Female, clear
                "ssml_gender": texttospeech.SsmlVoiceGender.FEMALE
            },
            "teacher": {
                "language_code": "en-US", 
                "name": "en-US-Standard-B",  # Male, authoritative
                "ssml_gender": texttospeech.SsmlVoiceGender.MALE
            },
            "clear": {
                "language_code": "en-US",
                "name": "en-US-Standard-A",  # Female, very clear
                "ssml_gender": texttospeech.SsmlVoiceGender.FEMALE
            }
        }
        
        selected_voice = voice_config.get(voice_type, voice_config["child_friendly"])
        
        # Configure synthesis
        synthesis_input = texttospeech.SynthesisInput(text=text)
        voice = texttospeech.VoiceSelectionParams(
            language_code=selected_voice["language_code"],
            name=selected_voice["name"],
            ssml_gender=selected_voice["ssml_gender"]
        )
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=speed,
            pitch=2.0 if voice_type == "child_friendly" else 0.0  # Slightly higher pitch for kids
        )
        
        # Generate audio
        response = client.synthesize_speech(
            input=synthesis_input,
            voice=voice, 
            audio_config=audio_config
        )
        
        # Save to file
        filename = f"tts_{uuid.uuid4().hex}.mp3"
        file_path = self.output_dir / filename
        
        with open(file_path, "wb") as f:
            f.write(response.audio_content)
        
        # Estimate duration (rough calculation)
        word_count = len(text.split())
        estimated_duration = (word_count * 0.6) / speed  # ~0.6 seconds per word
        
        return {
            "success": True,
            "audio_url": f"/reading-assistant/pronunciation-audio/{filename}",
            "audio_file": str(file_path),
            "duration_seconds": estimated_duration,
            "text": text
        }
    
    async def _generate_pyttsx3_tts(
        self,
        text: str,
        voice_type: str,
        speed: float
    ) -> Dict[str, Any]:
        """Generate TTS using pyttsx3 (local/offline)"""
        
        def generate_audio():
            engine = pyttsx3.init()
            
            # Configure voice
            voices = engine.getProperty('voices')
            if voices:
                # Try to select appropriate voice
                if voice_type == "child_friendly" and len(voices) > 1:
                    engine.setProperty('voice', voices[1].id)  # Usually female
                else:
                    engine.setProperty('voice', voices[0].id)
            
            # Set speed and pitch
            rate = engine.getProperty('rate')
            engine.setProperty('rate', int(rate * speed))
            
            # Save to file
            filename = f"tts_{uuid.uuid4().hex}.wav"
            file_path = self.output_dir / filename
            
            engine.save_to_file(text, str(file_path))
            engine.runAndWait()
            
            return str(file_path), filename
        
        # Run in thread to avoid blocking
        loop = asyncio.get_event_loop()
        file_path, filename = await loop.run_in_executor(None, generate_audio)
        
        # Estimate duration
        word_count = len(text.split())
        estimated_duration = (word_count * 0.6) / speed
        
        return {
            "success": True,
            "audio_url": f"/reading-assistant/pronunciation-audio/{filename}",
            "audio_file": file_path,
            "duration_seconds": estimated_duration,
            "text": text
        }
    
    async def _generate_fallback_tts(
        self,
        text: str,
        voice_type: str,
        speed: float
    ) -> Dict[str, Any]:
        """Fallback TTS when no service is available"""
        
        # Create a mock audio file or use system TTS
        filename = f"tts_fallback_{uuid.uuid4().hex}.txt"
        file_path = self.output_dir / filename
        
        # Save text file as placeholder
        with open(file_path, "w") as f:
            f.write(f"Pronunciation: {text}\nVoice: {voice_type}\nSpeed: {speed}")
        
        word_count = len(text.split())
        estimated_duration = (word_count * 0.6) / speed
        
        return {
            "success": True,
            "audio_url": f"/reading-assistant/pronunciation-audio/{filename}",
            "audio_file": str(file_path),
            "duration_seconds": estimated_duration,
            "text": text,
            "fallback": True
        }
    
    async def generate_word_pronunciation(
        self,
        word: str,
        phonetic_hint: Optional[str] = None,
        context: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate pronunciation for a single word with phonetic guidance"""
        
        # Create pronunciation text with phonetic hints
        if phonetic_hint:
            pronunciation_text = f"{word}. {phonetic_hint}. {word}."
        elif context:
            pronunciation_text = f"{word}. As in {context}. {word}."
        else:
            pronunciation_text = f"{word}. {word}."
        
        return await self.generate_pronunciation_audio(
            text=pronunciation_text,
            voice_type="child_friendly",
            speed=0.7,  # Slower for individual words
            cache_key=f"word_{word}_{phonetic_hint or 'default'}"
        )
    
    async def generate_sentence_pronunciation(
        self,
        sentence: str,
        highlight_words: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Generate pronunciation for a full sentence with word emphasis"""
        
        if highlight_words:
            # Add slight pauses around highlighted words
            highlighted_sentence = sentence
            for word in highlight_words:
                highlighted_sentence = highlighted_sentence.replace(
                    word, f"... {word} ..."
                )
            pronunciation_text = highlighted_sentence
        else:
            pronunciation_text = sentence
        
        return await self.generate_pronunciation_audio(
            text=pronunciation_text,
            voice_type="teacher",
            speed=0.8,
            cache_key=f"sentence_{hash(sentence)}_{len(highlight_words or [])}"
        )
    
    def cleanup_old_files(self, max_age_hours: int = 24):
        """Clean up old TTS files to save space"""
        
        try:
            current_time = datetime.now()
            cleaned_count = 0
            
            for file_path in self.output_dir.glob("tts_*"):
                if file_path.is_file():
                    file_age = current_time - datetime.fromtimestamp(file_path.stat().st_mtime)
                    if file_age.total_seconds() > (max_age_hours * 3600):
                        file_path.unlink()
                        cleaned_count += 1
            
            print(f"🧹 Cleaned up {cleaned_count} old TTS files")
            
        except Exception as e:
            print(f"⚠️ TTS cleanup warning: {e}")


# Global TTS service instance
tts_service = TTSService()