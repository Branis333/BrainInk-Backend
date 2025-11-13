"""
Script to initialize default roles in the database
Run this after creating the database tables
"""
from sqlalchemy.orm import sessionmaker
from db.connection import engine
from models.study_area_models import Role, UserRole

def initialize_roles():
    """Initialize default roles in the database"""
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        # Create default roles if they don't exist
        roles_to_create = [
            (UserRole.normal_user, "Default role for new users"),
            (UserRole.student, "Student role for school students"),
            (UserRole.teacher, "Teacher role for school teachers"),
            (UserRole.principal, "Principal role for school administrators"),
            (UserRole.admin, "System administrator role")
        ]
        
        for role_name, description in roles_to_create:
            existing_role = db.query(Role).filter(Role.name == role_name).first()
            if not existing_role:
                role = Role(name=role_name, description=description)
                db.add(role)
                print(f"Created role: {role_name.value}")
            else:
                print(f"Role already exists: {role_name.value}")
        
        db.commit()
        print("Role initialization completed successfully!")
        
    except Exception as e:
        print(f"Error initializing roles: {str(e)}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    initialize_roles()
