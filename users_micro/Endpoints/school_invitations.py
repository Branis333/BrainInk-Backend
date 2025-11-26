"""
School Invitation Endpoints - Replaces Access Code System
This module handles email-based invitations for teachers and students
"""

from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, status
from typing import Annotated, List
from sqlalchemy.orm import Session
from sqlalchemy import func

from users_micro.db.connection import db_dependency
from models.study_area_models import (
    School, Student, Teacher, UserRole, SchoolInvitation, InvitationType
)
from models.users_models import User
from schemas.school_invitations_schemas import (
    SchoolInvitationCreate, SchoolInvitationOut, BulkInvitationCreate, 
    BulkInvitationResponse, JoinSchoolByEmailRequest, JoinSchoolResponse
)
from Endpoints.auth import get_current_user
from Endpoints.utils import ensure_user_role, assign_role_to_user_by_email

router = APIRouter(tags=["School Invitations"])

user_dependency = Annotated[dict, Depends(get_current_user)]

# === PRINCIPAL INVITATION ENDPOINTS ===

@router.post("/invitations/create", response_model=SchoolInvitationOut)
async def create_school_invitation(
    invitation: SchoolInvitationCreate,
    db: db_dependency,
    current_user: user_dependency
):
    """
    Create an invitation for a teacher or student (principals only)
    """
    ensure_user_role(db, current_user["user_id"], UserRole.principal)
    
    # Verify principal owns the school
    school = db.query(School).filter(
        School.id == invitation.school_id,
        School.principal_id == current_user["user_id"],
        School.is_active == True
    ).first()
    
    if not school:
        raise HTTPException(
            status_code=403, 
            detail="You can only create invitations for schools you manage"
        )
    
    # Check if invitation already exists
    existing_invitation = db.query(SchoolInvitation).filter(
        SchoolInvitation.email == invitation.email.lower(),
        SchoolInvitation.school_id == invitation.school_id,
        SchoolInvitation.invitation_type == invitation.invitation_type,
        SchoolInvitation.is_active == True
    ).first()
    
    if existing_invitation:
        raise HTTPException(
            status_code=400,
            detail=f"Active invitation already exists for {invitation.email} as {invitation.invitation_type.value}"
        )
    
    # Check if user is already in the school in this role
    user = db.query(User).filter(User.email == invitation.email.lower()).first()
    if user:
        if invitation.invitation_type == InvitationType.teacher:
            existing_teacher = db.query(Teacher).filter(
                Teacher.user_id == user.id,
                Teacher.school_id == invitation.school_id
            ).first()
            if existing_teacher:
                raise HTTPException(
                    status_code=400,
                    detail=f"{invitation.email} is already a teacher in this school"
                )
        elif invitation.invitation_type == InvitationType.student:
            existing_student = db.query(Student).filter(
                Student.user_id == user.id,
                Student.school_id == invitation.school_id
            ).first()
            if existing_student:
                raise HTTPException(
                    status_code=400,
                    detail=f"{invitation.email} is already a student in this school"
                )
    
    # Create the invitation
    new_invitation = SchoolInvitation(
        email=invitation.email.lower(),
        invitation_type=invitation.invitation_type,
        school_id=invitation.school_id,
        invited_by=current_user["user_id"]
    )
    
    db.add(new_invitation)
    db.commit()
    db.refresh(new_invitation)
    
    return SchoolInvitationOut(
        id=new_invitation.id,
        email=new_invitation.email,
        invitation_type=new_invitation.invitation_type,
        school_id=new_invitation.school_id,
        school_name=school.name,
        invited_by=new_invitation.invited_by,
        invited_date=new_invitation.invited_date,
        is_used=new_invitation.is_used,
        used_date=new_invitation.used_date,
        is_active=new_invitation.is_active
    )

