from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile

from db.connection import db_dependency
from Endpoints.auth import get_current_user
from Endpoints.utils import ensure_user_role
from models.study_area_models import UserRole
from schemas.lesson_schems import (
	LessonPlanCreate,
	LessonPlanDashboardResponse,
	LessonPlanResponse,
	LessonPlanUpdate,
)
from services.lesson_services import (
	create_lesson_plan,
	deactivate_lesson_plan,
	generate_and_create_lesson_plan,
	get_lesson_plan,
	list_lesson_dashboard,
	update_lesson_plan,
)


router = APIRouter(prefix="/lessons", tags=["Lesson Plans"])
user_dependency = Depends(get_current_user)

MAX_SOURCE_FILE_SIZE = 15 * 1024 * 1024  # 15MB for optional lesson source PDF
ALLOWED_SOURCE_EXTENSIONS = {".pdf"}


def _parse_objectives_text(value: Optional[str]) -> List[str]:
	if not value:
		return []
	tokens = [piece.strip() for chunk in value.split("\n") for piece in chunk.split(",")]
	return [token for token in tokens if token]


@router.post("", response_model=LessonPlanResponse)
async def create_teacher_lesson_plan(
	payload: LessonPlanCreate,
	db: db_dependency,
	current_user: dict = user_dependency,
):
	"""Create a lesson plan manually for a specific classroom and subject."""
	ensure_user_role(db, current_user["user_id"], UserRole.teacher)
	return create_lesson_plan(
		db,
		current_user["user_id"],
		classroom_id=payload.classroom_id,
		subject_id=payload.subject_id,
		title=payload.title,
		description=payload.description,
		duration_minutes=payload.duration_minutes,
		learning_objectives=payload.learning_objectives,
		activities=payload.activities,
		materials_needed=payload.materials_needed,
		assessment_strategy=payload.assessment_strategy,
		homework=payload.homework,
		references=[item.model_dump() for item in payload.references],
	)


@router.post("/generate", response_model=LessonPlanResponse)
async def generate_teacher_lesson_plan(
	db: db_dependency,
	current_user: dict = user_dependency,
	classroom_id: int = Form(..., description="Classroom ID"),
	subject_id: int = Form(..., description="Subject ID"),
	title: str = Form(..., min_length=3, max_length=200, description="Lesson title"),
	description: str = Form(..., min_length=10, max_length=4000, description="Lesson context/description"),
	duration_minutes: int = Form(..., ge=10, le=240, description="Planned lesson duration in minutes"),
	learning_objectives: Optional[str] = Form(None, description="Optional comma/newline separated objectives"),
	source_file: Optional[UploadFile] = File(None, description="Optional PDF source material for generation"),
):
	"""Generate and save an AI lesson plan with optional PDF context and resource references."""
	ensure_user_role(db, current_user["user_id"], UserRole.teacher)

	file_bytes = None
	file_name = None
	file_mime_type = None

	if source_file is not None:
		if not source_file.filename:
			raise HTTPException(status_code=400, detail="Source file has no filename")

		file_ext = "." + source_file.filename.rsplit(".", 1)[-1].lower() if "." in source_file.filename else ""
		if file_ext not in ALLOWED_SOURCE_EXTENSIONS:
			raise HTTPException(status_code=400, detail="Only PDF files are supported as source material")

		file_bytes = await source_file.read()
		if not file_bytes:
			raise HTTPException(status_code=400, detail="Uploaded source file is empty")
		if len(file_bytes) > MAX_SOURCE_FILE_SIZE:
			raise HTTPException(status_code=400, detail="Source file exceeds 15MB limit")

		file_name = source_file.filename
		file_mime_type = source_file.content_type or "application/pdf"

	return await generate_and_create_lesson_plan(
		db,
		current_user["user_id"],
		classroom_id=classroom_id,
		subject_id=subject_id,
		title=title,
		description=description,
		duration_minutes=duration_minutes,
		learning_objectives=_parse_objectives_text(learning_objectives),
		file_bytes=file_bytes,
		file_name=file_name,
		file_mime_type=file_mime_type,
	)


@router.get("/dashboard", response_model=LessonPlanDashboardResponse)
async def get_teacher_lesson_dashboard(
	db: db_dependency,
	current_user: dict = user_dependency,
	classroom_id: Optional[int] = Query(None, description="Filter by classroom"),
	subject_id: Optional[int] = Query(None, description="Filter by subject"),
	active_only: bool = Query(True, description="Show active lessons only"),
	limit: int = Query(50, ge=1, le=200, description="Maximum lesson plans to return"),
):
	"""Teacher dashboard feed of lesson plans."""
	ensure_user_role(db, current_user["user_id"], UserRole.teacher)
	return list_lesson_dashboard(
		db,
		current_user["user_id"],
		classroom_id=classroom_id,
		subject_id=subject_id,
		active_only=active_only,
		limit=limit,
	)


@router.get("/{lesson_id}", response_model=LessonPlanResponse)
async def get_teacher_lesson(
	lesson_id: int,
	db: db_dependency,
	current_user: dict = user_dependency,
):
	ensure_user_role(db, current_user["user_id"], UserRole.teacher)
	return get_lesson_plan(db, current_user["user_id"], lesson_id)


@router.put("/{lesson_id}", response_model=LessonPlanResponse)
async def update_teacher_lesson(
	lesson_id: int,
	payload: LessonPlanUpdate,
	db: db_dependency,
	current_user: dict = user_dependency,
):
	ensure_user_role(db, current_user["user_id"], UserRole.teacher)
	update_payload = payload.model_dump(exclude_unset=True)
	if "references" in update_payload and update_payload["references"] is not None:
		update_payload["references"] = [item.model_dump() for item in payload.references or []]
	return update_lesson_plan(db, current_user["user_id"], lesson_id, update_payload)


@router.delete("/{lesson_id}")
async def delete_teacher_lesson(
	lesson_id: int,
	db: db_dependency,
	current_user: dict = user_dependency,
):
	ensure_user_role(db, current_user["user_id"], UserRole.teacher)
	return deactivate_lesson_plan(db, current_user["user_id"], lesson_id)
