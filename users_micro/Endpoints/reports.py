from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, func, text
from typing import List, Optional, Dict, Any, Annotated
from datetime import datetime, timedelta
import json
import uuid
import os
from pathlib import Path
import re
import requests

# Local imports
from db.connection import get_db, db_dependency
from models.study_area_models import (
    Report, ReportTemplate, ReportShare, ReportSchedule,
    Student, Teacher, Subject, Assignment, Grade, Classroom, School,
    ReportType, ReportStatus, ReportFormat
)
from schemas.reports_schemas import (
    ReportTemplateCreate, ReportTemplateUpdate, ReportTemplateResponse,
    ReportCreate, ReportUpdate, ReportResponse, ReportGenerationRequest,
    ReportShareCreate, ReportShareUpdate, ReportShareResponse,
    ReportScheduleCreate, ReportScheduleUpdate, ReportScheduleResponse,
    ReportAnalytics, StudentProgressData, ClassPerformanceData, SubjectAnalyticsData,
    QuickReportRequest, ReportPreview, BulkReportRequest, BulkReportResponse,
    ExportRequest, ExportResponse
)
from Endpoints.auth import get_current_user
from models.users_models import User

router = APIRouter(tags=["Reports"])

# Use the same pattern as other working files
user_dependency = Annotated[dict, Depends(get_current_user)]

# Test endpoint to verify authentication
@router.get("/auth-test")
def test_auth(
    current_user: user_dependency,
    db: db_dependency
):

    """Test endpoint to verify authentication"""
    try:
        user_id = current_user["user_id"]
        user = db.query(User).filter(User.id == user_id).first()
        
        # Get user's school information
        teacher = db.query(Teacher).filter(Teacher.user_id == user_id).first()
        school = db.query(School).filter(School.principal_id == user_id).first()
        
        return {
            "success": True,
            "message": "Authentication working!",
            "user_info": current_user,
            "user_roles": [role.name.value for role in user.roles] if user and user.roles else [],
            "teacher_school_id": teacher.school_id if teacher else None,
            "principal_school_id": school.id if school else None,
            "recommended_school_id": _get_user_school_id(user_id, db)
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "user_data": current_user if 'current_user' in locals() else "No user data"
        }

# --- Report Templates Endpoints ---

@router.post("/templates/", response_model=ReportTemplateResponse)
def create_report_template(
    template: ReportTemplateCreate,
    db: db_dependency,
    current_user: user_dependency
):
    """Create a new report template"""
    # Validate JSON template_config
    try:
        json.loads(template.template_config)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON in template_config")

    # Resolve effective school_id: allow client to send 0 and derive from user
    effective_school_id = template.school_id
    if not effective_school_id or effective_school_id == 0:
        effective_school_id = _get_user_school_id(current_user["user_id"], db)
        if not effective_school_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No school associated with this user. Please contact an administrator."
            )

    # Verify user has access to the school
    if not _user_has_school_access(current_user["user_id"], effective_school_id, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this school")

    # Convert Pydantic Enum to SQLAlchemy Enum for report_type
    try:
        # template.report_type may be a pydantic enum (value is str)
        report_type_value = getattr(template.report_type, "value", template.report_type)
        model_report_type = ReportType(report_type_value)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid report_type")

    db_template = ReportTemplate(
        name=template.name,
        description=template.description,
        report_type=model_report_type,
        template_config=template.template_config,
    school_id=effective_school_id,
        is_active=template.is_active,
        is_default=template.is_default,
        created_by=current_user["user_id"],
    )

    try:
        db.add(db_template)
        db.commit()
        db.refresh(db_template)
        return db_template
    except Exception as e:
        db.rollback()
        # Surface the error so the client sees why it failed
        raise HTTPException(status_code=500, detail=f"Failed to create report template: {str(e)}")

@router.get("/templates/", response_model=List[ReportTemplateResponse])
def get_report_templates(
    school_id: int,
    db: db_dependency,
    current_user: user_dependency,
    report_type: Optional[str] = None,
    is_active: Optional[bool] = None,
    skip: int = 0,
    limit: int = 100
):
    """Get report templates for a school"""
    # If school_id is 0, try to get user's school
    if school_id == 0:
        school_id = _get_user_school_id(current_user["user_id"], db)
        if school_id == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No school associated with this user. Please contact an administrator."
            )
    
    if not _user_has_school_access(current_user["user_id"], school_id, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this school"
        )
    
    query = db.query(ReportTemplate).filter(ReportTemplate.school_id == school_id)

    # Normalize report_type filter to ORM enum if provided
    if report_type:
        try:
            rt = ReportType(report_type) if isinstance(report_type, str) else report_type
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid report_type filter"
            )
        query = query.filter(ReportTemplate.report_type == rt)
    if is_active is not None:
        query = query.filter(ReportTemplate.is_active == is_active)
    
    templates = query.offset(skip).limit(limit).all()
    return templates

@router.get("/templates/{template_id}", response_model=ReportTemplateResponse)
def get_report_template(
    template_id: int,
    db: db_dependency,
    current_user: user_dependency
):
    """Get a specific report template"""
    template = db.query(ReportTemplate).filter(ReportTemplate.id == template_id).first()
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report template not found"
        )
    
    if not _user_has_school_access(current_user["user_id"], template.school_id, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this template"
        )
    
    return template

