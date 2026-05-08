from collections.abc import Generator
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models.prediction  # noqa: F401
import app.models.promocode  # noqa: F401
from app.core.exceptions import BillingConsistencyError, InsufficientCreditsError
from app.models.transaction import Transaction
from app.models.user import User
from app.services.billing_service import BillingService


@pytest.fixture
def db() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    User.__table__.create(bind=engine)
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


def create_user(db: Session, balance: int = 100, reserved_balance: int = 0) -> User:
    user = User(
        email=f"billing-{uuid4().hex}@example.com",
        hashed_password="hashed",
        balance=balance,
        reserved_balance=reserved_balance,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def transactions_for_user(db: Session, user_id: int) -> list[Transaction]:
    return list(
        db.scalars(
            select(Transaction)
            .where(Transaction.user_id == user_id)
            .order_by(Transaction.id)
        )
    )


def test_top_up_increases_balance(db: Session) -> None:
    user = create_user(db, balance=100)

    updated_user = BillingService(db).top_up(user.id, 50)

    assert updated_user.balance == 150
    assert updated_user.reserved_balance == 0


def test_top_up_creates_transaction(db: Session) -> None:
    user = create_user(db)

    BillingService(db).top_up(user.id, 50)

    transaction = transactions_for_user(db, user.id)[0]
    assert transaction.transaction_type == "top_up"
    assert transaction.amount == 50
    assert transaction.reason == "Mock payment top-up"


def test_top_up_rejects_zero_amount(db: Session) -> None:
    user = create_user(db)

    with pytest.raises(ValueError):
        BillingService(db).top_up(user.id, 0)


def test_top_up_rejects_negative_amount(db: Session) -> None:
    user = create_user(db)

    with pytest.raises(ValueError):
        BillingService(db).top_up(user.id, -1)


def test_reserve_credits_success(db: Session) -> None:
    user = create_user(db, balance=100)

    updated_user = BillingService(db).reserve_prediction_credits(user.id, 1, 10)

    assert updated_user.balance == 90
    assert updated_user.reserved_balance == 10


def test_reserve_credits_decreases_balance(db: Session) -> None:
    user = create_user(db, balance=100)

    updated_user = BillingService(db).reserve_prediction_credits(user.id, 1, 25)

    assert updated_user.balance == 75


def test_reserve_credits_increases_reserved_balance(db: Session) -> None:
    user = create_user(db, balance=100, reserved_balance=5)

    updated_user = BillingService(db).reserve_prediction_credits(user.id, 1, 25)

    assert updated_user.reserved_balance == 30


def test_reserve_credits_creates_transaction(db: Session) -> None:
    user = create_user(db, balance=100)

    BillingService(db).reserve_prediction_credits(user.id, 1, 10)

    transaction = transactions_for_user(db, user.id)[0]
    assert transaction.transaction_type == "prediction_reserve"
    assert transaction.amount == -10
    assert transaction.prediction_id == 1


def test_reserve_credits_insufficient_balance_raises_error(db: Session) -> None:
    user = create_user(db, balance=5)

    with pytest.raises(InsufficientCreditsError):
        BillingService(db).reserve_prediction_credits(user.id, 1, 10)


def test_confirm_charge_success(db: Session) -> None:
    user = create_user(db, balance=90, reserved_balance=10)

    updated_user = BillingService(db).confirm_prediction_charge(user.id, 1, 10)

    assert updated_user.reserved_balance == 0


def test_confirm_charge_decreases_reserved_balance(db: Session) -> None:
    user = create_user(db, balance=90, reserved_balance=25)

    updated_user = BillingService(db).confirm_prediction_charge(user.id, 1, 10)

    assert updated_user.reserved_balance == 15


def test_confirm_charge_creates_zero_amount_transaction(db: Session) -> None:
    user = create_user(db, balance=90, reserved_balance=10)

    BillingService(db).confirm_prediction_charge(user.id, 1, 10)

    transaction = transactions_for_user(db, user.id)[0]
    assert transaction.transaction_type == "prediction_charge"
    assert transaction.amount == 0


def test_refund_success(db: Session) -> None:
    user = create_user(db, balance=90, reserved_balance=10)

    updated_user = BillingService(db).refund_prediction_credits(user.id, 1, 10)

    assert updated_user.balance == 100
    assert updated_user.reserved_balance == 0


def test_refund_decreases_reserved_balance(db: Session) -> None:
    user = create_user(db, balance=90, reserved_balance=25)

    updated_user = BillingService(db).refund_prediction_credits(user.id, 1, 10)

    assert updated_user.reserved_balance == 15


def test_refund_increases_balance(db: Session) -> None:
    user = create_user(db, balance=90, reserved_balance=10)

    updated_user = BillingService(db).refund_prediction_credits(user.id, 1, 10)

    assert updated_user.balance == 100


def test_refund_creates_positive_transaction(db: Session) -> None:
    user = create_user(db, balance=90, reserved_balance=10)

    BillingService(db).refund_prediction_credits(user.id, 1, 10)

    transaction = transactions_for_user(db, user.id)[0]
    assert transaction.transaction_type == "prediction_refund"
    assert transaction.amount == 10


def test_refund_without_reserved_balance_fails(db: Session) -> None:
    user = create_user(db, balance=100, reserved_balance=0)

    with pytest.raises(BillingConsistencyError):
        BillingService(db).refund_prediction_credits(user.id, 1, 10)


def test_charge_without_reserved_balance_fails(db: Session) -> None:
    user = create_user(db, balance=100, reserved_balance=0)

    with pytest.raises(BillingConsistencyError):
        BillingService(db).confirm_prediction_charge(user.id, 1, 10)


def test_double_charge_guard(db: Session) -> None:
    user = create_user(db, balance=90, reserved_balance=10)
    service = BillingService(db)

    service.confirm_prediction_charge(user.id, 1, 10)
    service.confirm_prediction_charge(user.id, 1, 10)

    transactions = transactions_for_user(db, user.id)
    assert len(transactions) == 1
    assert transactions[0].transaction_type == "prediction_charge"


def test_double_refund_guard(db: Session) -> None:
    user = create_user(db, balance=90, reserved_balance=10)
    service = BillingService(db)

    service.refund_prediction_credits(user.id, 1, 10)
    service.refund_prediction_credits(user.id, 1, 10)

    transactions = transactions_for_user(db, user.id)
    assert len(transactions) == 1
    assert transactions[0].transaction_type == "prediction_refund"
