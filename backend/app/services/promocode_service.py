from datetime import datetime, timezone
from typing import Any

from pydantic import AnyUrl, TypeAdapter, ValidationError
from sqlalchemy.orm import Session

from app.core.exceptions import (
    BillingConsistencyError,
    InvalidChallengeSubmissionError,
    PromocodeActivationLimitError,
    PromocodeAlreadyActivatedError,
    PromocodeExpiredError,
    PromocodeInactiveError,
    PromocodeNotFoundError,
)
from app.models.promocode import Promocode
from app.repositories.billing_repository import BillingRepository
from app.repositories.promocode_repository import PromocodeRepository
from app.repositories.transaction_repository import TransactionRepository


POINCARE_CHALLENGE_CODE = "POINCARE_CHALLENGE"
POINCARE_CHALLENGE_WORDING_RU = (
    "Всякое замкнутое односвязное трёхмерное многообразие "
    "гомеоморфно трёхмерной сфере."
)
POINCARE_CHALLENGE_WORDING_EN = (
    "Every simply connected, closed 3-manifold is homeomorphic to the 3-sphere."
)
POINCARE_CHALLENGE_MVP_MESSAGE = (
    "MVP validates URL format only; mathematical correctness is not verified."
)


class PromocodeService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.billing = BillingRepository(db)
        self.promocodes = PromocodeRepository(db)
        self.transactions = TransactionRepository(db)

    def activate_promocode(self, user_id: int, code: str) -> dict[str, Any]:
        normalized_code = self._normalize_code(code)
        return self._activate(
            user_id=user_id,
            code=normalized_code,
            reason=f"Promocode activated: {normalized_code}",
            message=f"Promocode activated: {normalized_code}",
        )

    def activate_poincare_challenge(
        self,
        user_id: int,
        proof_url: str,
    ) -> dict[str, Any]:
        self._validate_proof_url(proof_url)
        return self._activate(
            user_id=user_id,
            code=POINCARE_CHALLENGE_CODE,
            reason="Poincaré challenge bonus activated",
            message=POINCARE_CHALLENGE_MVP_MESSAGE,
        )

    def list_promocodes(self) -> list[Promocode]:
        now = datetime.now(timezone.utc)
        return [
            promocode
            for promocode in self.promocodes.list_active_promocodes()
            if self._is_not_expired(promocode, now)
        ]

    def _activate(
        self,
        user_id: int,
        code: str,
        reason: str,
        message: str,
    ) -> dict[str, Any]:
        try:
            user = self.billing.get_user_for_update(user_id)
            if user is None:
                raise BillingConsistencyError("User not found")

            promocode = self.promocodes.get_by_code_for_update(code)
            self._validate_promocode(promocode)
            assert promocode is not None

            existing_activation = self.promocodes.get_activation(
                user_id=user.id,
                promocode_id=promocode.id,
            )
            if existing_activation is not None:
                raise PromocodeAlreadyActivatedError("Promocode already activated")

            user.balance += promocode.credits_amount
            self.promocodes.increment_current_activations(promocode)
            self.promocodes.create_activation(
                user_id=user.id,
                promocode_id=promocode.id,
            )
            self.transactions.create_transaction(
                user_id=user.id,
                amount=promocode.credits_amount,
                transaction_type="promo_bonus",
                promocode_id=promocode.id,
                reason=reason,
            )
            self.db.commit()
            self.db.refresh(user)

            return {
                "code": promocode.code,
                "credits_amount": promocode.credits_amount,
                "balance": user.balance,
                "reserved_balance": user.reserved_balance,
                "message": message,
            }
        except Exception:
            self.db.rollback()
            raise

    def _validate_promocode(self, promocode: Promocode | None) -> None:
        if promocode is None:
            raise PromocodeNotFoundError("Promocode not found")
        if not promocode.is_active:
            raise PromocodeInactiveError("Promocode is inactive")
        if not self._is_not_expired(promocode, datetime.now(timezone.utc)):
            raise PromocodeExpiredError("Promocode is expired")
        if promocode.current_activations >= promocode.max_activations:
            raise PromocodeActivationLimitError("Promocode activation limit reached")

    def _is_not_expired(self, promocode: Promocode, now: datetime) -> bool:
        if promocode.expires_at is None:
            return True
        expires_at = promocode.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        return expires_at > now

    def _normalize_code(self, code: str) -> str:
        return code.strip().upper()

    def _validate_proof_url(self, proof_url: str) -> None:
        try:
            TypeAdapter(AnyUrl).validate_python(proof_url)
        except ValidationError as exc:
            raise InvalidChallengeSubmissionError("Invalid proof URL") from exc
