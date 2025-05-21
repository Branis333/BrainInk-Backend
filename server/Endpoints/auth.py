from datetime import timedelta, datetime
from fastapi import APIRouter, HTTPException, Depends, Response, status
from typing import Annotated, Optional
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy import or_
from pydantic import BaseModel
from dotenv import load_dotenv
import os

from db.connection import db_dependency
from models.users_models import User, OTP  # Import User class directly
from schemas.schemas import CreateUserRequest, UserLogin, Token
from schemas.return_schemas import ReturnUser
from functions.encrypt import encrypt_any_data
from google.oauth2 import id_token
from google.auth.transport import requests

# Load environment variables
load_dotenv()

router = APIRouter(tags=["Authentication"])

# Environment variables
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")

# Password and token setup
bcrypt_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_bearer = OAuth2PasswordBearer(tokenUrl="login")

class UserResponse(BaseModel):
    access_token: str
    token_type: str
    encrypted_data: str

class GoogleAuthRequest(BaseModel):
    token: str

# Authentication function
def authenticate_user(username: str, password: str, db):
    user = (
        db.query(User)  # Changed from user to User
        .filter(
            or_(
                User.username == username,  # Changed from user.username to User.username
                User.email == username      # Changed from user.email to User.email
            )
        )
        .first()
    )
    if not user:
        return False
    if not bcrypt_context.verify(password, user.password_hash):
        return False
    return user

# Token creation
def create_access_token(
    username: str, user_id: int, acc_type: str = "user", expires_delta: timedelta = timedelta(minutes=60 * 24)
):
    encode = {"uname": username, "id": user_id, "acc_type": acc_type}
    expires = datetime.utcnow() + expires_delta
    encode.update({"exp": expires})
    return jwt.encode(encode, SECRET_KEY, algorithm=ALGORITHM)

# Current user dependency
async def get_current_user(token: Annotated[str, Depends(oauth2_bearer)]):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("uname")
        user_id: int = payload.get("id")
        acc_type: str = payload.get("acc_type")
        if username is None or user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
            )
        return {"username": username, "user_id": user_id, "acc_type": acc_type}
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed. Your token is invalid or has expired.",
        )

user_dependency = Annotated[dict, Depends(get_current_user)]

@router.post("/register", response_model=UserResponse)
async def create_user(db: db_dependency, user_request: CreateUserRequest):
    """
    Register a new user account
    """
    # Check if username or email already exists
    check_username = db.query(User).filter(User.username == user_request.username).first()  # Changed from users to User
    check_email = db.query(User).filter(User.email == user_request.email).first()  # Changed from users to User

    if check_username:
        raise HTTPException(status_code=400, detail="Username already taken")

    if check_email:
        raise HTTPException(status_code=400, detail="Email already taken")

    try:
        # Create user model
        new_user = User(  # Changed from Users to User
            fname=user_request.fname,
            lname=user_request.lname,
            email=user_request.email,
            username=user_request.username,
            password_hash=bcrypt_context.hash(user_request.password),
        )

        # Add to database
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        
        # Create token
        token = create_access_token(new_user.username, new_user.id)
        
        # Get user info
        user_info = ReturnUser.from_orm(new_user).dict()
        
        # Encrypt data
        data = encrypt_any_data({"UserInfo": user_info})
        
        return {"access_token": token, "token_type": "bearer", "encrypted_data": data}

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Registration error: {str(e)}")

@router.post("/login", response_model=UserResponse)
async def login(db: db_dependency, user_login: UserLogin):
    """
    Authenticate user and provide access token
    """
    user = authenticate_user(user_login.username, user_login.password, db)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    
    # Create token
    token = create_access_token(user.username, user.id)
    
    # Get user info
    user_info = ReturnUser.from_orm(user).dict()
    
    # Encrypt data
    data = encrypt_any_data({"UserInfo": user_info})
    
    return {"access_token": token, "token_type": "bearer", "encrypted_data": data}

@router.post("/logout")
async def logout(response: Response):
    """
    Logout user - frontend should clear token
    """
    # Since JWTs are stateless, actual logout happens on client side
    # We can set an empty cookie as a signal to frontend
    response.set_cookie(key="access_token", value="", max_age=0)
    return {"message": "Successfully logged out"}

@router.get("/me", response_model=dict)
async def get_user(current_user: user_dependency, db: db_dependency):
    """
    Get current user information
    """
    user = db.query(User).filter(User.id == current_user["user_id"]).first()  # Changed from Users to User
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user_info = ReturnUser.from_orm(user).dict()
    encrypted_data = encrypt_any_data({"UserInfo": user_info})
    
    return {"encrypted_data": encrypted_data}

    
@router.post("/google-register", response_model=UserResponse)
async def google_register(db: db_dependency, google_request: GoogleAuthRequest):
    """
    Register a new user with Google authentication
    """
    try:
        # Verify the Google token
        google_client_id = os.getenv("GOOGLE_CLIENT_ID")
        idinfo = id_token.verify_oauth2_token(
            google_request.token, requests.Request(), google_client_id
        )
        
        # Check if email is verified by Google
        if not idinfo.get("email_verified"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email not verified by Google"
            )
            
        email = idinfo.get("email")
        
        # Check if user with this email already exists
        existing_user = db.query(User).filter(User.email == email).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="User with this email already exists. Please use login instead."
            )
            
        # Create username from email if not provided
        username = email.split("@")[0] + "_google"
        # Check if username exists and modify if needed
        check_username = db.query(User).filter(User.username == username).first()
        if check_username:
            username = f"{username}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
        # Create user model
        new_user = User(
            fname=idinfo.get("given_name", ""),
            lname=idinfo.get("family_name", ""),
            email=email,
            username=username,
            password_hash=bcrypt_context.hash(os.urandom(24).hex()),  # Random secure password
            is_google_account=True  # Add this field to your User model
        )
        
        # Add to database
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        
        # Create token
        token = create_access_token(new_user.username, new_user.id)
        
        # Get user info
        user_info = ReturnUser.from_orm(new_user).dict()
        
        # Encrypt data
        data = encrypt_any_data({"UserInfo": user_info})
        
        return {"access_token": token, "token_type": "bearer", "encrypted_data": data}
        
    except ValueError:
        # Invalid token
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Invalid Google token"
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration error: {str(e)}"
        )

@router.post("/google-login", response_model=UserResponse)
async def google_login(db: db_dependency, google_request: GoogleAuthRequest):
    """
    Login with Google authentication
    """
    try:
        # Verify the Google token
        google_client_id = os.getenv("GOOGLE_CLIENT_ID")
        idinfo = id_token.verify_oauth2_token(
            google_request.token, requests.Request(), google_client_id
        )
        
        # Check if email is verified
        if not idinfo.get("email_verified"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email not verified by Google"
            )
            
        email = idinfo.get("email")
        
        # Find user with this email
        user = db.query(User).filter(User.email == email).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found. Please register first."
            )
            
        # Create token
        token = create_access_token(user.username, user.id)
        
        # Get user info
        user_info = ReturnUser.from_orm(user).dict()
        
        # Encrypt data
        data = encrypt_any_data({"UserInfo": user_info})
        
        return {"access_token": token, "token_type": "bearer", "encrypted_data": data}
        
    except ValueError:
        # Invalid token
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google token"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Login error: {str(e)}"
        )