@router.post("/invitations/bulk-create", response_model=BulkInvitationResponse)
async def create_bulk_invitations(
    bulk_invitation: BulkInvitationCreate,
    db: db_dependency,
    current_user: user_dependency
):
    """
    Create multiple invitations at once (principals only)
    """
    ensure_user_role(db, current_user["user_id"], UserRole.principal)
    
    # Verify principal owns the school
    school = db.query(School).filter(
        School.id == bulk_invitation.school_id,
        School.principal_id == current_user["user_id"],
        School.is_active == True
    ).first()
    
    if not school:
        raise HTTPException(
            status_code=403, 
            detail="You can only create invitations for schools you manage"
        )
    
    successful_invitations = []
    failed_emails = []
    errors = []
    
    for email in bulk_invitation.emails:
        try:
            # Check if invitation already exists
            existing_invitation = db.query(SchoolInvitation).filter(
                SchoolInvitation.email == email.lower(),
                SchoolInvitation.school_id == bulk_invitation.school_id,
                SchoolInvitation.invitation_type == bulk_invitation.invitation_type,
                SchoolInvitation.is_active == True
            ).first()
            
            if existing_invitation:
                failed_emails.append(email)
                errors.append(f"{email}: Already has active invitation")
                continue
            
            # Check if user is already in the school
            user = db.query(User).filter(User.email == email.lower()).first()
            if user:
                skip = False
                if bulk_invitation.invitation_type == InvitationType.teacher:
                    existing_teacher = db.query(Teacher).filter(
                        Teacher.user_id == user.id,
                        Teacher.school_id == bulk_invitation.school_id
                    ).first()
                    if existing_teacher:
                        failed_emails.append(email)
                        errors.append(f"{email}: Already a teacher in this school")
                        skip = True
                elif bulk_invitation.invitation_type == InvitationType.student:
                    existing_student = db.query(Student).filter(
                        Student.user_id == user.id,
                        Student.school_id == bulk_invitation.school_id
                    ).first()
                    if existing_student:
                        failed_emails.append(email)
                        errors.append(f"{email}: Already a student in this school")
                        skip = True
                
                if skip:
                    continue
            
            # Create the invitation
            new_invitation = SchoolInvitation(
                email=email.lower(),
                invitation_type=bulk_invitation.invitation_type,
                school_id=bulk_invitation.school_id,
                invited_by=current_user["user_id"]
            )
            
            db.add(new_invitation)
            db.commit()
            db.refresh(new_invitation)
            
            successful_invitations.append(SchoolInvitationOut(
                id=new_invitation.id,
                email=new_invitation.email,
                invitation_type=new_invitation.invitation_type,
                school_id=new_invitation.school_id,
                school_name=school.name,
                invited_by=new_invitation.invited_by,
                invited_date=new_invitation.invited_date,
                is_used=new_invitation.is_used,
                used_date=new_invitation.used_date,
                is_active=new_invitation.is_active
            ))
            
        except Exception as e:
            db.rollback()
            failed_emails.append(email)
            errors.append(f"{email}: {str(e)}")
    
    return BulkInvitationResponse(
        success_count=len(successful_invitations),
        failed_count=len(failed_emails),
        successful_invitations=successful_invitations,
        failed_emails=failed_emails,
        errors=errors
    )

@router.get("/invitations/my-school", response_model=List[SchoolInvitationOut])
async def get_my_school_invitations(
    db: db_dependency,
    current_user: user_dependency
):
    """
    Get all invitations for the principal's school
    """
    ensure_user_role(db, current_user["user_id"], UserRole.principal)
    
    # Get principal's school
    school = db.query(School).filter(
        School.principal_id == current_user["user_id"],
        School.is_active == True
    ).first()
    
    if not school:
        raise HTTPException(status_code=404, detail="No active school found for this principal")
    
    invitations = db.query(SchoolInvitation).filter(
        SchoolInvitation.school_id == school.id,
        SchoolInvitation.is_active == True
    ).order_by(SchoolInvitation.invited_date.desc()).all()
    
    return [
        SchoolInvitationOut(
            id=inv.id,
            email=inv.email,
            invitation_type=inv.invitation_type,
            school_id=inv.school_id,
            school_name=school.name,
            invited_by=inv.invited_by,
            invited_date=inv.invited_date,
            is_used=inv.is_used,
            used_date=inv.used_date,
            is_active=inv.is_active
        )
        for inv in invitations
    ]

@router.delete("/invitations/{invitation_id}")
async def cancel_invitation(
    invitation_id: int,
    db: db_dependency,
    current_user: user_dependency
):
    """
    Cancel/deactivate an invitation (principals only)
    """
    ensure_user_role(db, current_user["user_id"], UserRole.principal)
    
    invitation = db.query(SchoolInvitation).filter(
        SchoolInvitation.id == invitation_id,
        SchoolInvitation.invited_by == current_user["user_id"],
        SchoolInvitation.is_active == True
    ).first()
    
    if not invitation:
        raise HTTPException(
            status_code=404, 
            detail="Invitation not found or you don't have permission to cancel it"
        )
    
    invitation.is_active = False
    db.commit()
    
    return {"message": f"Invitation for {invitation.email} has been cancelled"}

# === STUDENT/TEACHER JOIN ENDPOINTS ===

