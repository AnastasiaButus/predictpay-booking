from sqlalchemy import select
from sqlalchemy.orm import Session

import app.models  # noqa: F401
from app.models.transaction import Transaction


class TransactionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_transaction(
        self,
        user_id: int,
        amount: int,
        transaction_type: str,
        status: str = "completed",
        reason: str | None = None,
        prediction_id: int | None = None,
        promocode_id: int | None = None,
    ) -> Transaction:
        transaction = Transaction(
            user_id=user_id,
            amount=amount,
            transaction_type=transaction_type,
            status=status,
            reason=reason,
            prediction_id=prediction_id,
            promocode_id=promocode_id,
        )
        self.db.add(transaction)
        self.db.flush()
        return transaction

    def list_by_user(
        self,
        user_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Transaction]:
        return list(
            self.db.scalars(
                select(Transaction)
                .where(Transaction.user_id == user_id)
                .order_by(Transaction.created_at.desc(), Transaction.id.desc())
                .limit(limit)
                .offset(offset)
            )
        )

    def get_by_prediction_and_type(
        self,
        user_id: int,
        prediction_id: int,
        transaction_type: str,
    ) -> Transaction | None:
        return self.db.scalar(
            select(Transaction).where(
                Transaction.user_id == user_id,
                Transaction.prediction_id == prediction_id,
                Transaction.transaction_type == transaction_type,
            )
        )
