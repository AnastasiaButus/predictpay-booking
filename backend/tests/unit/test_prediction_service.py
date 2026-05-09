from collections.abc import Generator
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.core.exceptions import (
    ActivePredictionLimitError,
    InsufficientCreditsError,
    PredictionEnqueueError,
)
from app.db.base_class import Base
from app.ml.features import FEATURE_COLUMNS
from app.models.ml_model import MLModel
from app.models.prediction import Prediction
from app.models.transaction import Transaction
from app.models.user import User
from app.services.prediction_service import PredictionService


@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw) -> str:
    return "JSON"


class FakeAsyncResult:
    def __init__(self, task_id: str = "fake-task-id") -> None:
        self.id = task_id


class CapturingTaskSender:
    def __init__(self) -> None:
        self.calls: list[tuple[int, str]] = []

    def __call__(self, prediction_id: int, queue: str) -> FakeAsyncResult:
        self.calls.append((prediction_id, queue))
        return FakeAsyncResult(f"task-{prediction_id}-{queue}")


class FailingTaskSender:
    def __call__(self, prediction_id: int, queue: str) -> FakeAsyncResult:
        raise RuntimeError("Redis unavailable")


@pytest.fixture
def db() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
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


def valid_features() -> dict:
    return {
        "hotel": "City Hotel",
        "lead_time": 120,
        "adults": 2,
        "children": 0,
        "previous_cancellations": 1,
        "booking_changes": 0,
        "deposit_type": "No Deposit",
        "customer_type": "Transient",
        "market_segment": "Online TA",
        "required_car_parking_spaces": 0,
        "total_of_special_requests": 1,
        "adr": 95.5,
    }