@router.put("/templates/{template_id}", response_model=ReportTemplateResponse)
def update_report_template(
    template_id: int,
    template_update: ReportTemplateUpdate,
    db: db_dependency,
    current_user: user_dependency
):
    """Update a report template"""
    template = db.query(ReportTemplate).filter(ReportTemplate.id == template_id).first()
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report template not found"
        )
    
    if not _user_has_school_access(current_user["user_id"], template.school_id, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this template"
        )
    
    # Validate JSON template_config if provided
    if template_update.template_config:
        try:
            json.loads(template_update.template_config)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid JSON in template_config"
            )
    
    for field, value in template_update.dict(exclude_unset=True).items():
        setattr(template, field, value)
    
    template.updated_date = datetime.utcnow()
    db.commit()
    db.refresh(template)
    
    return template

@router.delete("/templates/{template_id}")
def delete_report_template(
    template_id: int,
    db: db_dependency,
    current_user: user_dependency
):
    """Delete a report template"""
    template = db.query(ReportTemplate).filter(ReportTemplate.id == template_id).first()
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report template not found"
        )
    
    if not _user_has_school_access(current_user["user_id"], template.school_id, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this template"
        )
    
    db.delete(template)
    db.commit()
    
    return {"message": "Report template deleted successfully"}

# --- Reports Endpoints ---

@router.post("/generate", response_model=ReportResponse)
def generate_report(
    request: ReportGenerationRequest,
    background_tasks: BackgroundTasks,
    db: db_dependency,
    current_user: user_dependency
):
    """Generate a new report"""
    # Determine school_id from the request scope; if not derivable, fall back to user's school
    try:
        school_id = _get_school_id_from_scope(request, db)
    except HTTPException:
        school_id = _get_user_school_id(current_user["user_id"], db)
        if not school_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot determine school from request scope or user profile"
            )
    
    if not _user_has_school_access(current_user["user_id"], school_id, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this school"
        )
    
    # Convert enums from request (Pydantic enums or strings) to ORM enums
    try:
        report_type_value = getattr(request.report_type, "value", request.report_type)
        model_report_type = ReportType(report_type_value)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid report_type")

    try:
        format_value = getattr(request.format, "value", request.format)
        model_format = ReportFormat(format_value)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid format")

    # Create report record
    db_report = Report(
        title=request.title,
        report_type=model_report_type,
        template_id=request.template_id,
        school_id=school_id,
        subject_id=request.subject_id,
        classroom_id=request.classroom_id,
        student_id=request.student_id,
        teacher_id=request.teacher_id,
        assignment_id=request.assignment_id,
        date_from=request.date_from,
        date_to=request.date_to,
        parameters=json.dumps(request.custom_parameters) if request.custom_parameters else None,
        format=model_format,
        requested_by=current_user["user_id"],
        status=ReportStatus.pending
    )
    
    db.add(db_report)
    db.commit()
    db.refresh(db_report)
    
    # Start background report generation
    background_tasks.add_task(_generate_report_background, db_report.id, request)
    
    return db_report

@router.get("/", response_model=List[ReportResponse])
def get_reports(
    school_id: int,
    db: db_dependency,
    current_user: user_dependency,
    report_type: Optional[str] = None,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 100
):
    """Get reports for a school"""
    # If school_id is 0, try to get user's school
    if school_id == 0:
        school_id = _get_user_school_id(current_user["user_id"], db)
        if school_id == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No school associated with this user. Please contact an administrator."
            )
    
    if not _user_has_school_access(current_user["user_id"], school_id, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this school"
        )
    
    query = db.query(Report).filter(Report.school_id == school_id)

    # Normalize filters to ORM enums if provided
    if report_type:
        try:
            rt = ReportType(report_type) if isinstance(report_type, str) else report_type
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid report_type filter"
            )
        query = query.filter(Report.report_type == rt)
    if status:
        try:
            st = ReportStatus(status) if isinstance(status, str) else status
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid status filter"
            )
        query = query.filter(Report.status == st)
    
    reports = query.order_by(desc(Report.requested_date)).offset(skip).limit(limit).all()
    return reports

@router.get("/{report_id}", response_model=ReportResponse)
def get_report(
    report_id: int,
    db: db_dependency,
    current_user: user_dependency
):
    """Get a specific report"""
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found"
        )
    
    if not _user_has_report_access(current_user["user_id"], report, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this report"
        )
    
    # Update access tracking
    report.access_count += 1
    report.last_accessed = datetime.utcnow()
    db.commit()
    
    return report

@router.get("/{report_id}/download")
def download_report(
    report_id: int,
    db: db_dependency,
    current_user: user_dependency
):
    """Download a generated report file"""
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found"
        )
    
    if not _user_has_report_access(current_user["user_id"], report, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this report"
        )
    
    if report.status != ReportStatus.completed or not report.file_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Report is not ready for download"
        )
    
    if not os.path.exists(report.file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report file not found"
        )
    
    # Update access tracking
    report.access_count += 1
    report.last_accessed = datetime.utcnow()
    db.commit()
    
    return FileResponse(
        path=report.file_path,
        filename=report.file_name,
        media_type='application/octet-stream'
    )

@router.delete("/{report_id}")
def delete_report(
    report_id: int,
    db: db_dependency,
    current_user: user_dependency
):
    """Delete a report"""
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found"
        )
    
    if not _user_has_school_access(current_user["user_id"], report.school_id, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this report"
        )
    
    # Delete file if exists
    if report.file_path and os.path.exists(report.file_path):
        os.remove(report.file_path)
    
    db.delete(report)
    db.commit()
    
    return {"message": "Report deleted successfully"}

