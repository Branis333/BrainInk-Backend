"""
Shared utility functions for the study area modules
This module contains common functions used across school_management, academic_management, and grades modules
"""

from typing import List
from sqlalchemy.orm import Session
from fastapi import HTTPException
import random
import string

from models.users_models import User
from models.study_area_models import Role, UserRole


def _get_user_roles(db: Session, user_id: int) -> List[UserRole]:
    """Get all user roles, return [normal_user] if no roles assigned"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.roles:
        return [UserRole.normal_user]
    return [role.name for role in user.roles]


def check_user_role(db: Session, user_id: int, required_role: UserRole) -> bool:
    """Check if user has required role"""
    user_roles = _get_user_roles(db, user_id)
    return required_role in user_roles


def ensure_user_role(db: Session, user_id: int, required_role: UserRole):
    """Raise HTTPException if user doesn't have required role"""
    if not check_user_role(db, user_id, required_role):
        raise HTTPException(
            status_code=403, 
            detail=f"Only users with {required_role.value} role can access this endpoint"
        )


def check_user_has_any_role(db: Session, user_id: int, required_roles: List[UserRole]) -> bool:
    """Check if user has any of the required roles"""
    user_roles = _get_user_roles(db, user_id)
    return any(role in user_roles for role in required_roles)


def ensure_user_has_any_role(db: Session, user_id: int, required_roles: List[UserRole]):
    """Raise HTTPException if user doesn't have any of the required roles"""
    if not check_user_has_any_role(db, user_id, required_roles):
        role_names = [role.value for role in required_roles]
        raise HTTPException(
            status_code=403, 
            detail=f"Only users with one of these roles can access this endpoint: {', '.join(role_names)}"
        )


def generate_random_code(length=8):
    """Generate a unique random access code"""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))


def assign_role_to_user_by_email(db: Session, email: str, role: UserRole) -> bool:
    """
    Assign a role to a user by email if they exist in the system
    Returns True if role was assigned, False if user doesn't exist
    """
    try:
        user = db.query(User).filter(User.email == email.lower()).first()
        if user:
            target_role = db.query(Role).filter(Role.name == role).first()
            if target_role and not user.has_role(role):
                user.add_role(target_role)
                print(f"✅ Automatically assigned {role.value} role to user {user.username} ({email})")
                return True
            elif user.has_role(role):
                print(f"ℹ️  User {user.username} ({email}) already has {role.value} role")
                return True
        else:
            print(f"ℹ️  User with email {email} not found in system - role will be assigned when they join")
        return False
    except Exception as e:
        print(f"❌ Error assigning role to {email}: {str(e)}")
        return False
