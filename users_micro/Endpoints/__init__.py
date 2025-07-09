# Endpoints package initialization
from . import auth
from . import school_management
from . import academic_management
from . import grades
from . import school_invitations
from . import class_room
from . import modules

__all__ = [
    "auth",
    "school_management", 
    "academic_management",
    "grades",
    "school_invitations",
    "class_room",
    "modules"
]