# --- Quick Reports ---

@router.post("/quick", response_model=ReportResponse)
def generate_quick_report(
    request: QuickReportRequest,
    background_tasks: BackgroundTasks,
    db: db_dependency,
    current_user: user_dependency
):
    """Generate a quick report with predefined parameters"""
    # Convert quick request to full generation request
    school_id = _get_school_id_from_quick_scope(request.report_type, request.scope_id, db)
    
    if not _user_has_school_access(current_user["user_id"], school_id, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this school"
        )
    
    # Create quick report
    title = f"Quick {request.report_type.replace('_', ' ').title()} Report"
    date_from = datetime.utcnow() - timedelta(days=request.date_range_days)
    
    db_report = Report(
        title=title,
        report_type=request.report_type,
        school_id=school_id,
        date_from=date_from,
        date_to=datetime.utcnow(),
        format=request.format,
        requested_by=current_user["user_id"],
        status=ReportStatus.pending
    )
    
    # Set scope based on report type
    if request.report_type == "student_progress":
        db_report.student_id = request.scope_id
    elif request.report_type == "class_performance":
        db_report.classroom_id = request.scope_id
    elif request.report_type == "subject_analytics":
        db_report.subject_id = request.scope_id
    
    db.add(db_report)
    db.commit()
    db.refresh(db_report)
    
    # Generate in background
    background_tasks.add_task(_generate_quick_report_background, db_report.id, request)
    
    return db_report

@router.get("/preview/{report_type}/{scope_id}", response_model=ReportPreview)
def get_report_preview(
    report_type: str,
    scope_id: int,
    db: db_dependency,
    current_user: user_dependency,
    date_range_days: int = 30
):
    """Get a preview of report data without generating the full report"""
    school_id = _get_school_id_from_quick_scope(report_type, scope_id, db)
    
    if not _user_has_school_access(current_user["user_id"], school_id, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this school"
        )
    
    date_from = datetime.utcnow() - timedelta(days=date_range_days)
    
    if report_type == "student_progress":
        return _generate_student_progress_preview(scope_id, date_from, db)
    elif report_type == "class_performance":
        return _generate_class_performance_preview(scope_id, date_from, db)
    elif report_type == "subject_analytics":
        return _generate_subject_analytics_preview(scope_id, date_from, db)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported report type for preview"
        )

# --- Report Analytics ---

@router.get("/analytics/overview", response_model=ReportAnalytics)
def get_report_analytics(
    school_id: int,
    db: db_dependency,
    current_user: user_dependency,
    days: int = 30
):
    """Get analytics about report usage"""
    # If school_id is 0, try to get user's school
    if school_id == 0:
        school_id = _get_user_school_id(current_user["user_id"], db)
        if school_id == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No school associated with this user. Please contact an administrator."
            )
    
    if not _user_has_school_access(current_user["user_id"], school_id, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this school"
        )
    
    date_from = datetime.utcnow() - timedelta(days=days)
    total_reports = db.query(Report).filter(
        Report.school_id == school_id,
        Report.requested_date >= date_from
    ).count()
    
    type_counts = db.query(Report.report_type, func.count(Report.id)).filter(
        Report.school_id == school_id,
        Report.requested_date >= date_from
    ).group_by(Report.report_type).all()
    reports_by_type = {str(t[0]): t[1] for t in type_counts}
    
    status_counts = db.query(Report.status, func.count(Report.id)).filter(
        Report.school_id == school_id,
        Report.requested_date >= date_from
    ).group_by(Report.status).all()
    reports_by_status = {str(s[0]): s[1] for s in status_counts}
    
    format_counts = db.query(Report.format, func.count(Report.id)).filter(
        Report.school_id == school_id,
        Report.requested_date >= date_from
    ).group_by(Report.format).all()
    reports_by_format = {str(f[0]): f[1] for f in format_counts}
    
    completed_reports = db.query(Report).filter(
        Report.school_id == school_id,
        Report.requested_date >= date_from,
        Report.status == ReportStatus.completed
    ).count()
    success_rate = (completed_reports / total_reports * 100) if total_reports > 0 else 0
    
    total_size = db.query(func.sum(Report.file_size)).filter(
        Report.school_id == school_id,
        Report.file_size.isnot(None)
    ).scalar() or 0
    
    return ReportAnalytics(
        total_reports=total_reports,
        reports_by_type=reports_by_type,
        reports_by_status=reports_by_status,
        reports_by_format=reports_by_format,
        most_requested_types=[
            {"type": k, "count": v} for k, v in 
            sorted(reports_by_type.items(), key=lambda x: x[1], reverse=True)[:5]
        ],
        success_rate=success_rate,
        storage_used=total_size
    )
    # If school_id is 0, try to get user's school
    if school_id == 0:
        school_id = _get_user_school_id(current_user["user_id"], db)
        if school_id == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No school associated with this user. Please contact an administrator."
            )
    
    if not _user_has_school_access(current_user["user_id"], school_id, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this school"
        )
    
    date_from = datetime.utcnow() - timedelta(days=days)
    
    # Basic counts
    total_reports = db.query(Report).filter(
        Report.school_id == school_id,
        Report.requested_date >= date_from
    ).count()
    
    # Reports by type
    type_counts = db.query(
        Report.report_type,
        func.count(Report.id)
    ).filter(
        Report.school_id == school_id,
        Report.requested_date >= date_from
    ).group_by(Report.report_type).all()
    
    reports_by_type = {str(t[0]): t[1] for t in type_counts}
    
    # Reports by status
    status_counts = db.query(
        Report.status,
        func.count(Report.id)
    ).filter(
        Report.school_id == school_id,
        Report.requested_date >= date_from
    ).group_by(Report.status).all()
    
    reports_by_status = {str(s[0]): s[1] for s in status_counts}
    
    # Format distribution
    format_counts = db.query(
        Report.format,
        func.count(Report.id)
    ).filter(
        Report.school_id == school_id,
        Report.requested_date >= date_from
    ).group_by(Report.format).all()
    
    reports_by_format = {str(f[0]): f[1] for f in format_counts}
    
    # Success rate
    completed_reports = db.query(Report).filter(
        Report.school_id == school_id,
        Report.requested_date >= date_from,
        Report.status == ReportStatus.completed
    ).count()
    
    success_rate = (completed_reports / total_reports * 100) if total_reports > 0 else 0
    
    # Storage calculation (simplified)
    total_size = db.query(func.sum(Report.file_size)).filter(
        Report.school_id == school_id,
        Report.file_size.isnot(None)
    ).scalar() or 0
    
    return ReportAnalytics(
        total_reports=total_reports,
        reports_by_type=reports_by_type,
        reports_by_status=reports_by_status,
        reports_by_format=reports_by_format,
        most_requested_types=[
            {"type": k, "count": v} for k, v in 
            sorted(reports_by_type.items(), key=lambda x: x[1], reverse=True)[:5]
        ],
        success_rate=success_rate,
        storage_used=total_size
    )

