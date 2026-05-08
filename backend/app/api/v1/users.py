from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.user import UserMe


router = APIRouter(prefix="/api/v1/users", tags=["users"])


@router.get("/me", response_model=UserMe)
def read_current_user(current_user: User = Depends(get_current_user)) -> User:
    return current_user