@router.post("/join-school/student", response_model=JoinSchoolResponse)
async def join_school_as_student(
    request: JoinSchoolByEmailRequest,
    db: db_dependency,
    current_user: user_dependency
):
    """
    Join a school as student (requires valid invitation)
    """
    user = db.query(User).filter(User.id == current_user["user_id"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check for valid invitation
    invitation = db.query(SchoolInvitation).filter(
        SchoolInvitation.email == user.email.lower(),
        SchoolInvitation.school_id == request.school_id,
        SchoolInvitation.invitation_type == InvitationType.student,
        SchoolInvitation.is_active == True,
        SchoolInvitation.is_used == False
    ).first()
    
    if not invitation:
        raise HTTPException(
            status_code=403,
            detail="No valid invitation found. Please contact the school principal to get invited."
        )
    
    # Get school info
    school = db.query(School).filter(
        School.id == request.school_id,
        School.is_active == True
    ).first()
    
    if not school:
        raise HTTPException(status_code=404, detail="School not found or inactive")
    
    # Check if already a student
    existing_student = db.query(Student).filter(
        Student.user_id == current_user["user_id"],
        Student.school_id == request.school_id
    ).first()
    
    if existing_student:
        raise HTTPException(status_code=400, detail="You are already a student in this school")
    
    # Create student profile
    new_student = Student(
        user_id=current_user["user_id"],
        school_id=request.school_id,
        enrollment_date=datetime.utcnow()
    )
    
    # Assign student role and mark invitation as used
    assign_role_to_user_by_email(db, user.email, UserRole.student)
    invitation.is_used = True
    invitation.used_date = datetime.utcnow()
    
    db.add(new_student)
    db.commit()
    db.refresh(new_student)
    
    return JoinSchoolResponse(
        success=True,
        message=f"Successfully joined {school.name} as a student",
        school_name=school.name,
        role="student",
        school_id=school.id
    )

@router.post("/join-school/teacher", response_model=JoinSchoolResponse)
async def join_school_as_teacher(
    request: JoinSchoolByEmailRequest,
    db: db_dependency,
    current_user: user_dependency
):
    """
    Join a school as teacher (requires valid invitation)
    """
    user = db.query(User).filter(User.id == current_user["user_id"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check for valid invitation
    invitation = db.query(SchoolInvitation).filter(
        SchoolInvitation.email == user.email.lower(),
        SchoolInvitation.school_id == request.school_id,
        SchoolInvitation.invitation_type == InvitationType.teacher,
        SchoolInvitation.is_active == True,
        SchoolInvitation.is_used == False
    ).first()
    
    if not invitation:
        raise HTTPException(
            status_code=403,
            detail="No valid invitation found. Please contact the school principal to get invited."
        )
    
    # Get school info
    school = db.query(School).filter(
        School.id == request.school_id,
        School.is_active == True
    ).first()
    
    if not school:
        raise HTTPException(status_code=404, detail="School not found or inactive")
    
    # Check if already a teacher
    existing_teacher = db.query(Teacher).filter(
        Teacher.user_id == current_user["user_id"],
        Teacher.school_id == request.school_id
    ).first()
    
    if existing_teacher:
        raise HTTPException(status_code=400, detail="You are already a teacher in this school")
    
    # Create teacher profile
    new_teacher = Teacher(
        user_id=current_user["user_id"],
        school_id=request.school_id,
        hire_date=datetime.utcnow()
    )
    
    # Assign teacher role and mark invitation as used
    assign_role_to_user_by_email(db, user.email, UserRole.teacher)
    invitation.is_used = True
    invitation.used_date = datetime.utcnow()
    
    db.add(new_teacher)
    db.commit()
    db.refresh(new_teacher)
    
    return JoinSchoolResponse(
        success=True,
        message=f"Successfully joined {school.name} as a teacher",
        school_name=school.name,
        role="teacher",
        school_id=school.id
    )

@router.get("/invitations/check-eligibility/{school_id}")
async def check_join_eligibility(
    school_id: int,
    db: db_dependency,
    current_user: user_dependency
):
    """
    Check if current user has any invitations for a specific school
    """
    user = db.query(User).filter(User.id == current_user["user_id"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    school = db.query(School).filter(
        School.id == school_id,
        School.is_active == True
    ).first()
    
    if not school:
        raise HTTPException(status_code=404, detail="School not found or inactive")
    
    # Check for active invitations
    invitations = db.query(SchoolInvitation).filter(
        SchoolInvitation.email == user.email.lower(),
        SchoolInvitation.school_id == school_id,
        SchoolInvitation.is_active == True,
        SchoolInvitation.is_used == False
    ).all()
    
    eligible_roles = [inv.invitation_type.value for inv in invitations]
    
    return {
        "school_id": school_id,
        "school_name": school.name,
        "user_email": user.email,
        "eligible_roles": eligible_roles,
        "has_invitations": len(eligible_roles) > 0
    }
