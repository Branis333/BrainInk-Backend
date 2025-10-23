from fastapi import APIRouter, HTTPException, Depends
from starlette import status
from typing import Annotated
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

router = APIRouter(prefix="/auth", tags=["Authentication"])

# load env values
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")

oauth2_bearer = OAuth2PasswordBearer(tokenUrl="auth/token")

async def get_current_user(token: Annotated[str, Depends(oauth2_bearer)]):
    try:
        playload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = playload.get("uname")
        acc_type: str = playload.get("acc_type")
        user_id: str = playload.get("id")
        if username is None or user_id is None or acc_type is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required!",
            )
        return {"username": username, "user_id": user_id, "acc_type": acc_type}
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed. Your token is invalid or has expired. Please re-authenticate.",
        )

async def get_front_current_user(token: Annotated[str, Depends(oauth2_bearer)]):
    try:
        playload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = playload.get("uname")
        acc_type: str = playload.get("acc_type")
        user_id: str = playload.get("id")
        if username is None or user_id is None or acc_type is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required!",
            )
        return {"username": username, "user_id": user_id, "acc_type": acc_type}
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed. Your token is invalid or has expired. Please re-authenticate.",
        )
#         return {"username": username, "user_id": user_id, "acc_type": acc_type}
#     except JWTError:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Authentication failed. Your token is invalid or has expired. Please re-authenticate.",
#         )

# async def get_front_current_user(token: Annotated[str, Depends(oauth2_bearer)]):
#     try:
#         playload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
#         username: str = playload.get("uname")
#         acc_type: str = playload.get("acc_type")
#         user_id: str = playload.get("id")
#         if username is None or user_id is None or acc_type is None:
#             raise HTTPException(
#                 status_code=status.HTTP_401_UNAUTHORIZED,
#                 detail="Authentication required!",
#             )
#         return {"username": username, "user_id": user_id, "acc_type": acc_type}
#     except JWTError:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Authentication failed. Your token is invalid or has expired. Please re-authenticate.",
#         )

# # Dependencies for easy use
# user_dependency = Annotated[dict, Depends(get_current_user)]
# user_Front_dependency = Annotated[dict, Depends(get_front_current_user)]