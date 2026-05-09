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
    InsufficientCreditsError,
    InvalidFeaturePayloadError,
    ModelNotFoundError,
    PredictionNotFoundError,
)
from app.db.base_class import Base
from app.ml.features import FEATURE_COLUMNS
from app.models.ml_model import MLModel
from app.models.prediction import Prediction
from app.models.transaction import Transaction
from app.models.user import User
from app.services.prediction_service import (
    PREDICTION_COST_CREDITS,
    PredictionService,
)


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


class MissingModelPredictor:
    def __init__(self, model_path: str) -> None:
        raise ModelNotFoundError("Model artifact not found")


class FailingPredictor:
    def __init__(self, model_path: str) -> None:
        self.model_path = model_path

    def predict_one(self, features: dict) -> dict:
        raise InvalidFeaturePayloadError("Invalid features")


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


def create_user(db: Session, balance: int = 100) -> User:
    user = User(
        email=f"prediction-{uuid4().hex}@example.com",
        hashed_password="hashed",
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


def transactions_for_prediction(db: Session, prediction_id: int) -> list[Transaction]:
    return list(
        db.scalars(
            select(Transaction)
            .where(Transaction.prediction_id == prediction_id)
            .order_by(Transaction.id)
        )
    )


def test_create_prediction_success_creates_record(db: Session) -> None:
    user = create_user(db)
    create_model_metadata(db)

    prediction = PredictionService(db, predictor_factory=FakePredictor).create_prediction_sync(
        user.id,
        valid_features(),
    )

    assert prediction.id is not None
    assert prediction.status == "completed"


def test_create_prediction_success_reserves_and_charges_credits(db: Session) -> None:
    user = create_user(db, balance=100)
    create_model_metadata(db)

    prediction = PredictionService(db, predictor_factory=FakePredictor).create_prediction_sync(
        user.id,
        valid_features(),
    )
    db.refresh(user)

    assert user.balance == 90
    assert user.reserved_balance == 0
    transaction_types = [
        transaction.transaction_type
        for transaction in transactions_for_prediction(db, prediction.id)
    ]
    assert transaction_types == ["prediction_reserve", "prediction_charge"]


def test_create_prediction_success_stores_result(db: Session) -> None:
    user = create_user(db)
    create_model_metadata(db)

    prediction = PredictionService(db, predictor_factory=FakePredictor).create_prediction_sync(
        user.id,
        valid_features(),
    )

    assert prediction.result["prediction"] == 1
    assert prediction.result["cancellation_probability"] == 0.82
    assert prediction.result["risk_label"] == "high"


def test_create_prediction_insufficient_credits_raises(db: Session) -> None:
    user = create_user(db, balance=5)
    create_model_metadata(db)

    with pytest.raises(InsufficientCreditsError):
        PredictionService(db, predictor_factory=FakePredictor).create_prediction_sync(
            user.id,
            valid_features(),
        )


def test_create_prediction_model_missing_refunds_if_reserved(db: Session) -> None:
    user = create_user(db, balance=100)
    create_model_metadata(db)
    service = PredictionService(db, predictor_factory=MissingModelPredictor)

    with pytest.raises(ModelNotFoundError):
        service.create_prediction_sync(user.id, valid_features())

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


def test_create_prediction_predictor_error_refunds(db: Session) -> None:
    user = create_user(db, balance=100)
    create_model_metadata(db)
    service = PredictionService(db, predictor_factory=FailingPredictor)

    with pytest.raises(InvalidFeaturePayloadError):
        service.create_prediction_sync(user.id, valid_features())

    db.refresh(user)
    prediction = db.scalar(select(Prediction).where(Prediction.user_id == user.id))
    assert prediction.status == "failed"
    assert "Invalid features" in prediction.error_message
    assert user.balance == 100
    assert user.reserved_balance == 0


def test_get_prediction_only_owner(db: Session) -> None:
    owner = create_user(db)
    other_user = create_user(db)
    create_model_metadata(db)
    service = PredictionService(db, predictor_factory=FakePredictor)
    prediction = service.create_prediction_sync(owner.id, valid_features())

    assert service.get_prediction(owner.id, prediction.id).id == prediction.id
    with pytest.raises(PredictionNotFoundError):
        service.get_prediction(other_user.id, prediction.id)


def test_list_predictions_only_current_user(db: Session) -> None:
    first_user = create_user(db)
    second_user = create_user(db)
    create_model_metadata(db)
    service = PredictionService(db, predictor_factory=FakePredictor)
    first_prediction = service.create_prediction_sync(first_user.id, valid_features())
    service.create_prediction_sync(second_user.id, valid_features())

    predictions = service.list_predictions(first_user.id)

    assert [prediction.id for prediction in predictions] == [first_prediction.id]


def test_prediction_cost_is_10_credits(db: Session) -> None:
    user = create_user(db)
    create_model_metadata(db)

    prediction = PredictionService(db, predictor_factory=FakePredictor).create_prediction_sync(
        user.id,
        valid_features(),
    )

    assert PREDICTION_COST_CREDITS == 10
    assert prediction.cost == 10
