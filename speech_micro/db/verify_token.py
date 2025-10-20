from fastapi import Depends
from typing import Annotated
from endpoints.auth import get_current_user, get_front_current_user

user_dependency = Annotated[dict, Depends(get_current_user)]
user_Front_dependency = Annotated[dict, Depends(get_front_current_user)]