# --- Teacher-authorized Student Grades (Reports Scope) ---

def _letter_grade_from_pct(pct: float) -> str:
    try:
        p = float(pct)
    except Exception:
        p = 0.0
    if p >= 90:
        return "A"
    if p >= 80:
        return "B"
    if p >= 70:
        return "C"
    if p >= 60:
        return "D"
    return "F"

@router.get("/grades/student/{student_id}")
def get_student_grades_overview(
    student_id: int,
    db: db_dependency,
    current_user: user_dependency
):
    """Return all graded assignments for a student across subjects for teachers/principals/admins in the same school.

    Response contains an aggregated list of grades with assignment/subject metadata
    and per-subject summaries with averages.
    """
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    # Authorize based on school membership (teacher/principal/admin)
    if not _user_has_school_access(current_user["user_id"], student.school_id, db):
        raise HTTPException(status_code=403, detail="Access denied to this student's school")

    # Fetch all graded items for this student (join assignment + subject)
    graded = db.query(Grade, Assignment, Subject, Teacher).\
        join(Assignment, Grade.assignment_id == Assignment.id).\
        join(Subject, Assignment.subject_id == Subject.id).\
        join(Teacher, Grade.teacher_id == Teacher.id).\
        filter(Grade.student_id == student_id).all()

    grades_payload = []
    # Aggregate per subject
    subj_stats: Dict[int, Dict[str, Any]] = {}

    for g, a, s, t in graded:
        pct = round((g.points_earned / a.max_points) * 100, 2) if a.max_points and a.max_points > 0 else 0
        grades_payload.append({
            "id": g.id,
            "assignment_id": a.id,
            "student_id": student_id,
            "teacher_id": t.id,
            "points_earned": g.points_earned,
            "feedback": g.feedback or "",
            "graded_date": g.graded_date.isoformat() if g.graded_date else None,
            "is_active": g.is_active,
            "assignment_title": a.title,
            "assignment_max_points": a.max_points,
            "student_name": f"{student.user.fname} {student.user.lname}" if student and student.user else "",
            "teacher_name": f"{t.user.fname} {t.user.lname}" if t and t.user else "",
            "subject_id": s.id,
            "subject_name": s.name,
            "percentage": pct,
        })

        if s.id not in subj_stats:
            subj_stats[s.id] = {
                "subject_id": s.id,
                "subject_name": s.name,
                "total_assignments": 0,  # unknown here; counting graded only
                "graded_assignments": 0,
                "total_points_possible": 0,
                "total_points_earned": 0,
            }
        subj_stats[s.id]["graded_assignments"] += 1
        subj_stats[s.id]["total_points_possible"] += (a.max_points or 0)
        subj_stats[s.id]["total_points_earned"] += (g.points_earned or 0)

    subjects_summary = []
    overall_possible = 0
    overall_earned = 0
    for sid, st in subj_stats.items():
        avg_pct = (st["total_points_earned"] / st["total_points_possible"] * 100) if st["total_points_possible"] > 0 else 0
        subjects_summary.append({
            **st,
            "average_percentage": round(avg_pct, 2),
            "letter_grade": _letter_grade_from_pct(avg_pct),
        })
        overall_possible += st["total_points_possible"]
        overall_earned += st["total_points_earned"]

    overall_avg = (overall_earned / overall_possible * 100) if overall_possible > 0 else 0

    return {
        "student_id": student.id,
        "student_name": f"{student.user.fname} {student.user.lname}" if student and student.user else "",
        "school_id": student.school_id,
        "overall_average_percentage": round(overall_avg, 2),
        "subjects": subjects_summary,
        "grades": grades_payload,
    }

