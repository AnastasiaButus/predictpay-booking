from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models.prediction  # noqa: F401
from app.core.exceptions import (
    InvalidChallengeSubmissionError,
    PromocodeActivationLimitError,
    PromocodeAlreadyActivatedError,
    PromocodeExpiredError,
    PromocodeInactiveError,
    PromocodeNotFoundError,
)
from app.models.promocode import Promocode
from app.models.promocode_activation import PromocodeActivation
from app.models.transaction import Transaction
from app.models.user import User
from app.services.promocode_service import PromocodeService


@pytest.fixture
def db() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    User.__table__.create(bind=engine)
    Promocode.__table__.create(bind=engine)
    PromocodeActivation.__table__.create(bind=engine)
    Transaction.__table__.create(bind=engine)
    testing_session_local = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    session = testing_session_local()
    try:
        yield session
    finally:
        session.close()


def create_user(db: Session, balance: int = 100) -> User:
    user = User(
        email=f"promo-{uuid4().hex}@example.com",
        hashed_password="hashed",
        balance=balance,
        reserved_balance=0,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_promocode(
    db: Session,
    code: str = "WELCOME100",
    credits_amount: int = 100,
    is_active: bool = True,
    max_activations: int = 100000,
    current_activations: int = 0,
    expires_at: datetime | None = None,
) -> Promocode:
    promocode = Promocode(
        code=code,
        credits_amount=credits_amount,
        max_activations=max_activations,
        current_activations=current_activations,
        is_active=is_active,
        expires_at=expires_at,
        description=f"{code} description",
    )
    db.add(promocode)
    db.commit()
    db.refresh(promocode)
    return promocode


def transactions_for_user(db: Session, user_id: int) -> list[Transaction]:
    return list(db.scalars(select(Transaction).where(Transaction.user_id == user_id)))


def activations_for_user(db: Session, user_id: int) -> list[PromocodeActivation]:
    return list(
        db.scalars(
            select(PromocodeActivation).where(PromocodeActivation.user_id == user_id)
        )
    )


def test_activate_welcome_promocode_success(db: Session) -> None:
    user = create_user(db)
    create_promocode(db, code="WELCOME100")

    result = PromocodeService(db).activate_promocode(user.id, "welcome100")

    assert result["code"] == "WELCOME100"
    assert result["credits_amount"] == 100
    assert result["balance"] == 200


def test_activate_promocode_increases_balance(db: Session) -> None:
    user = create_user(db, balance=100)
    create_promocode(db, credits_amount=50)

    PromocodeService(db).activate_promocode(user.id, "WELCOME100")
    db.refresh(user)

    assert user.balance == 150


def test_activate_promocode_creates_promo_bonus_transaction(db: Session) -> None:
    user = create_user(db)
    promocode = create_promocode(db)

    PromocodeService(db).activate_promocode(user.id, promocode.code)

    transaction = transactions_for_user(db, user.id)[0]
    assert transaction.transaction_type == "promo_bonus"
    assert transaction.amount == 100
    assert transaction.promocode_id == promocode.id


def test_activate_promocode_creates_activation(db: Session) -> None:
    user = create_user(db)
    promocode = create_promocode(db)

    PromocodeService(db).activate_promocode(user.id, promocode.code)

    activation = activations_for_user(db, user.id)[0]
    assert activation.promocode_id == promocode.id


def test_activate_promocode_increments_current_activations(db: Session) -> None:
    user = create_user(db)
    promocode = create_promocode(db, current_activations=2)

    PromocodeService(db).activate_promocode(user.id, promocode.code)
    db.refresh(promocode)

    assert promocode.current_activations == 3


def test_duplicate_activation_blocked(db: Session) -> None:
    user = create_user(db)
    promocode = create_promocode(db)
    service = PromocodeService(db)
    service.activate_promocode(user.id, promocode.code)

    with pytest.raises(PromocodeAlreadyActivatedError):
        service.activate_promocode(user.id, promocode.code)


def test_inactive_promocode_blocked(db: Session) -> None:
    user = create_user(db)
    create_promocode(db, is_active=False)

    with pytest.raises(PromocodeInactiveError):
        PromocodeService(db).activate_promocode(user.id, "WELCOME100")


def test_expired_promocode_blocked(db: Session) -> None:
    user = create_user(db)
    create_promocode(db, expires_at=datetime.now(timezone.utc) - timedelta(days=1))

    with pytest.raises(PromocodeExpiredError):
        PromocodeService(db).activate_promocode(user.id, "WELCOME100")


def test_activation_limit_blocked(db: Session) -> None:
    user = create_user(db)
    create_promocode(db, max_activations=1, current_activations=1)

    with pytest.raises(PromocodeActivationLimitError):
        PromocodeService(db).activate_promocode(user.id, "WELCOME100")


def test_unknown_promocode_blocked(db: Session) -> None:
    user = create_user(db)

    with pytest.raises(PromocodeNotFoundError):
        PromocodeService(db).activate_promocode(user.id, "UNKNOWN")


def test_poincare_challenge_success_with_valid_url(db: Session) -> None:
    user = create_user(db)
    create_promocode(db, code="POINCARE_CHALLENGE", credits_amount=1000)

    result = PromocodeService(db).activate_poincare_challenge(
        user.id,
        "https://example.com/poincare-proof",
    )

    assert result["code"] == "POINCARE_CHALLENGE"
    assert result["balance"] == 1100


def test_poincare_challenge_invalid_url_blocked(db: Session) -> None:
    user = create_user(db)
    create_promocode(db, code="POINCARE_CHALLENGE", credits_amount=1000)

    with pytest.raises(InvalidChallengeSubmissionError):
        PromocodeService(db).activate_poincare_challenge(user.id, "not-a-url")


def test_poincare_challenge_message_mentions_url_only_mvp(db: Session) -> None:
    user = create_user(db)
    create_promocode(db, code="POINCARE_CHALLENGE", credits_amount=1000)

    result = PromocodeService(db).activate_poincare_challenge(
        user.id,
        "https://example.com/poincare-proof",
    )

    assert "URL format only" in result["message"]
    assert "mathematical correctness is not verified" in result["message"]
