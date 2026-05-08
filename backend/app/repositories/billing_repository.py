from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User


class BillingRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_user_for_update(self, user_id: int) -> User | None:
        return self.db.scalar(
            select(User).where(User.id == user_id).with_for_update()
        )

    def get_user(self, user_id: int) -> User | None:
        return self.db.scalar(select(User).where(User.id == user_id))
