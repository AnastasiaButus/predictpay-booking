from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from jose import JWTError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    hash_token,
    verify_password,
)
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.user_repository import UserRepository


class AuthService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.users = UserRepository(db)
        self.refresh_token_repo = RefreshTokenRepository(db)

    def register_user(self, email: str, password: str) -> User:
        normalized_email = email.lower()
        if self.users.get_by_email(normalized_email) is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered",
            )

        user = self.users.create_user(
            email=normalized_email,
            hashed_password=get_password_hash(password),
        )
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered",
            ) from exc
        self.db.refresh(user)
        return user

    def authenticate_user(self, email: str, password: str) -> User | None:
        user = self.users.get_by_email(email.lower())
        if user is None:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user

    def login(self, email: str, password: str) -> dict[str, str | int]:
        user = self.authenticate_user(email, password)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Inactive user",
            )

        token_pair = self._create_and_store_token_pair(user)
        self.db.commit()
        return token_pair

    def refresh_tokens(self, refresh_token: str) -> dict[str, str | int]:
        payload = self._decode_refresh_payload(refresh_token)
        user_id = self._extract_user_id(payload)
        token_hash = hash_token(refresh_token)
        token_record = self.refresh_token_repo.get_by_hash(token_hash)

        if not self._is_refresh_record_valid(token_record):
            raise self._invalid_refresh_token_exception()

        user = self.users.get_by_id(user_id)
        if user is None:
            raise self._invalid_refresh_token_exception()
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Inactive user",
            )

        self.refresh_token_repo.revoke(token_record)
        token_pair = self._create_and_store_token_pair(user)
        self.db.commit()
        return token_pair

    def logout(self, current_user_id: int, refresh_token: str) -> dict[str, str]:
        token_hash = hash_token(refresh_token)
        token_record = self.refresh_token_repo.get_by_hash(token_hash)
        if token_record is None or token_record.user_id != current_user_id:
            raise self._invalid_refresh_token_exception()
        if token_record.revoked_at is None:
            self.refresh_token_repo.revoke(token_record)
            self.db.commit()
        return {"message": "Logged out"}

    def _create_and_store_token_pair(self, user: User) -> dict[str, str | int]:
        access_token = create_access_token(user_id=user.id, role=user.role)
        refresh_token = create_refresh_token(user_id=user.id)
        refresh_expires_at = datetime.now(timezone.utc) + timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS
        )
        self.refresh_token_repo.create(
            user_id=user.id,
            token_hash=hash_token(refresh_token),
            expires_at=refresh_expires_at,
        )
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        }

    def _decode_refresh_payload(self, refresh_token: str) -> dict:
        try:
            payload = decode_token(refresh_token)
        except JWTError as exc:
            raise self._invalid_refresh_token_exception() from exc
        if payload.get("type") != "refresh":
            raise self._invalid_refresh_token_exception()
        return payload

    def _extract_user_id(self, payload: dict) -> int:
        try:
            return int(payload["sub"])
        except (KeyError, TypeError, ValueError) as exc:
            raise self._invalid_refresh_token_exception() from exc

    def _is_refresh_record_valid(self, token_record: RefreshToken | None) -> bool:
        if token_record is None or token_record.revoked_at is not None:
            return False
        expires_at = token_record.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        return expires_at > datetime.now(timezone.utc)

    def _invalid_refresh_token_exception(self) -> HTTPException:
        return HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )
