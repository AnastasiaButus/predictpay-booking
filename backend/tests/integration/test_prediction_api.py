from collections.abc import Generator
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.api.v1.predictions as predictions_api
import app.models  # noqa: F401
from app.api.deps import get_db
from app.db.base_class import Base
from app.ml.features import FEATURE_COLUMNS
from app.models.ml_model import MLModel
from app.models.user import User
from app.services.prediction_service import PredictionService


@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw) -> str:
    return "JSON"


class FakeAsyncResult:
    def __init__(self, task_id: str) -> None:
        self.id = task_id


class FakePredictionService(PredictionService):
    def __init__(self, db: Session) -> None:
        super().__init__(db, task_sender=self._fake_send)

    def _fake_send(self, prediction_id: int, queue: str) -> FakeAsyncResult:
        return FakeAsyncResult(f"fake-{prediction_id}-{queue}")


@pytest.fixture
def prediction_client(
    app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[TestClient, None, None]:
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

    def override_get_db() -> Generator[Session, None, None]:
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    monkeypatch.setattr(predictions_api, "PredictionService", FakePredictionService)
    with testing_session_local() as db:
        seed_model_metadata(db)
    with TestClient(app) as test_client:
        test_client.testing_session_local = testing_session_local
        yield test_client
    app.dependency_overrides.pop(get_db, None)


def seed_model_metadata(db: Session) -> None:
    db.add(
        MLModel(
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
    )
    db.commit()


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


def register_and_login(client: TestClient) -> tuple[dict[str, str], dict]:
    payload = {
        "email": f"prediction-{uuid4().hex}@example.com",
        "password": "StrongPassword123!",
    }
    register_response = client.post("/api/v1/auth/register", json=payload)
    assert register_response.status_code == 201
    login_response = client.post("/api/v1/auth/login", json=payload)
    assert login_response.status_code == 200
    return payload, login_response.json()


def auth_headers(tokens: dict) -> dict[str, str]:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def set_user_balance(client: TestClient, email: str, balance: int) -> None:
    session_local = client.testing_session_local
    with session_local() as db:
        user = db.scalar(select(User).where(User.email == email))
        user.balance = balance
        user.reserved_balance = 0
        db.commit()


def test_create_prediction_requires_auth(prediction_client: TestClient) -> None:
    response = prediction_client.post(
        "/api/v1/predictions",
        json={"features": valid_features()},
    )

    assert response.status_code == 401


def test_create_prediction_returns_pending(prediction_client: TestClient) -> None:
    _, tokens = register_and_login(prediction_client)

    response = prediction_client.post(
        "/api/v1/predictions",
        json={"features": valid_features()},
        headers=auth_headers(tokens),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "pending"
    assert body["prediction"] is None
    assert body["cancellation_probability"] is None
    assert body["risk_label"] is None
    assert body["cost_credits"] == 10
    assert body["celery_task_id"].startswith("fake-")


def test_create_prediction_decreases_balance_by_10_and_reserved_increases(
    prediction_client: TestClient,
) -> None:
    _, tokens = register_and_login(prediction_client)

    response = prediction_client.post(
        "/api/v1/predictions",
        json={"features": valid_features()},
        headers=auth_headers(tokens),
    )
    assert response.status_code == 200
    balance_response = prediction_client.get(
        "/api/v1/billing/balance",
        headers=auth_headers(tokens),
    )

    assert balance_response.json() == {"balance": 90, "reserved_balance": 10}


def test_free_active_prediction_limit_returns_409_without_extra_reserve(
    prediction_client: TestClient,
) -> None:
    _, tokens = register_and_login(prediction_client)
    headers = auth_headers(tokens)

    for _ in range(3):
        response = prediction_client.post(
            "/api/v1/predictions",
            json={"features": valid_features()},
            headers=headers,
        )
        assert response.status_code == 200

    balance_before = prediction_client.get(
        "/api/v1/billing/balance",
        headers=headers,
    ).json()
    response = prediction_client.post(
        "/api/v1/predictions",
        json={"features": valid_features()},
        headers=headers,
    )
    balance_after = prediction_client.get(
        "/api/v1/billing/balance",
        headers=headers,
    ).json()
    history = prediction_client.get(
        "/api/v1/predictions/history",
        headers=headers,
    ).json()

    assert response.status_code == 409
    assert response.json()["detail"] == "Active prediction limit reached: 3"
    assert balance_before == {"balance": 70, "reserved_balance": 30}
    assert balance_after == balance_before
    assert len(history["items"]) == 3


def test_get_prediction_pending(prediction_client: TestClient) -> None:
    _, tokens = register_and_login(prediction_client)
    create_response = prediction_client.post(
        "/api/v1/predictions",
        json={"features": valid_features()},
        headers=auth_headers(tokens),
    )
    prediction_id = create_response.json()["id"]

    response = prediction_client.get(
        f"/api/v1/predictions/{prediction_id}",
        headers=auth_headers(tokens),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "pending"


def test_history_shows_prediction(prediction_client: TestClient) -> None:
    _, tokens = register_and_login(prediction_client)
    create_response = prediction_client.post(
        "/api/v1/predictions",
        json={"features": valid_features()},
        headers=auth_headers(tokens),
    )

    response = prediction_client.get(
        "/api/v1/predictions/history",
        headers=auth_headers(tokens),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["limit"] == 50
    assert body["offset"] == 0
    assert [item["id"] for item in body["items"]] == [create_response.json()["id"]]


def test_invalid_payload_returns_422(prediction_client: TestClient) -> None:
    _, tokens = register_and_login(prediction_client)
    features = valid_features()
    features["adr"] = -1

    response = prediction_client.post(
        "/api/v1/predictions",
        json={"features": features},
        headers=auth_headers(tokens),
    )

    assert response.status_code == 422


def test_extra_fields_rejected(prediction_client: TestClient) -> None:
    _, tokens = register_and_login(prediction_client)
    features = valid_features()
    features["unexpected"] = "value"

    response = prediction_client.post(
        "/api/v1/predictions",
        json={"features": features},
        headers=auth_headers(tokens),
    )

    assert response.status_code == 422


def test_leakage_fields_rejected(prediction_client: TestClient) -> None:
    _, tokens = register_and_login(prediction_client)
    features = valid_features()
    features["reservation_status"] = "Check-Out"

    response = prediction_client.post(
        "/api/v1/predictions",
        json={"features": features},
        headers=auth_headers(tokens),
    )

    assert response.status_code == 422


def test_insufficient_credits_returns_402(prediction_client: TestClient) -> None:
    payload, tokens = register_and_login(prediction_client)
    set_user_balance(prediction_client, payload["email"], balance=5)

    response = prediction_client.post(
        "/api/v1/predictions",
        json={"features": valid_features()},
        headers=auth_headers(tokens),
    )

    assert response.status_code == 402


def test_owner_only_detail(prediction_client: TestClient) -> None:
    _, first_tokens = register_and_login(prediction_client)
    _, second_tokens = register_and_login(prediction_client)
    create_response = prediction_client.post(
        "/api/v1/predictions",
        json={"features": valid_features()},
        headers=auth_headers(first_tokens),
    )
    prediction_id = create_response.json()["id"]

    response = prediction_client.get(
        f"/api/v1/predictions/{prediction_id}",
        headers=auth_headers(second_tokens),
    )

    assert response.status_code == 404
