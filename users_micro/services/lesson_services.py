import json
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

from models.study_area_models import LessonPlan, Teacher, Subject, Classroom
from services.gemma_services.lessonplan_services import gemma_lessonplan_service


def _as_json_list(value: Optional[List[Any]]) -> str:
	return json.dumps(value or [])


def _safe_json_list(value: Optional[str]) -> List[Any]:
	if not value:
		return []
	try:
		loaded = json.loads(value)
		return loaded if isinstance(loaded, list) else []
	except Exception:
		return []


def _clean_string_list(values: Optional[List[Any]]) -> List[str]:
	cleaned: List[str] = []
	for item in values or []:
		text = str(item).strip()
		if text:
			cleaned.append(text)
	return cleaned


def _lesson_to_dict(lesson: LessonPlan) -> Dict[str, Any]:
	teacher_name = ""
	if lesson.teacher and lesson.teacher.user:
		teacher_name = f"{lesson.teacher.user.fname} {lesson.teacher.user.lname}".strip()

	return {
		"id": lesson.id,
		"teacher_id": lesson.teacher_id,
		"classroom_id": lesson.classroom_id,
		"subject_id": lesson.subject_id,
		"title": lesson.title,
		"description": lesson.description,
		"duration_minutes": lesson.duration_minutes,
		"learning_objectives": _safe_json_list(lesson.learning_objectives),
		"activities": _safe_json_list(lesson.activities),
		"materials_needed": _safe_json_list(lesson.materials_needed),
		"assessment_strategy": lesson.assessment_strategy,
		"homework": lesson.homework,
		"references": _safe_json_list(lesson.references),
		"classroom_name": lesson.classroom.name if lesson.classroom else None,
		"subject_name": lesson.subject.name if lesson.subject else None,
		"teacher_name": teacher_name or None,
		"source_filename": lesson.source_filename,
		"generated_by_ai": lesson.generated_by_ai,
		"created_date": lesson.created_date,
		"updated_date": lesson.updated_date,
		"is_active": lesson.is_active,
	}


def _get_teacher_profile(db: Session, user_id: int) -> Teacher:
	teacher = db.query(Teacher).options(joinedload(Teacher.user)).filter(Teacher.user_id == user_id).first()
	if not teacher:
		raise HTTPException(status_code=404, detail="Teacher profile not found")
	return teacher


def _validate_lesson_scope(db: Session, teacher: Teacher, classroom_id: int, subject_id: int) -> Tuple[Classroom, Subject]:
	classroom = db.query(Classroom).filter(Classroom.id == classroom_id, Classroom.is_active == True).first()
	if not classroom:
		raise HTTPException(status_code=404, detail="Classroom not found")

	subject = db.query(Subject).filter(Subject.id == subject_id, Subject.is_active == True).first()
	if not subject:
		raise HTTPException(status_code=404, detail="Subject not found")

	if classroom.school_id != teacher.school_id:
		raise HTTPException(status_code=403, detail="Classroom is outside your school")
	if subject.school_id != teacher.school_id:
		raise HTTPException(status_code=403, detail="Subject is outside your school")

	teacher_subject = db.query(Subject).join(Subject.teachers).filter(
		Subject.id == subject_id,
		Teacher.id == teacher.id
	).first()
	if not teacher_subject:
		raise HTTPException(status_code=403, detail="You are not assigned to this subject")

	if classroom.teacher_id and classroom.teacher_id != teacher.id:
		raise HTTPException(status_code=403, detail="Classroom is assigned to another teacher")

	return classroom, subject


