from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, LogoutRequest
from app.schemas.token import RefreshTokenRequest, TokenPair
from app.schemas.user import UserCreate, UserRead
from app.services.auth_service import AuthService


router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Session = Depends(get_db)) -> User:
    return AuthService(db).register_user(
        email=str(payload.email),
        password=payload.password,
    )


@router.post("/login", response_model=TokenPair)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> dict[str, str | int]:
    return AuthService(db).login(email=str(payload.email), password=payload.password)


@router.post("/refresh", response_model=TokenPair)
def refresh(
    payload: RefreshTokenRequest,
    db: Session = Depends(get_db),
) -> dict[str, str | int]:
    return AuthService(db).refresh_tokens(refresh_token=payload.refresh_token)


@router.post("/logout")
def logout(
    payload: LogoutRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    return AuthService(db).logout(
        current_user_id=current_user.id,
        refresh_token=payload.refresh_token,
    )