@router.get("/grades/student/{student_id}/subject/{subject_id}")
def get_student_grades_for_subject_reports(
    student_id: int,
    subject_id: int,
    db: db_dependency,
    current_user: user_dependency
):
    """Return a student's grades in a subject for teachers/principals/admins in the same school.

    This endpoint mirrors the StudentGradeReport shape expected by the frontend services.
    """
    student = db.query(Student).filter(Student.id == student_id).first()
    subject = db.query(Subject).filter(Subject.id == subject_id).first()

    if not student or not subject:
        raise HTTPException(status_code=404, detail="Student or subject not found")

    # Authorize by school access, not by teaching assignment
    if not _user_has_school_access(current_user["user_id"], student.school_id, db):
        raise HTTPException(status_code=403, detail="Access denied to this student's school")
    if subject.school_id != student.school_id:
        raise HTTPException(status_code=400, detail="Subject and student belong to different schools")

    # Get all active assignments for the subject
    assignments = db.query(Assignment).filter(
        Assignment.subject_id == subject_id,
        Assignment.is_active == True
    ).all()

    grades: List[Dict[str, Any]] = []
    total_points_possible = 0
    total_points_earned = 0
    graded_count = 0

    # Preload teacher map for names
    teacher_ids = set()
    for a in assignments:
        if a.teacher_id:
            teacher_ids.add(a.teacher_id)
    teacher_map = {t.id: t for t in db.query(Teacher).filter(Teacher.id.in_(list(teacher_ids)) if teacher_ids else text("0=1")).all()}

    for a in assignments:
        total_points_possible += (a.max_points or 0)
        g = db.query(Grade).filter(
            Grade.assignment_id == a.id,
            Grade.student_id == student_id
        ).first()

        if g:
            graded_count += 1
            total_points_earned += (g.points_earned or 0)
            t = teacher_map.get(g.teacher_id)
            pct = round((g.points_earned / a.max_points) * 100, 2) if a.max_points and a.max_points > 0 else 0
            grades.append({
                "id": g.id,
                "assignment_id": a.id,
                "student_id": student_id,
                "teacher_id": g.teacher_id,
                "points_earned": g.points_earned,
                "feedback": g.feedback or "",
                "graded_date": g.graded_date.isoformat() if g.graded_date else None,
                "is_active": g.is_active,
                "assignment_title": a.title,
                "assignment_max_points": a.max_points,
                "student_name": f"{student.user.fname} {student.user.lname}" if student and student.user else "",
                "teacher_name": (f"{t.user.fname} {t.user.lname}" if t and t.user else "") if t else "",
                "percentage": pct,
            })

    avg_pct = (total_points_earned / total_points_possible * 100) if total_points_possible > 0 else 0

    return {
        "student_id": student_id,
        "student_name": f"{student.user.fname} {student.user.lname}" if student and student.user else "",
        "subject_id": subject_id,
        "subject_name": subject.name,
        "total_assignments": len(assignments),
        "graded_assignments": graded_count,
        "total_points_possible": total_points_possible,
        "total_points_earned": total_points_earned,
        "average_percentage": round(avg_pct, 2),
        "letter_grade": _letter_grade_from_pct(avg_pct),
        "grades": grades,
    }

# --- Helper Functions ---

def _get_user_school_id(user_id: int, db: Session) -> int:
    """Get the school_id for a user"""
    # Check if user is a teacher
    teacher = db.query(Teacher).filter(Teacher.user_id == user_id).first()
    if teacher:
        return teacher.school_id
    
    # Check if user is a principal
    school = db.query(School).filter(School.principal_id == user_id).first()
    if school:
        return school.id
    
    # If no school found, return 0 (will cause proper error)
    return 0

