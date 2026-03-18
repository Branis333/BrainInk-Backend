import base64
from typing import Any, Dict

from google.generativeai import protos


def build_inline_part(*, data: bytes, mime_type: str, display_name: str | None = None) -> protos.Part:
    """Return a Gemini part carrying an inline blob attachment.

    Args:
        data: Raw file bytes to send with the request.
        mime_type: Media type understood by Gemini (e.g. ``application/pdf``).
        display_name: Optional human friendly name (informational only - not sent to Gemini).
            For inline attachments, only mime_type and data are used by the Gemini API.
    """
    # Note: display_name is NOT a valid field for protos.Blob (that's Files API only).
    # For inline attachments, only mime_type and raw data are sent to Gemini.
    inline_data = protos.Blob(mime_type=mime_type, data=data)
    part = protos.Part(inline_data=inline_data)
    return part


def build_text_part(text: str) -> protos.Part:
    return protos.Part(text=text)
