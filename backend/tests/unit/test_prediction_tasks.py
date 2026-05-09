from collections.abc import Generator
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.db.base_class import Base
from app.ml.features import FEATURE_COLUMNS
from app.models.ml_model import MLModel
from app.models.prediction import Prediction
from app.models.transaction import Transaction
from app.models.user import User
from app.workers import prediction_tasks


@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw) -> str:
    return "JSON"


class FakePredictor:
    def __init__(self, model_path: str) -> None:
        self.model_path = model_path

    def predict_one(self, features: dict) -> dict:
        return {
            "prediction": 1,
            "cancellation_probability": 0.82,
            "risk_label": "high",
            "model_name": "hotel_cancellation_model",
            "model_version": "1.0.0",
            "features_used": FEATURE_COLUMNS,
        }


class FailingPredictor:
    def __init__(self, model_path: str) -> None:
        self.model_path = model_path

    def predict_one(self, features: dict) -> dict:
        raise RuntimeError("Predictor failed")


class MissingModelPredictor:
    def __init__(self, model_path: str) -> None:
        raise FileNotFoundError("Model artifact missing")


@pytest.fixture
def db(
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[Session, None, None]:
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
    monkeypatch.setattr(prediction_tasks, "SessionLocal", testing_session_local)
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


def create_user(db: Session, balance: int = 90, reserved_balance: int = 10) -> User:
    user = User(
        email=f"task-{uuid4().hex}@example.com",
        hashed_password="hashed",
        balance=balance,
        reserved_balance=reserved_balance,
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


def create_prediction(
    db: Session,
    user: User,
    model: MLModel,
    status: str = "pending",
) -> Prediction:
    prediction = Prediction(
        user_id=user.id,
        model_id=model.id,
        status=status,
        input_data=valid_features(),
        result={"prediction": 1} if status == "completed" else None,
        error_message="already failed" if status == "failed" else None,
        cost=10,
    )
    db.add(prediction)
    db.commit()
    db.refresh(prediction)
    return prediction


def transactions_for_prediction(db: Session, prediction_id: int) -> list[Transaction]:
    return list(
        db.scalars(
            select(Transaction)
            .where(Transaction.prediction_id == prediction_id)
            .order_by(Transaction.id)
        )
    )


def test_process_prediction_task_success_completes_prediction(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(prediction_tasks, "HotelCancellationPredictor", FakePredictor)
    user = create_user(db)
    model = create_model_metadata(db)
    prediction = create_prediction(db, user, model)

    result = prediction_tasks.process_prediction_task.run(prediction.id)
    db.refresh(prediction)

    assert result["status"] == "completed"
    assert prediction.status == "completed"
    assert prediction.result["prediction"] == 1


def test_process_prediction_task_success_confirms_charge(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(prediction_tasks, "HotelCancellationPredictor", FakePredictor)
    user = create_user(db, balance=90, reserved_balance=10)
    model = create_model_metadata(db)
    prediction = create_prediction(db, user, model)

    prediction_tasks.process_prediction_task.run(prediction.id)
    db.refresh(user)

    assert user.balance == 90
    assert user.reserved_balance == 0
    transaction = transactions_for_prediction(db, prediction.id)[0]
    assert transaction.transaction_type == "prediction_charge"
    assert transaction.amount == 0


def test_process_prediction_task_predictor_error_marks_failed(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(prediction_tasks, "HotelCancellationPredictor", FailingPredictor)
    user = create_user(db)
    model = create_model_metadata(db)
    prediction = create_prediction(db, user, model)

    result = prediction_tasks.process_prediction_task.run(prediction.id)
    db.refresh(prediction)

    assert result["status"] == "failed"
    assert prediction.status == "failed"
    assert "Predictor failed" in prediction.error_message


def test_process_prediction_task_predictor_error_refunds(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(prediction_tasks, "HotelCancellationPredictor", FailingPredictor)
    user = create_user(db, balance=90, reserved_balance=10)
    model = create_model_metadata(db)
    prediction = create_prediction(db, user, model)

    prediction_tasks.process_prediction_task.run(prediction.id)
    db.refresh(user)

    assert user.balance == 100
    assert user.reserved_balance == 0
    transaction = transactions_for_prediction(db, prediction.id)[0]
    assert transaction.transaction_type == "prediction_refund"
    assert transaction.amount == 10


def test_process_prediction_task_idempotent_if_already_completed(db: Session) -> None:
    user = create_user(db, balance=90, reserved_balance=0)
    model = create_model_metadata(db)
    prediction = create_prediction(db, user, model, status="completed")

    result = prediction_tasks.process_prediction_task.run(prediction.id)

    assert result == {
        "prediction_id": prediction.id,
        "status": "completed",
        "idempotent": True,
    }
    assert transactions_for_prediction(db, prediction.id) == []


def test_process_prediction_task_idempotent_if_already_failed(db: Session) -> None:
    user = create_user(db, balance=100, reserved_balance=0)
    model = create_model_metadata(db)
    prediction = create_prediction(db, user, model, status="failed")

    result = prediction_tasks.process_prediction_task.run(prediction.id)

    assert result == {
        "prediction_id": prediction.id,
        "status": "failed",
        "idempotent": True,
    }
    assert transactions_for_prediction(db, prediction.id) == []


def test_process_prediction_task_model_missing_refunds(db: Session) -> None:
    user = create_user(db, balance=90, reserved_balance=10)
    model = create_model_metadata(db)
    prediction = create_prediction(db, user, model)
    model.is_active = False
    db.commit()

    result = prediction_tasks.process_prediction_task.run(prediction.id)
    db.refresh(user)
    db.refresh(prediction)

    assert result["status"] == "failed"
    assert "Active model metadata is not seeded" in prediction.error_message
    assert user.balance == 100
    assert user.reserved_balance == 0