def create_lesson_plan(
	db: Session,
	user_id: int,
	*,
	classroom_id: int,
	subject_id: int,
	title: str,
	description: str,
	duration_minutes: int,
	learning_objectives: Optional[List[str]] = None,
	activities: Optional[List[str]] = None,
	materials_needed: Optional[List[str]] = None,
	assessment_strategy: Optional[str] = None,
	homework: Optional[str] = None,
	references: Optional[List[Dict[str, Any]]] = None,
	generated_by_ai: bool = False,
	source_filename: Optional[str] = None,
	source_mime_type: Optional[str] = None,
	source_summary: Optional[str] = None,
) -> Dict[str, Any]:
	teacher = _get_teacher_profile(db, user_id)
	_validate_lesson_scope(db, teacher, classroom_id=classroom_id, subject_id=subject_id)

	lesson = LessonPlan(
		teacher_id=teacher.id,
		classroom_id=classroom_id,
		subject_id=subject_id,
		title=title.strip(),
		description=description.strip(),
		duration_minutes=duration_minutes,
		learning_objectives=_as_json_list(_clean_string_list(learning_objectives)),
		activities=_as_json_list(_clean_string_list(activities)),
		materials_needed=_as_json_list(_clean_string_list(materials_needed)),
		assessment_strategy=assessment_strategy.strip() if assessment_strategy else None,
		homework=homework.strip() if homework else None,
		references=_as_json_list(references or []),
		generated_by_ai=generated_by_ai,
		source_filename=source_filename,
		source_mime_type=source_mime_type,
		source_summary=source_summary,
	)

	db.add(lesson)
	db.commit()
	db.refresh(lesson)

	lesson = db.query(LessonPlan).options(
		joinedload(LessonPlan.teacher).joinedload(Teacher.user),
		joinedload(LessonPlan.classroom),
		joinedload(LessonPlan.subject),
	).filter(LessonPlan.id == lesson.id).first()

	return _lesson_to_dict(lesson)


def get_lesson_plan(db: Session, user_id: int, lesson_id: int) -> Dict[str, Any]:
	teacher = _get_teacher_profile(db, user_id)
	lesson = db.query(LessonPlan).options(
		joinedload(LessonPlan.teacher).joinedload(Teacher.user),
		joinedload(LessonPlan.classroom),
		joinedload(LessonPlan.subject),
	).filter(
		LessonPlan.id == lesson_id,
		LessonPlan.teacher_id == teacher.id,
	).first()
	if not lesson:
		raise HTTPException(status_code=404, detail="Lesson plan not found")
	return _lesson_to_dict(lesson)


def list_lesson_dashboard(
	db: Session,
	user_id: int,
	*,
	classroom_id: Optional[int] = None,
	subject_id: Optional[int] = None,
	active_only: bool = True,
	limit: int = 50,
) -> Dict[str, Any]:
	teacher = _get_teacher_profile(db, user_id)

	query = db.query(LessonPlan).options(
		joinedload(LessonPlan.teacher).joinedload(Teacher.user),
		joinedload(LessonPlan.classroom),
		joinedload(LessonPlan.subject),
	).filter(LessonPlan.teacher_id == teacher.id)

	if active_only:
		query = query.filter(LessonPlan.is_active == True)
	if classroom_id:
		query = query.filter(LessonPlan.classroom_id == classroom_id)
	if subject_id:
		query = query.filter(LessonPlan.subject_id == subject_id)

	lessons = query.order_by(LessonPlan.updated_date.desc()).limit(limit).all()

	total_lessons = db.query(func.count(LessonPlan.id)).filter(LessonPlan.teacher_id == teacher.id).scalar() or 0
	ai_generated_lessons = db.query(func.count(LessonPlan.id)).filter(
		LessonPlan.teacher_id == teacher.id,
		LessonPlan.generated_by_ai == True
	).scalar() or 0
	active_lessons = db.query(func.count(LessonPlan.id)).filter(
		LessonPlan.teacher_id == teacher.id,
		LessonPlan.is_active == True
	).scalar() or 0

	return {
		"total_lessons": int(total_lessons),
		"ai_generated_lessons": int(ai_generated_lessons),
		"active_lessons": int(active_lessons),
		"lessons": [_lesson_to_dict(item) for item in lessons],
	}


