from fastapi import APIRouter, Depends

from db.connection import db_dependency
from Endpoints.auth import get_current_user
from Endpoints.after_school.grades import get_assignment_status_with_grade

router = APIRouter(prefix="/after-school/assignments", tags=["After-School Assignments (Public)"])

# Dependency for current user
user_dependency = Depends(get_current_user)

@router.get("/{assignment_id}/status")
async def get_assignment_status_public(
    assignment_id: int,
    db: db_dependency,
    current_user: dict = user_dependency
):
    """
    Public assignment status endpoint expected by mobile app at
    GET /after-school/assignments/{assignment_id}/status

    Returns the richer status payload (grade + attempts) expected by the mobile app.
    Delegates to the shared implementation used by the sessions router so the
    data stays consistent regardless of which endpoint the client calls.
    """
    return await get_assignment_status_with_grade(
        assignment_id=assignment_id,
        db=db,
        current_user=current_user,
    )
