"""Kokoro TTS integration for Kana.

Provides a cached wrapper around the Kokoro ONNX pipeline so we can reuse loaded
models across requests without blocking the event loop. The synthesis call is
run in a worker thread because Torchaudio/ONNX execution is CPU-bound.
"""

import asyncio
import base64
import io
import logging
import os
from typing import Any, Dict, Optional

import numpy as np
import soundfile as sf
from kokoro import KPipeline

logger = logging.getLogger(__name__)

DEFAULT_VOICE = os.getenv("KOKORO_DEFAULT_VOICE", "bf_isabella")
DEFAULT_SPEED = float(os.getenv("KOKORO_DEFAULT_VOICE_SPEED", "1.0"))
MAX_CHARS = int(os.getenv("KOKORO_TTS_MAX_CHARS", "1200"))
SAMPLE_RATE = 24_000

VOICE_REGISTRY = {
    "af_bella",
    "af_nicole",
    "af_sarah",
    "af_sky",
    "bf_emma",
    "bf_isabella",
    "am_adam",
    "am_michael",
    "bm_george",
    "bm_lewis",
}

LANG_CODE_MAP = {
    "a": "a",  # American English
    "b": "b",  # British English
    "e": "e",  # Spanish
    "f": "f",  # French
    "h": "h",  # Hindi
    "i": "i",  # Italian
    "j": "j",  # Japanese (requires misaki[ja])
    "p": "p",  # Portuguese (pt-BR)
    "z": "z",  # Mandarin Chinese
}


class KokoroTTSService:
    """Small helper that lazily loads a Kokoro pipeline per language."""

    def __init__(self) -> None:
        self._pipelines: Dict[str, KPipeline] = {}
        self._locks: Dict[str, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()

    async def synthesize(self, *, text: str, voice: Optional[str] = None, speed: float = DEFAULT_SPEED) -> Dict[str, Any]:
        normalized_text = (text or "").strip()
        if not normalized_text:
            raise ValueError("Text to synthesize cannot be empty")
        if len(normalized_text) > MAX_CHARS:
            raise ValueError(f"Text is too long for Kokoro (max {MAX_CHARS} characters)")

        voice_choice = self._normalize_voice(voice)
        lang_code = self._infer_lang_code(voice_choice)
        speed = max(0.5, min(speed, 1.5))

        pipeline = await self._get_pipeline(lang_code)

        def _generate() -> Dict[str, Any]:
            audio_chunks = []
            try:
                generator = pipeline(
                    normalized_text,
                    voice=voice_choice,
                    speed=speed,
                    split_pattern=r"\n+",
                )
                for _, _, audio in generator:
                    audio_chunks.append(audio)
            except Exception as exc:  # noqa: BLE001
                raise RuntimeError(f"Kokoro generation failed: {exc}") from exc

            if not audio_chunks:
                raise RuntimeError("Kokoro returned no audio")

            waveform = np.concatenate(audio_chunks)
            buffer = io.BytesIO()
            sf.write(buffer, waveform, SAMPLE_RATE, format="WAV")
            duration_seconds = waveform.shape[0] / SAMPLE_RATE
            return {
                "audio_bytes": buffer.getvalue(),
                "duration_seconds": duration_seconds,
            }

        result = await asyncio.to_thread(_generate)
        audio_b64 = base64.b64encode(result["audio_bytes"]).decode("utf-8")

        return {
            "audio_base64": audio_b64,
            "mime_type": "audio/wav",
            "sample_rate": SAMPLE_RATE,
            "voice": voice_choice,
            "duration_seconds": result["duration_seconds"],
        }

    async def _get_pipeline(self, lang_code: str) -> KPipeline:
        async with self._global_lock:
            if lang_code in self._pipelines:
                return self._pipelines[lang_code]
            lock = self._locks.setdefault(lang_code, asyncio.Lock())

        async with lock:
            # Another coroutine may have initialized it while we were waiting
            if lang_code in self._pipelines:
                return self._pipelines[lang_code]

            def _init_pipeline() -> KPipeline:
                logger.info("Loading Kokoro pipeline", extra={"lang_code": lang_code})
                return KPipeline(lang_code=lang_code)

            pipeline = await asyncio.to_thread(_init_pipeline)
            async with self._global_lock:
                self._pipelines[lang_code] = pipeline
            return pipeline

    def _normalize_voice(self, voice: Optional[str]) -> str:
        choice = (voice or DEFAULT_VOICE).strip()
        if choice not in VOICE_REGISTRY:
            logger.warning("Unsupported Kokoro voice requested; falling back to default", extra={"voice": choice})
            return DEFAULT_VOICE
        return choice

    def _infer_lang_code(self, voice: str) -> str:
        prefix = voice.split("_", 1)[0] if voice else ""
        first_char = (prefix or "a")[0].lower()
        return LANG_CODE_MAP.get(first_char, "a")


kokoro_tts_service = KokoroTTSService()
