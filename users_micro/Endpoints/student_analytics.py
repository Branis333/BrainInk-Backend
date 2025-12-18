from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Depends, status
from typing import Annotated, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from db.connection import db_dependency
from models.study_area_models import (
    Role, School, Subject, Student, Teacher, UserRole, Assignment, Grade,
    subject_students, subject_teachers
)
from models.users_models import User
from Endpoints.auth import get_current_user
from Endpoints.utils import ensure_user_role

router = APIRouter(tags=["Student Analytics", "Student Dashboard"])

user_dependency = Annotated[dict, Depends(get_current_user)]

# === STUDENT DASHBOARD ENDPOINTS ===

@router.get("/analytics/student-dashboard")
async def get_student_dashboard(db: db_dependency, current_user: user_dependency):
    """
    Get comprehensive academic overview for the student
    """
    ensure_user_role(db, current_user["user_id"], UserRole.student)
    
    # Get student record
    student = db.query(Student).filter(
        Student.user_id == current_user["user_id"],
        Student.is_active == True
    ).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student profile not found")
    
    # Get user info
    user = db.query(User).filter(User.id == student.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get school info
    school = db.query(School).filter(School.id == student.school_id).first()
    school_name = school.name if school else "Unknown School"
    
    # Get classroom info
    classroom_name = None
    if student.classroom_id:
        from models.study_area_models import Classroom
        classroom = db.query(Classroom).filter(Classroom.id == student.classroom_id).first()
        classroom_name = classroom.name if classroom else None
    
    # Get enrolled subjects
    try:
        subjects = db.query(Subject).join(
            subject_students, Subject.id == subject_students.c.subject_id
        ).filter(
            subject_students.c.student_id == student.id,
            Subject.is_active == True
        ).all()
    except Exception:
        subjects = db.query(Subject).filter(
            Subject.school_id == student.school_id,
            Subject.is_active == True
        ).all()
    
    # Get assignments for all subjects
    subject_ids = [subject.id for subject in subjects]
    assignments = []
    if subject_ids:
        assignments = db.query(Assignment).filter(
            Assignment.subject_id.in_(subject_ids),
            Assignment.is_active == True
        ).all()
    
    # Get grades for this student
    assignment_ids = [assignment.id for assignment in assignments]
    grades = []
    if assignment_ids:
        grades = db.query(Grade).filter(
            Grade.assignment_id.in_(assignment_ids),
            Grade.student_id == student.id,
            Grade.is_active == True
        ).all()
    
    # Calculate metrics
    total_subjects = len(subjects)
    total_assignments = len(assignments)
    completed_assignments = len(grades)
    
    # Calculate average grade
    average_grade = 0
    if grades:
        total_points = sum(grade.points_earned for grade in grades)
        max_points = 0
        for grade in grades:
            assignment = next((a for a in assignments if a.id == grade.assignment_id), None)
            if assignment:
                max_points += assignment.max_points
        
        if max_points > 0:
            average_grade = (total_points / max_points) * 100
    
    completion_rate = (completed_assignments / total_assignments * 100) if total_assignments > 0 else 0
    
    # Get recent grades (last 5)
    recent_grades = sorted(grades, key=lambda g: g.graded_date, reverse=True)[:5]
    recent_grades_formatted = []
    for grade in recent_grades:
        assignment = next((a for a in assignments if a.id == grade.assignment_id), None)
        subject = next((s for s in subjects if s.id == assignment.subject_id), None) if assignment else None
        
        percentage = (grade.points_earned / assignment.max_points * 100) if assignment else 0
        
        recent_grades_formatted.append({
            "id": grade.id,
            "assignment_id": grade.assignment_id,
            "student_id": grade.student_id,
            "teacher_id": grade.teacher_id,
            "points_earned": grade.points_earned,
            "feedback": grade.feedback,
            "graded_date": grade.graded_date,
            "is_active": grade.is_active,
            "assignment_title": assignment.title if assignment else None,
            "assignment_max_points": assignment.max_points if assignment else None,
            "percentage": percentage
        })
    
    # Get upcoming assignments (next 5 due)
    upcoming_assignments = []
    for assignment in assignments:
        if assignment.due_date:
            due_date = datetime.fromisoformat(str(assignment.due_date).replace('Z', '+00:00')) if isinstance(assignment.due_date, str) else assignment.due_date
            if due_date > datetime.now():
                # Check if already completed
                has_grade = any(g.assignment_id == assignment.id for g in grades)
                if not has_grade:
                    subject = next((s for s in subjects if s.id == assignment.subject_id), None)
                    upcoming_assignments.append({
                        "id": assignment.id,
                        "title": assignment.title,
                        "description": assignment.description,
                        "subtopic": assignment.subtopic,
                        "subject_id": assignment.subject_id,
                        "teacher_id": assignment.teacher_id,
                        "max_points": assignment.max_points,
                        "due_date": assignment.due_date,
                        "created_date": assignment.created_date,
                        "is_active": assignment.is_active,
                        "subject_name": subject.name if subject else None
                    })
    
    upcoming_assignments = sorted(upcoming_assignments, key=lambda a: a["due_date"])[:5]
    
    # Calculate subject performance
    subject_performance = []
    for subject in subjects:
        subject_assignments = [a for a in assignments if a.subject_id == subject.id]
        subject_grades = [g for g in grades if any(a.id == g.assignment_id for a in subject_assignments)]
        
        subject_total = len(subject_assignments)
        subject_completed = len(subject_grades)
        
        subject_avg = 0
        if subject_grades:
            total_points = sum(g.points_earned for g in subject_grades)
            max_points = sum(a.max_points for a in subject_assignments if any(g.assignment_id == a.id for g in subject_grades))
            if max_points > 0:
                subject_avg = (total_points / max_points) * 100
        
        subject_performance.append({
            "subject_id": subject.id,
            "subject_name": subject.name,
            "average_grade": subject_avg,
            "total_assignments": subject_total,
            "completed_assignments": subject_completed
        })
    
    # Generate learning recommendations based on performance
    learning_recommendations = []
    low_performing_subjects = [sp for sp in subject_performance if sp["average_grade"] < 70 and sp["completed_assignments"] > 0]
    
    if low_performing_subjects:
        for subject in low_performing_subjects:
            learning_recommendations.append(f"Focus on improving in {subject['subject_name']} - current average: {subject['average_grade']:.1f}%")
    
    if completion_rate < 80:
        learning_recommendations.append("Try to complete assignments on time to improve your overall progress")
    
    if average_grade > 90:
        learning_recommendations.append("Excellent work! Consider taking on more challenging assignments")
    elif average_grade > 80:
        learning_recommendations.append("Good progress! Keep up the consistent effort")
    
    if not learning_recommendations:
        learning_recommendations.append("Keep up the great work with your studies!")
    
    return {
        "student_info": {
            "id": student.id,
            "name": f"{user.fname} {user.lname}",
            "email": user.email,
            "school_name": school_name,
            "classroom_name": classroom_name
        },
        "academic_overview": {
            "total_subjects": total_subjects,
            "total_assignments": total_assignments,
            "completed_assignments": completed_assignments,
            "average_grade": round(average_grade, 2),
            "completion_rate": round(completion_rate, 2)
        },
        "recent_grades": recent_grades_formatted,
        "upcoming_assignments": upcoming_assignments,
        "subject_performance": subject_performance,
        "learning_recommendations": learning_recommendations
    }

@router.get("/analytics/student-subject-performance/{subject_id}")
async def get_student_subject_performance(
    subject_id: int,
    db: db_dependency,
    current_user: user_dependency
):
    """
    Get detailed performance analytics for a specific subject
    """
    ensure_user_role(db, current_user["user_id"], UserRole.student)
    
    # Get student record
    student = db.query(Student).filter(
        Student.user_id == current_user["user_id"],
        Student.is_active == True
    ).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student profile not found")
    
    # Get subject and verify enrollment
    subject = db.query(Subject).filter(
        Subject.id == subject_id,
        Subject.is_active == True
    ).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    
    # Check enrollment
    try:
        enrollment = db.query(subject_students).filter(
            subject_students.c.subject_id == subject_id,
            subject_students.c.student_id == student.id
        ).first()
        
        if not enrollment and subject.school_id != student.school_id:
            raise HTTPException(status_code=403, detail="You are not enrolled in this subject")
    except Exception:
        if subject.school_id != student.school_id:
            raise HTTPException(status_code=403, detail="You are not enrolled in this subject")
    
    # Get assignments for this subject
    assignments = db.query(Assignment).filter(
        Assignment.subject_id == subject_id,
        Assignment.is_active == True
    ).all()
    
    # Get grades for this student in this subject
    assignment_ids = [a.id for a in assignments]
    grades = []
    if assignment_ids:
        grades = db.query(Grade).filter(
            Grade.assignment_id.in_(assignment_ids),
            Grade.student_id == student.id,
            Grade.is_active == True
        ).all()
    
    # Calculate detailed performance metrics
    total_assignments = len(assignments)
    completed_assignments = len(grades)
    completion_rate = (completed_assignments / total_assignments * 100) if total_assignments > 0 else 0
    
    # Grade breakdown
    grade_distribution = {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0}
    total_points = 0
    max_points = 0
    
    assignment_performance = []
    for assignment in assignments:
        grade = next((g for g in grades if g.assignment_id == assignment.id), None)
        
        performance_item = {
            "assignment_id": assignment.id,
            "assignment_title": assignment.title,
            "max_points": assignment.max_points,
            "due_date": assignment.due_date,
            "completed": grade is not None
        }
        
        if grade:
            percentage = (grade.points_earned / assignment.max_points) * 100
            performance_item.update({
                "points_earned": grade.points_earned,
                "percentage": percentage,
                "feedback": grade.feedback,
                "graded_date": grade.graded_date
            })
            
            total_points += grade.points_earned
            max_points += assignment.max_points
            
            # Grade distribution
            if percentage >= 90:
                grade_distribution["A"] += 1
            elif percentage >= 80:
                grade_distribution["B"] += 1
            elif percentage >= 70:
                grade_distribution["C"] += 1
            elif percentage >= 60:
                grade_distribution["D"] += 1
            else:
                grade_distribution["F"] += 1
        
        assignment_performance.append(performance_item)
    
    overall_percentage = (total_points / max_points * 100) if max_points > 0 else 0
    
    # Performance trends (last 30 days)
    thirty_days_ago = datetime.now() - timedelta(days=30)
    recent_grades = [g for g in grades if g.graded_date >= thirty_days_ago]
    
    trend_data = []
    for grade in sorted(recent_grades, key=lambda g: g.graded_date):
        assignment = next((a for a in assignments if a.id == grade.assignment_id), None)
        if assignment:
            percentage = (grade.points_earned / assignment.max_points) * 100
            trend_data.append({
                "date": grade.graded_date,
                "percentage": percentage,
                "assignment_title": assignment.title
            })
    
    # Strengths and improvement areas
    strengths = []
    improvement_areas = []
    
    if overall_percentage >= 90:
        strengths.append("Excellent overall performance in this subject")
    elif overall_percentage >= 80:
        strengths.append("Strong performance in this subject")
    
    if completion_rate >= 95:
        strengths.append("Excellent assignment completion rate")
    elif completion_rate < 70:
        improvement_areas.append("Focus on completing assignments on time")
    
    if grade_distribution["A"] > grade_distribution["F"]:
        strengths.append("Consistent high-quality work")
    
    if grade_distribution["F"] > 0:
        improvement_areas.append("Work on understanding core concepts to avoid failing grades")
    
    return {
        "subject_id": subject_id,
        "subject_name": subject.name,
        "overall_performance": {
            "total_assignments": total_assignments,
            "completed_assignments": completed_assignments,
            "completion_rate": round(completion_rate, 2),
            "overall_percentage": round(overall_percentage, 2),
            "total_points": total_points,
            "max_points": max_points
        },
        "grade_distribution": grade_distribution,
        "assignment_performance": assignment_performance,
        "performance_trends": trend_data,
        "strengths": strengths,
        "improvement_areas": improvement_areas
    }

# === STUDENT STATUS ENDPOINTS ===

@router.get("/user/status")
async def get_user_status(db: db_dependency, current_user: user_dependency):
    """
    Get current user's status and available actions
    """
    user_roles = []
    try:
        from Endpoints.utils import _get_user_roles
        user_roles = _get_user_roles(db, current_user["user_id"])
    except Exception:
        pass
    
    # Get user info
    user = db.query(User).filter(User.id == current_user["user_id"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    status_info = {
        "user_id": user.id,
        "username": user.username,
        "email": user.email,
        "roles": [role.value if hasattr(role, 'value') else str(role) for role in user_roles],
        "is_student": UserRole.student in user_roles,
        "is_teacher": UserRole.teacher in user_roles,
        "is_principal": UserRole.principal in user_roles,
        "available_actions": []
    }
    
    # Add available actions based on roles
    if UserRole.student in user_roles:
        student = db.query(Student).filter(
            Student.user_id == user.id,
            Student.is_active == True
        ).first()
        
        if student:
            status_info.update({
                "student_info": {
                    "id": student.id,
                    "school_id": student.school_id,
                    "classroom_id": student.classroom_id,
                    "enrollment_date": student.enrollment_date
                }
            })
            status_info["available_actions"].extend([
                "view_subjects",
                "view_assignments", 
                "view_grades",
                "view_dashboard"
            ])
        else:
            status_info["available_actions"].append("complete_student_profile")
    
    if not user_roles or UserRole.normal_user in user_roles:
        status_info["available_actions"].extend([
            "join_school_as_student",
            "join_school_as_teacher",
            "request_principal_role"
        ])
    
    return status_info
