"""
After-school endpoints package initializer.

Exposes submodules to ensure reliable imports across environments (including
non-namespace-package setups) and makes `from Endpoints.after_school import <module>`
work consistently.
"""

from . import course
from . import grades
from . import uploads
from . import reading_assistant
from . import assignments
from . import ai_tutor
from . import transcribe

__all__ = [
    "course",
    "grades",
    "uploads",
    "reading_assistant",
    "assignments",
    "ai_tutor",
    "transcribe",
]
