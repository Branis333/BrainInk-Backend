from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from db.connection import db_dependency
from Endpoints.auth import get_current_user
from schemas.afterschool_schema import ProgressDigestOut
from services.progress_service import progress_service


router = APIRouter(prefix="/after-school/progress", tags=["After-School Progress Digest"])

user_dependency = Depends(get_current_user)


@router.post("/weekly/generate", response_model=ProgressDigestOut)
async def generate_weekly_progress(
	db: db_dependency,
	current_user: dict = user_dependency,
):
	"""
	Generate and persist a weekly (last 7 days) progress digest for the current user.

	Uses assignment feedback (teacher or AI) to produce 2 short paragraphs summarizing
	strengths and next steps. Idempotent per week: calling again updates this week's digest.
	"""
	user_id = current_user["user_id"]
	digest = await progress_service.generate_weekly_digest(db, user_id=user_id)
	return digest


@router.get("/weekly", response_model=ProgressDigestOut)
async def get_weekly_progress(
	db: db_dependency,
	current_user: dict = user_dependency,
	reference_date: Optional[datetime] = Query(None, description="Any date within the desired 7-day window (defaults to now)"),
):
	"""
	Return the stored weekly digest for the 7-day window containing reference_date.
	If none exists yet, this returns 404 prompting the client to generate.
	"""
	user_id = current_user["user_id"]
	digest = progress_service.get_weekly_digest(db, user_id=user_id, reference_date=reference_date)
	if not digest:
		raise HTTPException(status_code=404, detail="No weekly digest found for this period. Generate first.")
	return digest


@router.post("/course/{course_id}/generate", response_model=ProgressDigestOut)
async def generate_course_progress(
	course_id: int,
	db: db_dependency,
	current_user: dict = user_dependency,
):
	"""
	Generate and persist a course-level digest for the current user.

	Aggregates all assignment feedback for this course and creates two concise paragraphs.
	Re-running will update the existing course digest.
	"""
	user_id = current_user["user_id"]
	digest = await progress_service.generate_course_digest(db, user_id=user_id, course_id=course_id)
	return digest


@router.get("/course/{course_id}", response_model=ProgressDigestOut)
async def get_course_progress(
	course_id: int,
	db: db_dependency,
	current_user: dict = user_dependency,
):
	"""
	Return the most recently updated course digest for this user and course.
	"""
	user_id = current_user["user_id"]
	digest = progress_service.get_course_digest(db, user_id=user_id, course_id=course_id)
	if not digest:
		raise HTTPException(status_code=404, detail="No course digest found. Generate first.")
	return digest