def _user_has_school_access(user_id: int, school_id: int, db: Session) -> bool:
    """Check if user has access to a school"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return False
    
    # If school_id is 0, try to get user's school from their teacher/principal record
    if school_id == 0:
        # Check if user is a teacher
        teacher = db.query(Teacher).filter(Teacher.user_id == user_id).first()
        if teacher:
            school_id = teacher.school_id
        else:
            # Check if user is a principal
            school = db.query(School).filter(School.principal_id == user_id).first()
            if school:
                school_id = school.id
    
    # Admin can access all schools
    if any(role.name.value == "admin" for role in user.roles):
        return True
    
    # Principal can access their school
    if any(role.name.value == "principal" for role in user.roles):
        school = db.query(School).filter(
            School.id == school_id,
            School.principal_id == user_id
        ).first()
        if school:
            return True
    
    # Teacher can access their school
    if any(role.name.value == "teacher" for role in user.roles):
        teacher = db.query(Teacher).filter(Teacher.user_id == user_id).first()
        if teacher and teacher.school_id == school_id:
            return True
    
    return False

def _user_has_report_access(user_id: int, report: Report, db: Session) -> bool:
    """Check if user has access to a specific report"""
    # Check school access first
    if not _user_has_school_access(user_id, report.school_id, db):
        return False
    
    # Report owner always has access
    if report.requested_by == user_id:
        return True
    
    # Check if report is public
    if report.is_public:
        return True
    
    # Check if report is shared with user
    share = db.query(ReportShare).filter(
        ReportShare.report_id == report.id,
        ReportShare.shared_with_user_id == user_id,
        ReportShare.is_active == True
    ).first()
    
    if share:
        # Check if share is not expired
        if not share.expires_date or share.expires_date > datetime.utcnow():
            return True
    
    return False

def _get_school_id_from_scope(request: ReportGenerationRequest, db: Session) -> int:
    """Get school_id from report scope"""
    if request.student_id:
        student = db.query(Student).filter(Student.id == request.student_id).first()
        return student.school_id if student else None
    elif request.classroom_id:
        classroom = db.query(Classroom).filter(Classroom.id == request.classroom_id).first()
        return classroom.school_id if classroom else None
    elif request.subject_id:
        subject = db.query(Subject).filter(Subject.id == request.subject_id).first()
        return subject.school_id if subject else None
    elif request.teacher_id:
        teacher = db.query(Teacher).filter(Teacher.id == request.teacher_id).first()
        return teacher.school_id if teacher else None
    elif request.assignment_id:
        assignment = db.query(Assignment).filter(Assignment.id == request.assignment_id).first()
        if assignment:
            subject = db.query(Subject).filter(Subject.id == assignment.subject_id).first()
            return subject.school_id if subject else None
    
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Cannot determine school from request scope"
    )

def _get_school_id_from_quick_scope(report_type: str, scope_id: int, db: Session) -> int:
    """Get school_id from quick report scope"""
    if report_type == "student_progress":
        student = db.query(Student).filter(Student.id == scope_id).first()
        return student.school_id if student else None
    elif report_type == "class_performance":
        classroom = db.query(Classroom).filter(Classroom.id == scope_id).first()
        return classroom.school_id if classroom else None
    elif report_type == "subject_analytics":
        subject = db.query(Subject).filter(Subject.id == scope_id).first()
        return subject.school_id if subject else None
    
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Cannot determine school from scope"
    )

def _generate_report_background(report_id: int, request: ReportGenerationRequest):
    """Background task to generate report"""
    # Populate report fields using the template_config as a schema-driven baseline
    # and mark as completed. This provides a non-empty report immediately.
    db_gen = get_db()
    db: Session = next(db_gen)
    try:
        report = db.query(Report).filter(Report.id == report_id).first()
        if not report:
            return

        # Load template JSON if available
        template_json: Dict[str, Any] = {}
        if report.template_id:
            tpl = db.query(ReportTemplate).filter(ReportTemplate.id == report.template_id).first()
            if tpl and tpl.template_config:
                try:
                    template_json = json.loads(tpl.template_config)
                except Exception:
                    template_json = {}

        # Assemble base report payload using the template structure
        assembled: Dict[str, Any] = {
            "meta": {
                "reportId": report.id,
                "title": report.title,
                "reportType": str(report.report_type.value if hasattr(report.report_type, 'value') else report.report_type),
                "format": str(report.format.value if hasattr(report.format, 'value') else report.format),
                "requestedAt": (report.requested_date.isoformat() if report.requested_date else None),
                "generatedAt": datetime.utcnow().isoformat(),
                "scope": {
                    "school_id": report.school_id,
                    "subject_id": report.subject_id,
                    "classroom_id": report.classroom_id,
                    "student_id": report.student_id,
                    "teacher_id": report.teacher_id,
                    "assignment_id": report.assignment_id,
                    "date_from": request.date_from.isoformat() if request.date_from else None,
                    "date_to": request.date_to.isoformat() if request.date_to else None,
                },
            },
            "template": template_json or {},
            "data": template_json or {},  # seed data with template fields so UI isn't empty
        }

        # Simple summary derived from template content
        summary: Dict[str, Any] = {
            "templateFieldCount": (len(template_json.keys()) if isinstance(template_json, dict) else 0),
            "hasStudentInfo": bool(template_json.get("studentInfo")) if isinstance(template_json, dict) else False,
            "hasSchoolInfo": bool(template_json.get("schoolInfo")) if isinstance(template_json, dict) else False,
            "hasAcademicPerformance": bool(template_json.get("academicPerformance")) if isinstance(template_json, dict) else False,
        }

        report.report_data = json.dumps(assembled)
        report.summary_stats = json.dumps(summary)
        report.generated_date = datetime.utcnow()
        report.status = ReportStatus.completed

        db.commit()
    except Exception as e:
        try:
            report = db.query(Report).filter(Report.id == report_id).first()
            if report:
                report.status = ReportStatus.failed
                report.error_message = str(e)
                db.commit()
        except Exception:
            pass
    finally:
        try:
            db.close()
        except Exception:
            pass

def _generate_quick_report_background(report_id: int, request: QuickReportRequest):
    """Background task to generate quick report"""
    db_gen = get_db()
    db: Session = next(db_gen)
    try:
        report = db.query(Report).filter(Report.id == report_id).first()
        if not report:
            return

        # For quick reports, no template is guaranteed; seed with minimal meta
        assembled = {
            "meta": {
                "reportId": report.id,
                "title": report.title,
                "reportType": str(report.report_type.value if hasattr(report.report_type, 'value') else report.report_type),
                "format": str(report.format.value if hasattr(report.format, 'value') else report.format),
                "requestedAt": (report.requested_date.isoformat() if report.requested_date else None),
                "generatedAt": datetime.utcnow().isoformat(),
                "quick": True,
            },
            "data": {},
        }
        report.report_data = json.dumps(assembled)
        report.summary_stats = json.dumps({"note": "Quick report generated with default content"})
        report.generated_date = datetime.utcnow()
        report.status = ReportStatus.completed
        db.commit()
    except Exception as e:
        try:
            report = db.query(Report).filter(Report.id == report_id).first()
            if report:
                report.status = ReportStatus.failed
                report.error_message = str(e)
                db.commit()
        except Exception:
            pass
    finally:
        try:
            db.close()
        except Exception:
            pass

def _generate_student_progress_preview(student_id: int, date_from: datetime, db: Session) -> ReportPreview:
    """Generate preview for student progress report"""
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    # Calculate basic metrics
    total_assignments = db.query(Assignment).join(Subject).filter(
        Subject.school_id == student.school_id,
        Assignment.created_date >= date_from
    ).count()
    
    completed_assignments = db.query(Grade).filter(
        Grade.student_id == student_id,
        Grade.graded_date >= date_from
    ).count()
    
    avg_grade = db.query(func.avg(Grade.points_earned)).filter(
        Grade.student_id == student_id,
        Grade.graded_date >= date_from
    ).scalar() or 0
    
    return ReportPreview(
        title=f"Student Progress Report - {student.user.full_name}",
        summary=f"Progress summary for the last {(datetime.utcnow() - date_from).days} days",
        key_metrics={
            "total_assignments": total_assignments,
            "completed_assignments": completed_assignments,
            "completion_rate": (completed_assignments / total_assignments * 100) if total_assignments > 0 else 0,
            "average_grade": round(avg_grade, 2)
        }
    )

def _generate_class_performance_preview(classroom_id: int, date_from: datetime, db: Session) -> ReportPreview:
    """Generate preview for class performance report"""
    classroom = db.query(Classroom).filter(Classroom.id == classroom_id).first()
    if not classroom:
        raise HTTPException(status_code=404, detail="Classroom not found")
    
    total_students = db.query(Student).filter(Student.classroom_id == classroom_id).count()
    
    avg_grade = db.query(func.avg(Grade.points_earned)).join(Student).filter(
        Student.classroom_id == classroom_id,
        Grade.graded_date >= date_from
    ).scalar() or 0
    
    return ReportPreview(
        title=f"Class Performance Report - {classroom.name}",
        summary=f"Performance summary for {total_students} students",
        key_metrics={
            "total_students": total_students,
            "average_class_grade": round(avg_grade, 2),
            "reporting_period": f"{(datetime.utcnow() - date_from).days} days"
        }
    )

def _generate_subject_analytics_preview(subject_id: int, date_from: datetime, db: Session) -> ReportPreview:
    """Generate preview for subject analytics report"""
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    
    total_assignments = db.query(Assignment).filter(
        Assignment.subject_id == subject_id,
        Assignment.created_date >= date_from
    ).count()
    
    total_students = db.query(Student).filter(
        Student.subjects.any(Subject.id == subject_id)
    ).count()
    
    avg_grade = db.query(func.avg(Grade.points_earned)).join(Assignment).filter(
        Assignment.subject_id == subject_id,
        Grade.graded_date >= date_from
    ).scalar() or 0
    
    return ReportPreview(
        title=f"Subject Analytics Report - {subject.name}",
        summary=f"Analytics for {total_students} students across {total_assignments} assignments",
        key_metrics={
            "total_assignments": total_assignments,
            "total_students": total_students,
            "average_grade": round(avg_grade, 2),
            "subject_name": subject.name
        }
    )

# --- Report Card OCR Extraction ---

def _parse_report_card_text(text: str) -> Dict[str, Any]:
    """Parse free-form report card text into the required JSON structure."""
    # Normalize whitespace
    raw = text or ""
    lines = [re.sub(r"\s+", " ", ln).strip() for ln in raw.splitlines() if ln.strip()]
    joined = "\n".join(lines)

    def find_first(patterns: List[str], flags=0) -> Optional[str]:
        for pat in patterns:
            m = re.search(pat, joined, flags)
            if m:
                # return first capturing group if present, else whole match
                return (m.group(1) if m.groups() else m.group(0)).strip()
        return None

    # Student & School
    name = find_first([
        r"(?:student\s*name|name)\s*[:.-]\s*([^\n]+)",
        r"(?:candidate)\s*[:.-]\s*([^\n]+)",
    ], flags=re.IGNORECASE)

    student_id = find_first([
        r"(?:student\s*(?:id|no|number)|reg(?:istration)?\s*no\.?|index\s*no\.?)\s*[:.-]\s*([^\n]+)",
    ], flags=re.IGNORECASE)

    school_name = find_first([
        r"(?:school|college|high\s*school|lycee)\s*[:.-]\s*([^\n]+)",
    ], flags=re.IGNORECASE)
    if not school_name and lines:
        # Heuristic: first uppercase-ish line with School/College
        for ln in lines[:5]:
            if re.search(r"school|college|lycee", ln, re.IGNORECASE):
                school_name = ln
                break

    academic_year = find_first([
        r"(?:academic|school)\s*year\s*[:.-]\s*([^\n]+)",
        r"(20\d{2}\s*/\s*20\d{2})",
    ], flags=re.IGNORECASE)

    student_class = find_first([
        r"(?:class|grade|option)\s*[:.-]\s*([^\n]+)",
        r"\b(S[1-6]\s*[- ]?\w+)\b",
    ], flags=re.IGNORECASE)

    # Subjects and grades
    common_subjects = [
        "mathematics", "math", "further mathematics", "english", "english language", "literature",
        "physics", "chemistry", "biology", "computer", "ict", "geography", "history", "economics",
        "commerce", "accounts", "agriculture", "agricultural science", "cre", "ire", "french",
        "kiswahili", "arabic", "entrepreneurship", "fine arts", "technical drawing"
    ]

    def extract_terms(block: str) -> Dict[str, Any]:
        term_patterns = [
            ("term1", [r"(?:term\s*1|1st\s*term|t\s*1|semester\s*1)[^\n]*?(?:total\s*[:.-]\s*)?(\d{1,3})"]),
            ("term2", [r"(?:term\s*2|2nd\s*term|t\s*2|semester\s*2)[^\n]*?(?:total\s*[:.-]\s*)?(\d{1,3})"]),
            ("term3", [r"(?:term\s*3|3rd\s*term|t\s*3|semester\s*3)[^\n]*?(?:total\s*[:.-]\s*)?(\d{1,3})"]),
        ]
        out = {
            "term1": {"total": None},
            "term2": {"total": None},
            "term3": {"total": None},
            "annual": {"total": None, "percentage": None},
        }
        lower = block.lower()
        for key, pats in term_patterns:
            for pat in pats:
                m = re.search(pat, lower, re.IGNORECASE)
                if m:
                    try:
                        out[key]["total"] = float(m.group(1))
                    except Exception:
                        pass
                    break
        # Annual/Final
        m_tot = re.search(r"(?:annual|final|gen(?:eral)?\s*total)\s*[:.-]?\s*(\d{1,3})", lower, re.IGNORECASE)
        if m_tot:
            try:
                out["annual"]["total"] = float(m_tot.group(1))
            except Exception:
                pass
        m_pct = re.search(r"(?:percent|percentage|%)[^\d]*(\d{1,3}(?:\.\d+)?)", lower, re.IGNORECASE)
        if m_pct:
            try:
                out["annual"]["percentage"] = float(m_pct.group(1))
            except Exception:
                pass
        return out

    subjects: List[Dict[str, Any]] = []
    lower_text = joined.lower()
    for subj in common_subjects:
        idx = lower_text.find(subj)
        if idx != -1:
            # Take a window of text around the subject to parse term totals
            window = lower_text[max(0, idx-80): idx+240]
            data = extract_terms(window)
            # Detect theory/practical labels nearby
            name = subj.title() if subj != "math" else "Mathematics"
            if re.search(r"practic(al|e)\b|pr\.?", window, re.IGNORECASE):
                name = f"{name} Practical"
            elif re.search(r"theory\b", window, re.IGNORECASE):
                name = f"{name} Theory"
            subjects.append({
                "subject": name,
                **data
            })

    # Remove duplicates by subject name, keeping the first occurrence
    seen = set()
    deduped = []
    for s in subjects:
        if s["subject"].lower() in seen:
            continue
        seen.add(s["subject"].lower())
        deduped.append(s)

    # Summary
    overall_total = find_first([
        r"(?:overall\s*total|total\s*marks|grand\s*total)\s*[:.-]\s*(\d{1,4})",
    ], flags=re.IGNORECASE)
    overall_pct = find_first([
        r"(?:overall\s*percentage|percentage|average\s*%)\s*[:.-]\s*(\d{1,3}(?:\.\d+)?)",
    ], flags=re.IGNORECASE)
    class_position = find_first([
        r"(?:position|rank)\s*[:.-]\s*([^\n]+)",
        r"\b(\d+\s*/\s*\d+)\b",
        r"\b(\d+\s+out\s+of\s+\d+)\b",
    ], flags=re.IGNORECASE)
    verdict = find_first([
        r"(?:verdict|decision)\s*[:.-]\s*([^\n]+)",
        r"\b(promoted|passed|fail|retained|congratulations?|excellent)\b",
    ], flags=re.IGNORECASE)
    comments = find_first([
        r"(?:comment|remarks?|teacher'?s\s*comments?)\s*[:.-]\s*([^\n]+)",
    ], flags=re.IGNORECASE)

    def to_num(s: Optional[str]) -> Optional[float]:
        if not s:
            return None
        try:
            return float(re.sub(r"[^\d.]", "", s))
        except Exception:
            return None

    result = {
        "studentInfo": {
            "fullName": name or None,
            "studentId": student_id or None,
            "class": student_class or None,
            "academicYear": academic_year or None,
        },
        "schoolInfo": {
            "name": school_name or None,
        },
        "academicPerformance": deduped if deduped else [],
        "summary": {
            "overallTotal": to_num(overall_total),
            "overallPercentage": to_num(overall_pct),
            "classPosition": class_position or None,
            "verdict": verdict or None,
            "comments": comments or None,
        }
    }
    return result

@router.post("/report-card/extract")
async def extract_report_card(
    file: UploadFile = File(...),
    current_user: user_dependency = None,
    db: db_dependency = None
):
    """Delegate report-card extraction to Kana Gemini OCR only; no Python OCR fallback."""
    filename = file.filename or "uploaded_file"
    if not filename:
        raise HTTPException(status_code=400, detail="No file provided")

    content = await file.read()
    kana_url = os.getenv("KANA_API_URL", "http://localhost:10000")
    try:
        resp = requests.post(
            f"{kana_url}/api/kana/report-card/extract",
            files={"file": (filename, content, file.content_type or "application/octet-stream")},
            timeout=60
        )
        if resp.status_code == 200:
            return resp.json()
        return JSONResponse(status_code=resp.status_code, content={"error": resp.text})
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Kana OCR unavailable: {str(e)}")