from datetime import datetime
from pydantic import BaseModel, Field
from typing import List, Optional


class LessonReference(BaseModel):
	title: str = Field(..., min_length=1, max_length=300)
	url: str = Field(..., min_length=3, max_length=1000)
	source_type: str = Field(..., description="youtube, article, website, textbook")
	note: Optional[str] = Field(None, max_length=500)


class LessonPlanBase(BaseModel):
	title: str = Field(..., min_length=3, max_length=200)
	description: str = Field(..., min_length=10, max_length=4000)
	duration_minutes: int = Field(..., ge=10, le=240)
	learning_objectives: List[str] = Field(default_factory=list)
	activities: List[str] = Field(default_factory=list)
	materials_needed: List[str] = Field(default_factory=list)
	assessment_strategy: Optional[str] = Field(None, max_length=2000)
	homework: Optional[str] = Field(None, max_length=2000)
	references: List[LessonReference] = Field(default_factory=list)


class LessonPlanCreate(LessonPlanBase):
	classroom_id: int
	subject_id: int


class LessonPlanUpdate(BaseModel):
	title: Optional[str] = Field(None, min_length=3, max_length=200)
	description: Optional[str] = Field(None, min_length=10, max_length=4000)
	duration_minutes: Optional[int] = Field(None, ge=10, le=240)
	learning_objectives: Optional[List[str]] = None
	activities: Optional[List[str]] = None
	materials_needed: Optional[List[str]] = None
	assessment_strategy: Optional[str] = Field(None, max_length=2000)
	homework: Optional[str] = Field(None, max_length=2000)
	references: Optional[List[LessonReference]] = None
	is_active: Optional[bool] = None


class LessonPlanResponse(LessonPlanBase):
	id: int
	teacher_id: int
	classroom_id: int
	subject_id: int
	classroom_name: Optional[str] = None
	subject_name: Optional[str] = None
	teacher_name: Optional[str] = None
	source_filename: Optional[str] = None
	generated_by_ai: bool = False
	created_date: datetime
	updated_date: datetime
	is_active: bool

	class Config:
		from_attributes = True


class LessonPlanGenerateRequest(BaseModel):
	classroom_id: int
	subject_id: int
	title: str = Field(..., min_length=3, max_length=200)
	description: str = Field(..., min_length=10, max_length=4000)
	duration_minutes: int = Field(..., ge=10, le=240)
	learning_objectives: List[str] = Field(default_factory=list)


class LessonPlanDashboardResponse(BaseModel):
	total_lessons: int = 0
	ai_generated_lessons: int = 0
	active_lessons: int = 0
	lessons: List[LessonPlanResponse] = Field(default_factory=list)
