from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.refresh_token import RefreshToken


class RefreshTokenRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        user_id: int,
        token_hash: str,
        expires_at: datetime,
    ) -> RefreshToken:
        token_record = RefreshToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        self.db.add(token_record)
        self.db.flush()
        return token_record

    def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        return self.db.scalar(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )

    def revoke(self, token_record: RefreshToken) -> RefreshToken:
        token_record.revoked_at = datetime.now(timezone.utc)
        self.db.add(token_record)
        self.db.flush()
        return token_record

    def revoke_by_hash(self, token_hash: str) -> RefreshToken | None:
        token_record = self.get_by_hash(token_hash)
        if token_record is None:
            return None
        return self.revoke(token_record)

    def revoke_all_for_user(self, user_id: int) -> None:
        self.db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id)
            .where(RefreshToken.revoked_at.is_(None))
            .values(revoked_at=datetime.now(timezone.utc))
        )
