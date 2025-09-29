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
import random
import string
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from db.connection import db_dependency
from models.users_models import User# Import User class directly
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
# Use bcrypt_sha256 to transparently hash long passwords via SHA-256 prior to bcrypt,
# avoiding bcrypt's 72-byte input limit while remaining compatible.
# Keep 'bcrypt' as a secondary scheme to verify legacy hashes.
bcrypt_context = CryptContext(
    schemes=["bcrypt_sha256", "bcrypt"],
    deprecated="auto",
    bcrypt__truncate_error=False  # do not raise on >72 bytes; bcrypt_sha256 handles prehashing
)
oauth2_bearer = OAuth2PasswordBearer(tokenUrl="login")

class UserResponse(BaseModel):
    access_token: str
    token_type: str
    encrypted_data: str

class GoogleAuthRequest(BaseModel):
    token: str

class UpdateUserRequest(BaseModel):
    fname: Optional[str] = None
    lname: Optional[str] = None
    email: Optional[str] = None
    username: Optional[str] = None
    current_password: Optional[str] = None
    new_password: Optional[str] = None

class ForgotPasswordRequest(BaseModel):
    email: str

class VerifyResetCodeRequest(BaseModel):
    email: str
    reset_code: str

class ResetPasswordRequest(BaseModel):
    email: str
    reset_code: str
    new_password: str

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
    # Verify password; catch backend issues (e.g., bcrypt backend not loaded, length errors)
    try:
        if not bcrypt_context.verify(password, user.password_hash):
            return False
    except ValueError:
        # bcrypt may raise on very long passwords if not using bcrypt_sha256; treat as invalid creds
        return False
    except Exception:
        # Avoid leaking backend errors; treat as invalid credentials
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
        if not google_client_id:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Google authentication not configured"
            )
            
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
        google_client_id = os.getenv("GOOGLE_CLIENT_ID", "969723698837-9aepndmu033gu0bk3gdrb6o1707mknp6.apps.googleusercontent.com")
        
        print(f"🔍 Attempting Google login with client ID: {google_client_id}")
        print(f"🎫 Token received: {google_request.token[:50]}...")
        
        try:
            idinfo = id_token.verify_oauth2_token(
                google_request.token, requests.Request(), google_client_id
            )
            print(f"✅ Token verified successfully: {idinfo}")
        except ValueError as e:
            print(f"❌ Token verification failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid Google token: {str(e)}"
            )
        
        # Check if email is verified
        if not idinfo.get("email_verified", True):  # Default to True if not present
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email not verified by Google"
            )
            
        email = idinfo.get("email")
        if not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No email found in Google token"
            )
        
        print(f"📧 Email from Google: {email}")
        
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

@router.put("/update-profile", response_model=UserResponse)
async def update_user_profile(
    db: db_dependency, 
    current_user: user_dependency, 
    update_request: UpdateUserRequest
):
    """
    Update current user's profile information
    """
    try:
        # Get current user from database
        user = db.query(User).filter(User.id == current_user["user_id"]).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # If updating password, verify current password
        if update_request.new_password:
            if not update_request.current_password:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Current password is required to set new password"
                )
            
            if not bcrypt_context.verify(update_request.current_password, user.password_hash):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Current password is incorrect"
                )
            
            user.password_hash = bcrypt_context.hash(update_request.new_password)
        
        # Check if new username is already taken (if provided)
        if update_request.username and update_request.username != user.username:
            existing_username = db.query(User).filter(
                User.username == update_request.username,
                User.id != user.id
            ).first()
            
            if existing_username:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Username already taken"
                )
            
            user.username = update_request.username
        
        # Check if new email is already taken (if provided)
        if update_request.email and update_request.email != user.email:
            existing_email = db.query(User).filter(
                User.email == update_request.email,
                User.id != user.id
            ).first()
            
            if existing_email:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already taken"
                )
            
            user.email = update_request.email
        
        # Update other fields if provided
        if update_request.fname is not None:
            user.fname = update_request.fname
        
        if update_request.lname is not None:
            user.lname = update_request.lname
        
        # Save changes
        db.commit()
        db.refresh(user)
        
        # Create new token (in case username changed)
        token = create_access_token(user.username, user.id)
        
        # Get updated user info
        user_info = ReturnUser.from_orm(user).dict()
        
        # Encrypt data
        data = encrypt_any_data({"UserInfo": user_info})
        
        return {"access_token": token, "token_type": "bearer", "encrypted_data": data}
        
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Update error: {str(e)}"
        )