def create_user(
    db: Session,
    balance: int = 100,
    role: str = "user",
    plan: str = "free",
) -> User:
    user = User(
        email=f"prediction-{uuid4().hex}@example.com",
        hashed_password="hashed",
        role=role,
        plan=plan,
        balance=balance,
        reserved_balance=0,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_model_metadata(db: Session) -> MLModel:
    model = MLModel(
        name="hotel_cancellation_model",
        version="1.0.0",
        file_path="storage/models/hotel_cancellation_model.joblib",
        model_type="sklearn_pipeline",
        input_schema={
            "features": FEATURE_COLUMNS,
            "target": "is_canceled",
            "leakage_excluded": [
                "reservation_status",
                "reservation_status_date",
            ],
        },
        is_active=True,
    )
    db.add(model)
    db.commit()
    db.refresh(model)
    return model


def create_prediction_with_status(
    db: Session,
    user: User,
    model: MLModel,
    status: str,
) -> Prediction:
    prediction = Prediction(
        user_id=user.id,
        model_id=model.id,
        status=status,
        input_data=valid_features(),
        cost=10,
    )
    db.add(prediction)
    db.commit()
    db.refresh(prediction)
    return prediction


def create_pending_prediction(db: Session, user: User, model: MLModel) -> Prediction:
    return create_prediction_with_status(db, user, model, "pending")


def transactions_for_prediction(db: Session, prediction_id: int) -> list[Transaction]:
    return list(
        db.scalars(
            select(Transaction)
            .where(Transaction.prediction_id == prediction_id)
            .order_by(Transaction.id)
        )
    )


def test_create_prediction_async_creates_pending_record(db: Session) -> None:
    user = create_user(db)
    create_model_metadata(db)

    prediction = PredictionService(
        db,
        task_sender=CapturingTaskSender(),
    ).create_prediction_async(user.id, valid_features())

    assert prediction.status == "pending"
    assert prediction.result is None
    assert prediction.celery_task_id.startswith("task-")


def test_create_prediction_async_reserves_credits(db: Session) -> None:
    user = create_user(db, balance=100)
    create_model_metadata(db)

    prediction = PredictionService(
        db,
        task_sender=CapturingTaskSender(),
    ).create_prediction_async(user.id, valid_features())
    db.refresh(user)

    assert user.balance == 90
    assert user.reserved_balance == 10
    transaction = transactions_for_prediction(db, prediction.id)[0]
    assert transaction.transaction_type == "prediction_reserve"
    assert transaction.amount == -10


def test_create_prediction_async_enqueues_task(db: Session) -> None:
    user = create_user(db)
    create_model_metadata(db)
    sender = CapturingTaskSender()

    prediction = PredictionService(db, task_sender=sender).create_prediction_async(
        user.id,
        valid_features(),
    )

    assert sender.calls == [(prediction.id, "default")]


def test_create_prediction_async_does_not_call_predictor(db: Session) -> None:
    user = create_user(db)
    create_model_metadata(db)

    prediction = PredictionService(
        db,
        task_sender=CapturingTaskSender(),
    ).create_prediction_async(user.id, valid_features())

    assert prediction.status == "pending"
    assert prediction.result is None
    assert prediction.completed_at is None


def test_create_prediction_async_insufficient_credits_raises(db: Session) -> None:
    user = create_user(db, balance=5)
    create_model_metadata(db)

    with pytest.raises(InsufficientCreditsError):
        PredictionService(db, task_sender=CapturingTaskSender()).create_prediction_async(
            user.id,
            valid_features(),
        )

    assert db.scalar(select(Prediction).where(Prediction.user_id == user.id)) is None


def test_create_prediction_async_enqueue_failure_refunds(db: Session) -> None:
    user = create_user(db, balance=100)
    create_model_metadata(db)

    with pytest.raises(PredictionEnqueueError):
        PredictionService(db, task_sender=FailingTaskSender()).create_prediction_async(
            user.id,
            valid_features(),
        )

    db.refresh(user)
    prediction = db.scalar(select(Prediction).where(Prediction.user_id == user.id))
    assert prediction.status == "failed"
    assert user.balance == 100
    assert user.reserved_balance == 0
    transaction_types = [
        transaction.transaction_type
        for transaction in transactions_for_prediction(db, prediction.id)
    ]
    assert transaction_types == ["prediction_reserve", "prediction_refund"]


def test_free_active_prediction_limit(db: Session) -> None:
    user = create_user(db, plan="free")
    model = create_model_metadata(db)
    for _ in range(3):
        create_pending_prediction(db, user, model)
    sender = CapturingTaskSender()

    with pytest.raises(ActivePredictionLimitError):
        PredictionService(db, task_sender=sender).create_prediction_async(
            user.id,
            valid_features(),
        )

    db.refresh(user)
    predictions = list(db.scalars(select(Prediction).where(Prediction.user_id == user.id)))
    transactions = list(db.scalars(select(Transaction).where(Transaction.user_id == user.id)))
    assert len(predictions) == 3
    assert transactions == []
    assert user.balance == 100
    assert user.reserved_balance == 0
    assert sender.calls == []


def test_pro_active_prediction_limit(db: Session) -> None:
    user = create_user(db, plan="pro")
    model = create_model_metadata(db)
    for _ in range(9):
        create_pending_prediction(db, user, model)

    PredictionService(db, task_sender=CapturingTaskSender()).create_prediction_async(
        user.id,
        valid_features(),
    )
    with pytest.raises(ActivePredictionLimitError):
        PredictionService(db, task_sender=CapturingTaskSender()).create_prediction_async(
            user.id,
            valid_features(),
        )


def test_completed_and_failed_predictions_do_not_count_toward_active_limit(
    db: Session,
) -> None:
    user = create_user(db, plan="free")
    model = create_model_metadata(db)
    for status in ("completed", "failed", "completed"):
        create_prediction_with_status(db, user, model, status)

    prediction = PredictionService(
        db,
        task_sender=CapturingTaskSender(),
    ).create_prediction_async(user.id, valid_features())

    assert prediction.status == "pending"


def test_queue_selection_free_default(db: Session) -> None:
    user = create_user(db, plan="free")
    create_model_metadata(db)
    sender = CapturingTaskSender()

    PredictionService(db, task_sender=sender).create_prediction_async(
        user.id,
        valid_features(),
    )

    assert sender.calls[0][1] == "default"


def test_queue_selection_pro_priority(db: Session) -> None:
    user = create_user(db, plan="pro")
    create_model_metadata(db)
    sender = CapturingTaskSender()

    PredictionService(db, task_sender=sender).create_prediction_async(
        user.id,
        valid_features(),
    )

    assert sender.calls[0][1] == "priority"


def test_queue_selection_admin_priority(db: Session) -> None:
    user = create_user(db, role="admin")
    create_model_metadata(db)
    sender = CapturingTaskSender()

    PredictionService(db, task_sender=sender).create_prediction_async(
        user.id,
        valid_features(),
    )

    assert sender.calls[0][1] == "priority"
