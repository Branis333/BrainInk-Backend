import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from models.afterschool_models import (
	CourseAssignment,
	StudentAssignment,
	ProgressDigest,
)
from services.gemini_service import gemini_service


logger = logging.getLogger(__name__)


class ProgressService:
	"""
	Builds and persists AI-digested progress summaries from assignment feedback.

	Scopes:
	- weekly: last 7 days across all courses for the student
	- course: entire course for the student
	"""

	def __init__(self):
		self.gemini = gemini_service

	# -----------------------------
	# Public API
	# -----------------------------
	async def generate_weekly_digest(self, db: Session, *, user_id: int, now: Optional[datetime] = None) -> ProgressDigest:
		now = now or datetime.utcnow()
		period_start = self._start_of_week_window(now)
		period_end = now

		records, stats = self._gather_feedback_for_window(db, user_id=user_id, start=period_start, end=period_end)
		summary_text = await self._summarize_feedback(
			scope_title="Weekly Progress (last 7 days)",
			user_id=user_id,
			records=records,
			stats=stats,
			window=(period_start, period_end),
		)

		digest = self._upsert_digest(
			db,
			user_id=user_id,
			scope="weekly",
			period_start=period_start,
			period_end=period_end,
			course_id=None,
			summary=summary_text,
			assignments_count=stats["count"],
			avg_grade=stats.get("avg_grade"),
		)
		return digest

	def get_weekly_digest(self, db: Session, *, user_id: int, reference_date: Optional[datetime] = None) -> Optional[ProgressDigest]:
		"""
		Retrieve the digest for the 7-day window containing reference_date (defaults to now).
		"""
		ref = reference_date or datetime.utcnow()
		period_start = self._start_of_week_window(ref)
		q = (
			db.query(ProgressDigest)
			.filter(
				and_(
					ProgressDigest.user_id == user_id,
					ProgressDigest.scope == "weekly",
					ProgressDigest.period_start == period_start,
				)
			)
			.order_by(ProgressDigest.created_at.desc())
		)
		return q.first()

	async def generate_course_digest(self, db: Session, *, user_id: int, course_id: int) -> ProgressDigest:
		records, stats, (period_start, period_end) = self._gather_feedback_for_course(db, user_id=user_id, course_id=course_id)

		summary_text = await self._summarize_feedback(
			scope_title=f"Course Progress (Course ID {course_id})",
			user_id=user_id,
			records=records,
			stats=stats,
			window=(period_start, period_end),
		)

		digest = self._upsert_digest(
			db,
			user_id=user_id,
			scope="course",
			period_start=period_start,
			period_end=period_end,
			course_id=course_id,
			summary=summary_text,
			assignments_count=stats["count"],
			avg_grade=stats.get("avg_grade"),
		)
		return digest

	def get_course_digest(self, db: Session, *, user_id: int, course_id: int) -> Optional[ProgressDigest]:
		q = (
			db.query(ProgressDigest)
			.filter(
				and_(
					ProgressDigest.user_id == user_id,
					ProgressDigest.scope == "course",
					ProgressDigest.course_id == course_id,
				)
			)
			.order_by(ProgressDigest.updated_at.desc())
		)
		return q.first()

	# -----------------------------
	# Internals
	# -----------------------------
	def _start_of_week_window(self, now: datetime) -> datetime:
		# Past 7 days window start; normalize to midnight UTC 7 days ago
		start = now - timedelta(days=7)
		return start.replace(hour=0, minute=0, second=0, microsecond=0)

	def _gather_feedback_for_window(
		self, db: Session, *, user_id: int, start: datetime, end: datetime
	) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
		"""
		Collect StudentAssignment feedback for the user between start and end (inclusive of end).
		Uses submitted_at if present, else updated_at/assigned_at to approximate recent activity.
		"""
		# Join with CourseAssignment for titles and course linkage
		q = (
			db.query(StudentAssignment, CourseAssignment)
			.join(CourseAssignment, CourseAssignment.id == StudentAssignment.assignment_id)
			.filter(
				and_(
					StudentAssignment.user_id == user_id,
					# feedback-driven filter: either submitted recently or updated recently
					(
						(StudentAssignment.submitted_at != None) & (StudentAssignment.submitted_at >= start) & (StudentAssignment.submitted_at <= end)
					)
					| (
						(StudentAssignment.updated_at != None) & (StudentAssignment.updated_at >= start) & (StudentAssignment.updated_at <= end)
					)
				)
			)
		)

		records: List[Dict[str, Any]] = []
		grades: List[float] = []
		for sa, ca in q.all():
			rec = self._to_feedback_record(sa, ca)
			if rec.get("grade") is not None:
				grades.append(rec["grade"])
			records.append(rec)

		stats = {
			"count": len(records),
			"avg_grade": (sum(grades) / len(grades)) if grades else None,
		}
		return records, stats

	def _gather_feedback_for_course(
		self, db: Session, *, user_id: int, course_id: int
	) -> Tuple[List[Dict[str, Any]], Dict[str, Any], Tuple[datetime, datetime]]:
		q = (
			db.query(StudentAssignment, CourseAssignment)
			.join(CourseAssignment, CourseAssignment.id == StudentAssignment.assignment_id)
			.filter(
				and_(
					StudentAssignment.user_id == user_id,
					StudentAssignment.course_id == course_id,
				)
			)
		)

		records: List[Dict[str, Any]] = []
		grades: List[float] = []
		earliest: Optional[datetime] = None
		latest: Optional[datetime] = None

		for sa, ca in q.all():
			rec = self._to_feedback_record(sa, ca)
			ts = rec.get("timestamp") or sa.updated_at or sa.assigned_at
			if ts:
				if earliest is None or ts < earliest:
					earliest = ts
				if latest is None or ts > latest:
					latest = ts
			if rec.get("grade") is not None:
				grades.append(rec["grade"])
			records.append(rec)

		now = datetime.utcnow()
		period_start = earliest or now
		period_end = latest or now

		stats = {
			"count": len(records),
			"avg_grade": (sum(grades) / len(grades)) if grades else None,
		}
		return records, stats, (period_start, period_end)

	def _to_feedback_record(self, sa: StudentAssignment, ca: CourseAssignment) -> Dict[str, Any]:
		grade = sa.manual_grade if sa.manual_grade is not None else sa.ai_grade if sa.ai_grade is not None else sa.grade
		timestamp = sa.submitted_at or sa.updated_at or sa.assigned_at
		return {
			"assignment_id": sa.assignment_id,
			"assignment_title": ca.title,
			"course_id": sa.course_id,
			"status": sa.status,
			"grade": float(grade) if grade is not None else None,
			"feedback": sa.feedback or "",
			"submitted_at": sa.submitted_at,
			"due_date": sa.due_date,
			"timestamp": timestamp,
		}

	async def _summarize_feedback(
		self,
		*,
		scope_title: str,
		user_id: int,
		records: List[Dict[str, Any]],
		stats: Dict[str, Any],
		window: Tuple[datetime, datetime],
	) -> str:
		if not records:
			# Friendly default if no feedback; keep two short paragraphs
			return (
				f"{scope_title}: No assignment feedback was recorded in this period. "
				"Keep engaging with your assignments and you'll see a personalized weekly progress summary here.\n\n"
				"Tip: Submit assignments and review teacher or AI feedback to get targeted guidance for the next week."
			)

		# Build compact context for the model
		start, end = window
		lines: List[str] = [
			f"TIME WINDOW: {start.isoformat()} to {end.isoformat()}",
			f"USER: {user_id}",
			f"ASSIGNMENTS COUNT: {stats.get('count', 0)}",
		]
		if stats.get("avg_grade") is not None:
			lines.append(f"AVERAGE GRADE: {stats['avg_grade']:.1f}")
		lines.append("")
		lines.append("FEEDBACK ITEMS:")
		for idx, r in enumerate(records[:30], start=1):  # cap context to 30 items for token safety
			# Trim feedback to avoid overly long prompts
			feedback = (r.get("feedback") or "").strip()
			if len(feedback) > 800:
				feedback = feedback[:800] + "..."
			title = (r.get("assignment_title") or "Assignment").strip()
			status = r.get("status") or ""
			grade = r.get("grade")
			grade_s = f"{grade:.1f}" if grade is not None else "N/A"
			lines.append(f"- [{idx}] {title} | status={status} | grade={grade_s} | feedback: {feedback}")

		prompt = (
			"You are a helpful teacher. Create a concise, encouraging weekly progress digest based strictly on the FEEDBACK ITEMS.\n"
			"Write EXACTLY two short paragraphs (no lists, no headings).\n"
			"Paragraph 1: Summarize strengths and wins this period in plain language.\n"
			"Paragraph 2: Actionable advice: what to practice next week and how. Keep it supportive and age-appropriate.\n"
			"Return STRICT JSON (no markdown), with this shape: {\n"
			"  \"summary\": \"para1\n\npara2\"\n"
			"}\n\n"
			+ "\n".join(lines)
		)

		try:
			result = await self.gemini._generate_json_response(
				prompt=prompt, attachments=None, temperature=0.2, max_output_tokens=1024
			)
			summary = str(result.get("summary") or "").strip()
			if not summary:
				# Fallback minimal join of model text if parsing failed
				summary = "\n\n".join([
					"Here's a brief weekly digest based on your recent feedback.",
					"Keep up the effort next week: focus on the areas highlighted in your feedback.",
				])
			# Normalize to two paragraphs
			parts = [p.strip() for p in summary.split("\n\n") if p.strip()]
			if len(parts) > 2:
				summary = "\n\n".join(parts[:2])
			elif len(parts) == 1:
				summary = parts[0] + "\n\n" + "Keep practicing; focus on the highlighted areas next week."
			return summary
		except Exception:
			logger.exception("Failed to generate progress summary; returning fallback text")
			return (
				"Progress summary unavailable due to an AI error. "
				"Please try again later or continue engaging with assignments."
			)

	def _upsert_digest(
		self,
		db: Session,
		*,
		user_id: int,
		scope: str,
		period_start: datetime,
		period_end: datetime,
		course_id: Optional[int],
		summary: str,
		assignments_count: int,
		avg_grade: Optional[float],
	) -> ProgressDigest:
		if scope == "weekly":
			existing = (
				db.query(ProgressDigest)
				.filter(
					and_(
						ProgressDigest.user_id == user_id,
						ProgressDigest.scope == scope,
						ProgressDigest.period_start == period_start,
					)
				)
				.first()
			)
		else:  # course
			existing = (
				db.query(ProgressDigest)
				.filter(
					and_(
						ProgressDigest.user_id == user_id,
						ProgressDigest.scope == scope,
						ProgressDigest.course_id == course_id,
					)
				)
				.first()
			)

		if existing:
			existing.period_end = period_end
			existing.summary = summary
			existing.assignments_count = assignments_count
			existing.avg_grade = avg_grade
			existing.updated_at = datetime.utcnow()
			db.add(existing)
			db.commit()
			db.refresh(existing)
			return existing

		digest = ProgressDigest(
			user_id=user_id,
			scope=scope,
			period_start=period_start,
			period_end=period_end,
			course_id=course_id,
			summary=summary,
			assignments_count=assignments_count,
			avg_grade=avg_grade,
		)
		db.add(digest)
		db.commit()
		db.refresh(digest)
		return digest


# Singleton
progress_service = ProgressService()

