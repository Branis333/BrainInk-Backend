"""Azure Cognitive Services Text-to-Speech helper.

Provides a reusable async-friendly wrapper that turns text into WAV audio bytes
without blocking the event loop. The heavy Azure SDK work is executed inside a
thread so the FastAPI worker stays responsive.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import os
from typing import Any, Dict, Optional
from xml.sax.saxutils import escape

try:
    import azure.cognitiveservices.speech as speechsdk
except ImportError:  # pragma: no cover - optional dependency checked at runtime
    speechsdk = None  # type: ignore

logger = logging.getLogger(__name__)

_DEFAULT_SAMPLE_RATE = 24000
_VOICE_PREFIX_MAP = {
    "af": "en-GB-LibbyNeural",
    "bf": "en-US-AvaNeural",
    "am": "en-US-GuyNeural",
    "bm": "en-US-DavisNeural",
    "e": "es-ES-ElviraNeural",
    "f": "fr-FR-DeniseNeural",
    "h": "hi-IN-NeerjaNeural",
    "i": "it-IT-ElsaNeural",
    "j": "ja-JP-NanamiNeural",
    "p": "pt-BR-FranciscaNeural",
    "z": "zh-CN-XiaoxiaoNeural",
}


class AzureTTSService:
    """Thin Azure TTS wrapper that returns both bytes and base64 payloads."""

    def __init__(self) -> None:
        self._key = os.getenv("AZURE_SPEECH_KEY")
        self._region = os.getenv("AZURE_SPEECH_REGION")
        self._default_voice = os.getenv("AZURE_TTS_DEFAULT_VOICE", "en-US-AvaNeural")
        self._sample_rate = int(os.getenv("AZURE_TTS_SAMPLE_RATE", str(_DEFAULT_SAMPLE_RATE)))
        self._lock = asyncio.Lock()

        if not speechsdk:
            logger.warning("azure-cognitiveservices-speech is not installed; Azure TTS disabled")
        elif not self._key or not self._region:
            logger.info("Azure Speech credentials not configured; set AZURE_SPEECH_KEY and AZURE_SPEECH_REGION")

    def _refresh_credentials(self) -> None:
        if not self._key:
            self._key = os.getenv("AZURE_SPEECH_KEY")
        if not self._region:
            self._region = os.getenv("AZURE_SPEECH_REGION")

    @property
    def is_available(self) -> bool:
        self._refresh_credentials()
        return bool(speechsdk and self._key and self._region)

    async def synthesize(self, *, text: str, voice: Optional[str] = None, speed: float = 1.0) -> Dict[str, Any]:
        """Generate Azure speech audio for the provided text."""

        normalized = (text or "").strip()
        if not normalized:
            raise ValueError("Text to synthesize cannot be empty")
        if not self.is_available:
            raise RuntimeError("Azure Speech SDK is unavailable or credentials are missing")

        resolved_voice = self._resolve_voice(voice)
        speed = max(0.5, min(speed, 1.5))

        style = (os.getenv("AZURE_TTS_STYLE") or "").strip() or None

        try:
            async with self._lock:
                audio_bytes = await asyncio.to_thread(
                    self._run_synthesis,
                    normalized,
                    resolved_voice,
                    speed,
                    style,
                )
        except RuntimeError as exc:
            if style:
                logger.warning(
                    "Azure TTS style failed; retrying without style",
                    extra={"voice": resolved_voice, "style": style, "error": str(exc)},
                )
                async with self._lock:
                    audio_bytes = await asyncio.to_thread(
                        self._run_synthesis,
                        normalized,
                        resolved_voice,
                        speed,
                        None,
                    )
            else:
                raise

        duration_seconds = len(audio_bytes) / (self._sample_rate * 2)
        audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
        return {
            "audio_bytes": audio_bytes,
            "audio_base64": audio_b64,
            "mime_type": "audio/wav",
            "sample_rate": self._sample_rate,
            "voice": resolved_voice,
            "duration_seconds": duration_seconds,
            "provider": "azure",
        }

    def _run_synthesis(self, text: str, voice: str, speed: float, style: Optional[str]) -> bytes:
        if speechsdk is None:
            raise RuntimeError("azure-cognitiveservices-speech is not installed")

        speech_config = speechsdk.SpeechConfig(subscription=self._key, region=self._region)
        speech_config.speech_synthesis_voice_name = voice
        speech_config.set_speech_synthesis_output_format(
            speechsdk.SpeechSynthesisOutputFormat.Riff24Khz16BitMonoPcm
        )
        synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=None)

        ssml = self._build_ssml(text, voice, speed, style)
        if ssml:
            result = synthesizer.speak_ssml_async(ssml).get()
        else:
            result = synthesizer.speak_text_async(text).get()

        if result.reason != speechsdk.ResultReason.SynthesizingAudioCompleted:
            error = getattr(result, "error_details", None) or "Azure TTS failed"
            logger.error("Azure TTS synthesis error", extra={"voice": voice, "style": style, "details": error})
            raise RuntimeError(error)
        return bytes(result.audio_data)

    def _resolve_voice(self, requested: Optional[str]) -> str:
        if not requested:
            return self._default_voice

        normalized = requested.strip()
        if "Neural" in normalized:
            return normalized

        prefix = normalized.split("_", 1)[0].lower()
        return _VOICE_PREFIX_MAP.get(prefix, self._default_voice)

    def _build_ssml(self, text: str, voice: str, speed: float, style: Optional[str]) -> Optional[str]:
        if abs(speed - 1.0) < 0.05 and not style:
            return None
        rate_percent = int(speed * 100)
        escaped_text = escape(text)
        style_open = f"<mstts:express-as style='{style}'>" if style else ""
        style_close = "</mstts:express-as>" if style else ""
        return (
            "<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' "
            "xmlns:mstts='https://www.w3.org/2001/mstts'>"
            f"<voice name='{voice}'><prosody rate='{rate_percent}%'>"
            f"{style_open}{escaped_text}{style_close}</prosody></voice></speak>"
        )


azure_tts_service = AzureTTSService()