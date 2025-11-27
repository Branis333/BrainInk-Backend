import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path

from db.connection import db_dependency
from Endpoints.auth import get_current_user
from models.afterschool_models import CourseAssignment, StudentAssignment, CourseBlock, StudentNote
from schemas.afterschool_schema import PracticeQuizOut
from services.quiz_services import quiz_service


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/after-school/quiz", tags=["Practice Quizzes (Ephemeral)"])

# Dependency for current user
user_dependency = Depends(get_current_user)


@router.post("/practice/assignment/{assignment_id}", response_model=PracticeQuizOut)
async def generate_practice_quiz_from_assignment(
	assignment_id: int = Path(..., description="Assignment ID to generate practice quiz from"),
	db: db_dependency = None,
	current_user: dict = user_dependency,
):
	"""
	Generate an ephemeral 5-question practice quiz grounded in the assignment details
	and the student's feedback (if any). Does not create or modify any records.
	"""
	user_id = current_user["user_id"]

	assignment = db.query(CourseAssignment).filter(CourseAssignment.id == assignment_id).first()
	if not assignment:
		raise HTTPException(status_code=404, detail="Assignment not found")

	# Student's own assignment (to extract personalized feedback/gaps)
	student_assignment: Optional[StudentAssignment] = (
		db.query(StudentAssignment)
		.filter(
			StudentAssignment.assignment_id == assignment_id,
			StudentAssignment.user_id == user_id,
		)
		.first()
	)

	feedback = student_assignment.feedback if student_assignment else None

	quiz = await quiz_service.generate_from_assignment(
		assignment_title=assignment.title,
		assignment_description=assignment.description,
		assignment_instructions=assignment.instructions,
		learning_outcomes=assignment.learning_outcomes,
		feedback=feedback,
		subject=None,
	)
	return quiz


@router.post("/practice/block/{block_id}", response_model=PracticeQuizOut)
async def generate_practice_quiz_from_block(
	block_id: int = Path(..., description="Course block ID to generate practice quiz from"),
	db: db_dependency = None,
	current_user: dict = user_dependency,
):
	"""
	Generate an ephemeral 5-question practice quiz based on a course block's
	content and learning objectives. Not stored and does not affect grades.
	"""
	block = db.query(CourseBlock).filter(CourseBlock.id == block_id).first()
	if not block:
		raise HTTPException(status_code=404, detail="Block not found")

	quiz = await quiz_service.generate_from_block(
		block_title=block.title,
		block_description=block.description,
		block_content=block.content,
		learning_objectives=block.learning_objectives,
		subject=None,
	)
	return quiz


@router.post("/practice/note/{note_id}", response_model=PracticeQuizOut)
async def generate_practice_quiz_from_note(
	note_id: int = Path(..., description="Student note ID to generate practice quiz from"),
	db: db_dependency = None,
	current_user: dict = user_dependency,
):
	"""
	Generate an ephemeral 5-question practice quiz from a student's analyzed notes
	(summary, key points, topics). Only the owner of the note can use this endpoint.
	"""
	user_id = current_user["user_id"]
	note = db.query(StudentNote).filter(StudentNote.id == note_id).first()
	if not note:
		raise HTTPException(status_code=404, detail="Note not found")
	if note.user_id != user_id:
		raise HTTPException(status_code=403, detail="Not authorized for this note")

	quiz = await quiz_service.generate_from_notes(
		note_title=note.title,
		summary=note.summary,
		key_points=note.key_points,
		main_topics=note.main_topics,
		learning_concepts=note.learning_concepts,
		subject=note.subject,
	)
	return quiz

