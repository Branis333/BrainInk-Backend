import asyncio
import logging
import mimetypes
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import google.generativeai as genai

from services.gemini_service import gemini_service
from tools.inline_attachment import build_inline_part

logger = logging.getLogger(__name__)

# Accept common mobile/desktop audio containers
SUPPORTED_AUDIO_MIME: Dict[str, str] = {
	"wav": "audio/wav",
	"mp3": "audio/mpeg",
	"m4a": "audio/mp4",
	"aac": "audio/aac",
	"ogg": "audio/ogg",
	"oga": "audio/ogg",
	"flac": "audio/flac",
	"webm": "audio/webm",
}

MAX_AUDIO_BYTES = 25 * 1024 * 1024  # 25 MB guardrail


class TranscribeService:
	"""Lightweight Gemini-powered audio transcription for the agent."""

	@staticmethod
	def _detect_mime(filename: str) -> Optional[str]:
		ext = Path(filename or "").suffix.lower().lstrip(".")
		if ext and ext in SUPPORTED_AUDIO_MIME:
			return SUPPORTED_AUDIO_MIME[ext]

		guessed, _ = mimetypes.guess_type(filename or "")
		if guessed and guessed.startswith("audio/"):
			return guessed
		return None

	@staticmethod
	def _validate_audio(file_bytes: bytes, filename: str) -> Tuple[str, str]:
		if not file_bytes:
			raise ValueError("Audio file is empty")
		if len(file_bytes) > MAX_AUDIO_BYTES:
			raise ValueError("Audio file exceeds 25MB limit")

		mime_type = TranscribeService._detect_mime(filename)
		if not mime_type:
			raise ValueError("Unsupported or unknown audio type")

		safe_name = filename or "audio"
		return mime_type, safe_name

	async def transcribe_audio(
		self,
		*,
		file_bytes: bytes,
		filename: str,
		instructions: Optional[str] = None,
	) -> Dict[str, Any]:
		"""Send audio to Gemini and return a plain-text transcript."""

		mime_type, safe_name = self._validate_audio(file_bytes, filename)

		# Build inline audio part for Gemini (no temp files needed)
		audio_part = build_inline_part(
			data=file_bytes,
			mime_type=mime_type,
			display_name=safe_name,
		)

		# Compose prompt with optional caller instructions
		custom_rules = f"Additional instructions: {instructions}\n" if instructions else ""
		prompt = (
			"You are an exacting transcription service. "
			"Listen to the attached audio and return a clean transcript.\n"
			"Rules:\n"
			"- Keep the spoken order; do not summarize or omit meaningful words.\n"
			"- Remove filler sounds like 'um', 'uh', 'ah' unless they change intent.\n"
			"- Do not hallucinate or rewrite slang; keep speaker wording.\n"
			"- Punctuate lightly for readability.\n"
			f"{custom_rules}"
			"Return ONLY the transcript text with no metadata or formatting."
		)

		# Force this service to use Gemini 2.5 Flash only (no fallbacks)
		ordered_models = ["gemini-2.5-flash"]

		last_error: Optional[Exception] = None

		for model_name in ordered_models:
			try:
				payload = gemini_service._build_content_payload(prompt, [audio_part])
				model = gemini_service.config.get_model(model_name)
				response = await asyncio.to_thread(
					lambda: model.generate_content(
						payload,
						generation_config=genai.types.GenerationConfig(
							temperature=0.1,
							max_output_tokens=1200,
						),
						safety_settings=gemini_service.config.get_safety_settings(),
					)
				)

				transcript = gemini_service._collect_candidate_text(response).strip()
				gemini_service._log_candidate_metadata(response, model_name=model_name)

				if not transcript:
					raise ValueError("Gemini returned empty transcript")

				return {
					"success": True,
					"transcript": transcript,
					"model": model_name,
					"filename": safe_name,
					"mime_type": mime_type,
				}
			except Exception as exc:  # noqa: BLE001
				last_error = exc
				logger.warning(
					"Gemini transcription attempt failed",
					extra={"model": model_name, "error": str(exc)},
				)
				continue

		raise RuntimeError(f"Transcription failed: {last_error}")


transcribe_service = TranscribeService()
