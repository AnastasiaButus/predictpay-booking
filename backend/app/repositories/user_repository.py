from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.user import User


class UserRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, user_id: int) -> User | None:
        return self.db.scalar(select(User).where(User.id == user_id))

    def get_by_email(self, email: str) -> User | None:
        return self.db.scalar(select(User).where(User.email == email))

    def create_user(
        self,
        email: str,
        hashed_password: str,
        role: str = "user",
        plan: str = "free",
        balance: int = settings.START_BALANCE,
    ) -> User:
        user = User(
            email=email,
            hashed_password=hashed_password,
            role=role,
            plan=plan,
            balance=balance,
        )
        self.db.add(user)
        self.db.flush()
        return user