@router.delete("/delete-account")
async def delete_user_account(
    db: db_dependency,
    current_user: user_dependency,
    password: str
):
    """
    Delete current user's account (requires password confirmation)
    """
    try:
        # Get current user from database
        user = db.query(User).filter(User.id == current_user["user_id"]).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Verify password for security
        if not bcrypt_context.verify(password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid password"
            )
        
        # Delete user from database
        db.delete(user)
        db.commit()
        
        return {"message": "Account successfully deleted"}
        
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Deletion error: {str(e)}"
        )

# In-memory storage for reset codes (in production, use Redis or database)
reset_codes = {}

def generate_reset_code():
    """Generate a 6-digit reset code"""
    return ''.join(random.choices(string.digits, k=6))

def send_reset_email(email: str, reset_code: str):
    """Send password reset email"""
    try:
        # Email configuration using your real .env credentials
        smtp_server = "smtp.gmail.com"
        smtp_port = 587
        sender_email = os.getenv("BRAININK_SENDER_EMAIL")
        sender_password = os.getenv("BRAININK_PASSWORD")
        
        print(f"🔧 Email Debug Info:")
        print(f"   Sender Email: {sender_email}")
        print(f"   Password Set: {'Yes' if sender_password else 'No'}")
        print(f"   Password Length: {len(sender_password) if sender_password else 0}")
        
        # For testing/development: If credentials not configured properly, just log the code
        if (not sender_email or not sender_password or 
            sender_password in ["your_app_password", "KANA@!@#$"] or
            "@gmail.com" not in sender_email):
            print(f"📧 EMAIL NOT CONFIGURED PROPERLY - RESET CODE FOR {email}: {reset_code}")
            print(f"⚠️  Gmail App Password Setup Required:")
            print(f"   1. Go to Google Account settings")
            print(f"   2. Security → 2-Step Verification → App passwords")
            print(f"   3. Generate app password for 'Mail'")
            print(f"   4. Update BRAININK_PASSWORD in .env with the 16-character app password")
            print(f"🔧 Current config: email={sender_email}, password={'***' if sender_password else 'None'}")
            return True  # Return True for testing purposes
        
        # Create message
        message = MIMEMultipart("alternative")
        message["Subject"] = "BrainInk - Password Reset Code"
        message["From"] = sender_email
        message["To"] = email
        
        # Create HTML content
        html = f"""
        <html>
          <body>
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
              <h2 style="color: #333; text-align: center;">BrainInk Password Reset</h2>
              <p>Hello,</p>
              <p>You requested to reset your password. Use the code below to reset your password:</p>
              
              <div style="background-color: #f4f4f4; padding: 20px; text-align: center; margin: 20px 0;">
                <h1 style="color: #007bff; font-size: 32px; margin: 0; letter-spacing: 3px;">{reset_code}</h1>
              </div>
              
              <p><strong>This code will expire in 15 minutes.</strong></p>
              <p>If you didn't request this reset, please ignore this email.</p>
              
              <p>Best regards,<br>The BrainInk Team</p>
            </div>
          </body>
        </html>
        """
        
        # Convert to MIMEText
        html_part = MIMEText(html, "html")
        message.attach(html_part)
        
        # Send email
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            try:
                server.login(sender_email, sender_password)
                server.sendmail(sender_email, email, message.as_string())
                print(f"✅ Email sent successfully to {email}")
            except smtplib.SMTPAuthenticationError as auth_error:
                print(f"❌ Gmail Authentication Failed: {auth_error}")
                print(f"🔧 Solutions:")
                print(f"   1. Enable 2-Step Verification on your Gmail account")
                print(f"   2. Generate an App Password (not your regular Gmail password)")
                print(f"   3. Use the 16-character app password in BRAININK_PASSWORD")
                print(f"   4. Make sure BRAININK_SENDER_EMAIL is correct: {sender_email}")
                raise Exception("Gmail authentication failed. Please check your App Password.")
            
        return True
    except Exception as e:
        print(f"Failed to send email: {e}")
        return False

@router.post("/forgot-password")
async def forgot_password(db: db_dependency, request: ForgotPasswordRequest):
    """
    Step 1: Request password reset - sends code to email
    """
    try:
        # Check if user exists
        user = db.query(User).filter(User.email == request.email).first()
        
        if not user:
            # Don't reveal if email exists for security
            return {
                "success": True,
                "message": "If this email exists in our system, you will receive a reset code."
            }
        
        # Generate reset code
        reset_code = generate_reset_code()
        
        # Store reset code with expiration (15 minutes)
        reset_codes[request.email] = {
            "code": reset_code,
            "expires_at": datetime.utcnow() + timedelta(minutes=15),
            "attempts": 0
        }
        
        # Send email
        email_sent = send_reset_email(request.email, reset_code)
        
        if not email_sent:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send reset email. Please try again later."
            )
        
        return {
            "success": True,
            "message": "Reset code sent to your email. Check your inbox and spam folder. (For testing: check console logs)",
            "expires_in_minutes": 15
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Password reset error: {str(e)}"
        )

@router.post("/verify-reset-code")
async def verify_reset_code(request: VerifyResetCodeRequest):
    """
    Step 2: Verify the reset code (optional verification step)
    """
    try:
        email = request.email
        code = request.reset_code
        
        # Check if reset code exists
        if email not in reset_codes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No reset request found for this email"
            )
        
        reset_data = reset_codes[email]
        
        # Check if code expired
        if datetime.utcnow() > reset_data["expires_at"]:
            del reset_codes[email]
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Reset code has expired. Please request a new one."
            )
        
        # Check attempts (max 3 attempts)
        if reset_data["attempts"] >= 3:
            del reset_codes[email]
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Too many failed attempts. Please request a new reset code."
            )
        
        # Verify code
        if reset_data["code"] != code:
            reset_codes[email]["attempts"] += 1
            remaining_attempts = 3 - reset_codes[email]["attempts"]
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid reset code. {remaining_attempts} attempts remaining."
            )
        
        return {
            "success": True,
            "message": "Reset code verified successfully. You can now reset your password.",
            "valid": True
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Code verification error: {str(e)}"
        )

@router.post("/reset-password")
async def reset_password(db: db_dependency, request: ResetPasswordRequest):
    """
    Step 3: Reset password with verified code
    """
    try:
        email = request.email
        code = request.reset_code
        new_password = request.new_password
        
        # Validate password strength
        if len(new_password) < 8:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must be at least 8 characters long"
            )
        
        # Check if reset code exists
        if email not in reset_codes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No reset request found for this email"
            )
        
        reset_data = reset_codes[email]
        
        # Check if code expired
        if datetime.utcnow() > reset_data["expires_at"]:
            del reset_codes[email]
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Reset code has expired. Please request a new one."
            )
        
        # Check attempts
        if reset_data["attempts"] >= 3:
            del reset_codes[email]
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Too many failed attempts. Please request a new reset code."
            )
        
        # Verify code
        if reset_data["code"] != code:
            reset_codes[email]["attempts"] += 1
            remaining_attempts = 3 - reset_codes[email]["attempts"]
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid reset code. {remaining_attempts} attempts remaining."
            )
        
        # Find user
        user = db.query(User).filter(User.email == email).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Update password
        user.password_hash = bcrypt_context.hash(new_password)
        db.commit()
        
        # Clean up reset code
        del reset_codes[email]
        
        return {
            "success": True,
            "message": "Password reset successfully. You can now login with your new password."
        }
        
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Password reset error: {str(e)}"
        )

@router.post("/resend-reset-code")
async def resend_reset_code(db: db_dependency, request: ForgotPasswordRequest):
    """
    Resend reset code if user didn't receive it
    """
    try:
        email = request.email
        
        # Check if user exists
        user = db.query(User).filter(User.email == email).first()
        if not user:
            return {
                "success": True,
                "message": "If this email exists in our system, you will receive a reset code."
            }
        
        # Check if there's an existing reset request
        if email in reset_codes:
            # Check if last request was less than 2 minutes ago (rate limiting)
            time_since_last = datetime.utcnow() - (reset_codes[email]["expires_at"] - timedelta(minutes=15))
            if time_since_last < timedelta(minutes=2):
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Please wait 2 minutes before requesting another code."
                )
        
        # Generate new reset code
        reset_code = generate_reset_code()
        
        # Store reset code
        reset_codes[email] = {
            "code": reset_code,
            "expires_at": datetime.utcnow() + timedelta(minutes=15),
            "attempts": 0
        }
        
        # Send email
        email_sent = send_reset_email(email, reset_code)
        
        if not email_sent:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send reset email. Please try again later."
            )
        
        return {
            "success": True,
            "message": "New reset code sent to your email. (For testing: check console logs)",
            "expires_in_minutes": 15
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Resend code error: {str(e)}"
        )

# CORS preflight handler for Google authentication
@router.options("/google-register")
@router.options("/google-login")
async def options_handler():
    return {"message": "OK"}