def update_lesson_plan(db: Session, user_id: int, lesson_id: int, updates: Dict[str, Any]) -> Dict[str, Any]:
	teacher = _get_teacher_profile(db, user_id)

	lesson = db.query(LessonPlan).filter(
		LessonPlan.id == lesson_id,
		LessonPlan.teacher_id == teacher.id,
	).first()
	if not lesson:
		raise HTTPException(status_code=404, detail="Lesson plan not found")

	new_classroom_id = updates.get("classroom_id", lesson.classroom_id)
	new_subject_id = updates.get("subject_id", lesson.subject_id)
	_validate_lesson_scope(db, teacher, classroom_id=new_classroom_id, subject_id=new_subject_id)

	if "classroom_id" in updates:
		lesson.classroom_id = updates["classroom_id"]
	if "subject_id" in updates:
		lesson.subject_id = updates["subject_id"]
	if "title" in updates and updates["title"] is not None:
		lesson.title = updates["title"].strip()
	if "description" in updates and updates["description"] is not None:
		lesson.description = updates["description"].strip()
	if "duration_minutes" in updates and updates["duration_minutes"] is not None:
		lesson.duration_minutes = updates["duration_minutes"]
	if "learning_objectives" in updates and updates["learning_objectives"] is not None:
		lesson.learning_objectives = _as_json_list(_clean_string_list(updates["learning_objectives"]))
	if "activities" in updates and updates["activities"] is not None:
		lesson.activities = _as_json_list(_clean_string_list(updates["activities"]))
	if "materials_needed" in updates and updates["materials_needed"] is not None:
		lesson.materials_needed = _as_json_list(_clean_string_list(updates["materials_needed"]))
	if "assessment_strategy" in updates:
		value = updates.get("assessment_strategy")
		lesson.assessment_strategy = value.strip() if isinstance(value, str) else value
	if "homework" in updates:
		value = updates.get("homework")
		lesson.homework = value.strip() if isinstance(value, str) else value
	if "references" in updates and updates["references"] is not None:
		lesson.references = _as_json_list(updates["references"])
	if "is_active" in updates and updates["is_active"] is not None:
		lesson.is_active = updates["is_active"]

	db.commit()
	db.refresh(lesson)

	lesson = db.query(LessonPlan).options(
		joinedload(LessonPlan.teacher).joinedload(Teacher.user),
		joinedload(LessonPlan.classroom),
		joinedload(LessonPlan.subject),
	).filter(LessonPlan.id == lesson.id).first()
	return _lesson_to_dict(lesson)


def deactivate_lesson_plan(db: Session, user_id: int, lesson_id: int) -> Dict[str, Any]:
	teacher = _get_teacher_profile(db, user_id)
	lesson = db.query(LessonPlan).filter(
		LessonPlan.id == lesson_id,
		LessonPlan.teacher_id == teacher.id,
	).first()
	if not lesson:
		raise HTTPException(status_code=404, detail="Lesson plan not found")

	lesson.is_active = False
	db.commit()
	db.refresh(lesson)
	return {"message": "Lesson plan deactivated successfully", "lesson_id": lesson.id}


async def generate_and_create_lesson_plan(
	db: Session,
	user_id: int,
	*,
	classroom_id: int,
	subject_id: int,
	title: str,
	description: str,
	duration_minutes: int,
	learning_objectives: Optional[List[str]] = None,
	file_bytes: Optional[bytes] = None,
	file_name: Optional[str] = None,
	file_mime_type: Optional[str] = None,
) -> Dict[str, Any]:
	teacher = _get_teacher_profile(db, user_id)
	classroom, subject = _validate_lesson_scope(db, teacher, classroom_id=classroom_id, subject_id=subject_id)

	extracted_context = ""
	source_summary = None
	if file_bytes and file_name:
		extracted_context = gemma_lessonplan_service.extract_pdf_text_from_bytes(file_bytes)
		source_summary = extracted_context[:4000]

	objectives_hint = _clean_string_list(learning_objectives)
	ai_payload = await gemma_lessonplan_service.generate_lesson_plan(
		subject_name=subject.name,
		classroom_name=classroom.name,
		title=title,
		description=description,
		duration_minutes=duration_minutes,
		learning_objectives_hint=objectives_hint,
		source_context=extracted_context,
	)

	generated_title = str(ai_payload.get("title") or title).strip()[:200]
	generated_description = str(ai_payload.get("description") or description).strip()
	generated_duration = int(ai_payload.get("duration_minutes") or duration_minutes)
	generated_objectives = _clean_string_list(ai_payload.get("learning_objectives") or objectives_hint)
	generated_activities = _clean_string_list(ai_payload.get("activities") or [])
	generated_materials = _clean_string_list(ai_payload.get("materials_needed") or [])
	generated_assessment = str(ai_payload.get("assessment_strategy") or "").strip() or None
	generated_homework = str(ai_payload.get("homework") or "").strip() or None
	references: List[Dict[str, Any]] = []

	return create_lesson_plan(
		db,
		user_id,
		classroom_id=classroom_id,
		subject_id=subject_id,
		title=generated_title,
		description=generated_description,
		duration_minutes=max(10, min(240, generated_duration)),
		learning_objectives=generated_objectives,
		activities=generated_activities,
		materials_needed=generated_materials,
		assessment_strategy=generated_assessment,
		homework=generated_homework,
		references=references,
		generated_by_ai=True,
		source_filename=file_name,
		source_mime_type=file_mime_type,
		source_summary=source_summary,
	)
