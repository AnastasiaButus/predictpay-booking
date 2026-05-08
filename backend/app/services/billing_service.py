from sqlalchemy.orm import Session

from app.core.exceptions import BillingConsistencyError, InsufficientCreditsError
from app.models.transaction import Transaction
from app.models.user import User
from app.repositories.billing_repository import BillingRepository
from app.repositories.transaction_repository import TransactionRepository


class BillingService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.billing = BillingRepository(db)
        self.transactions = TransactionRepository(db)

    def get_balance(self, user_id: int) -> User:
        user = self.billing.get_user(user_id)
        if user is None:
            raise BillingConsistencyError("User not found")
        return user

    def top_up(self, user_id: int, amount: int) -> User:
        self._validate_positive_amount(amount)
        try:
            user = self._get_locked_user(user_id)
            user.balance += amount
            self.transactions.create_transaction(
                user_id=user.id,
                amount=amount,
                transaction_type="top_up",
                reason="Mock payment top-up",
            )
            self.db.commit()
            self.db.refresh(user)
            return user
        except Exception:
            self.db.rollback()
            raise

    def reserve_prediction_credits(
        self,
        user_id: int,
        prediction_id: int,
        amount: int,
    ) -> User:
        self._validate_positive_amount(amount)
        try:
            user = self._get_locked_user(user_id)
            if user.balance < amount:
                raise InsufficientCreditsError("Insufficient credits")

            user.balance -= amount
            user.reserved_balance += amount
            self.transactions.create_transaction(
                user_id=user.id,
                amount=-amount,
                transaction_type="prediction_reserve",
                prediction_id=prediction_id,
                reason="Reserved credits for prediction",
            )
            self.db.commit()
            self.db.refresh(user)
            return user
        except Exception:
            self.db.rollback()
            raise

    def confirm_prediction_charge(
        self,
        user_id: int,
        prediction_id: int,
        amount: int,
    ) -> User:
        self._validate_positive_amount(amount)
        try:
            user = self._get_locked_user(user_id)
            existing_charge = self.transactions.get_by_prediction_and_type(
                user_id=user.id,
                prediction_id=prediction_id,
                transaction_type="prediction_charge",
            )
            if existing_charge is not None:
                return user

            if user.reserved_balance < amount:
                raise BillingConsistencyError("Reserved balance is too low")

            user.reserved_balance -= amount
            self.transactions.create_transaction(
                user_id=user.id,
                amount=0,
                transaction_type="prediction_charge",
                prediction_id=prediction_id,
                reason="Prediction charge confirmed",
            )
            self.db.commit()
            self.db.refresh(user)
            return user
        except Exception:
            self.db.rollback()
            raise

    def refund_prediction_credits(
        self,
        user_id: int,
        prediction_id: int,
        amount: int,
    ) -> User:
        self._validate_positive_amount(amount)
        try:
            user = self._get_locked_user(user_id)
            existing_refund = self.transactions.get_by_prediction_and_type(
                user_id=user.id,
                prediction_id=prediction_id,
                transaction_type="prediction_refund",
            )
            if existing_refund is not None:
                return user

            if user.reserved_balance < amount:
                raise BillingConsistencyError("Reserved balance is too low")

            user.reserved_balance -= amount
            user.balance += amount
            self.transactions.create_transaction(
                user_id=user.id,
                amount=amount,
                transaction_type="prediction_refund",
                prediction_id=prediction_id,
                reason="Prediction failed, credits refunded",
            )
            self.db.commit()
            self.db.refresh(user)
            return user
        except Exception:
            self.db.rollback()
            raise

    def list_transactions(
        self,
        user_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Transaction]:
        return self.transactions.list_by_user(user_id=user_id, limit=limit, offset=offset)

    def _get_locked_user(self, user_id: int) -> User:
        user = self.billing.get_user_for_update(user_id)
        if user is None:
            raise BillingConsistencyError("User not found")
        return user

    def _validate_positive_amount(self, amount: int) -> None:
        if amount <= 0:
            raise ValueError("Amount must be greater than zero")
