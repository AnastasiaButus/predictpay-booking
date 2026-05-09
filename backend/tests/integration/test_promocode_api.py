from collections.abc import Generator
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models.prediction  # noqa: F401
from app.api.deps import get_db
from app.models.promocode import Promocode
from app.models.promocode_activation import PromocodeActivation
from app.models.refresh_token import RefreshToken
from app.models.transaction import Transaction
from app.models.user import User


@pytest.fixture
def promocode_client(app: FastAPI) -> Generator[TestClient, None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    User.__table__.create(bind=engine)
    RefreshToken.__table__.create(bind=engine)
    Promocode.__table__.create(bind=engine)
    PromocodeActivation.__table__.create(bind=engine)
    Transaction.__table__.create(bind=engine)
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
    with testing_session_local() as db:
        seed_test_promocodes(db)
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_db, None)


def seed_test_promocodes(db: Session) -> None:
    db.add_all(
        [
            Promocode(
                code="WELCOME100",
                credits_amount=100,
                max_activations=100000,
                current_activations=0,
                is_active=True,
                description="Welcome bonus",
            ),
            Promocode(
                code="POINCARE_CHALLENGE",
                credits_amount=1000,
                max_activations=100000,
                current_activations=0,
                is_active=True,
                description="Poincare challenge",
            ),
        ]
    )
    db.commit()


def register_and_login(client: TestClient) -> tuple[dict[str, str], dict]:
    payload = {
        "email": f"promo-{uuid4().hex}@example.com",
        "password": "StrongPassword123!",
    }
    register_response = client.post("/api/v1/auth/register", json=payload)
    assert register_response.status_code == 201
    login_response = client.post("/api/v1/auth/login", json=payload)
    assert login_response.status_code == 200
    return payload, login_response.json()


def auth_headers(tokens: dict) -> dict[str, str]:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def test_list_promocodes_requires_auth(promocode_client: TestClient) -> None:
    response = promocode_client.get("/api/v1/promocodes")

    assert response.status_code == 401


def test_list_promocodes_success(promocode_client: TestClient) -> None:
    _, tokens = register_and_login(promocode_client)

    response = promocode_client.get(
        "/api/v1/promocodes",
        headers=auth_headers(tokens),
    )

    assert response.status_code == 200
    codes = {item["code"] for item in response.json()}
    assert {"WELCOME100", "POINCARE_CHALLENGE"}.issubset(codes)


def test_activate_promocode_requires_auth(promocode_client: TestClient) -> None:
    response = promocode_client.post(
        "/api/v1/promocodes/activate",
        json={"code": "WELCOME100"},
    )

    assert response.status_code == 401


def test_activate_welcome100_success(promocode_client: TestClient) -> None:
    _, tokens = register_and_login(promocode_client)

    response = promocode_client.post(
        "/api/v1/promocodes/activate",
        json={"code": "WELCOME100"},
        headers=auth_headers(tokens),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == "WELCOME100"
    assert body["credits_amount"] == 100
    assert body["balance"] == 200


def test_activate_duplicate_returns_409(promocode_client: TestClient) -> None:
    _, tokens = register_and_login(promocode_client)
    first_response = promocode_client.post(
        "/api/v1/promocodes/activate",
        json={"code": "WELCOME100"},
        headers=auth_headers(tokens),
    )
    assert first_response.status_code == 200

    duplicate_response = promocode_client.post(
        "/api/v1/promocodes/activate",
        json={"code": "WELCOME100"},
        headers=auth_headers(tokens),
    )

    assert duplicate_response.status_code == 409


def test_activate_unknown_returns_404(promocode_client: TestClient) -> None:
    _, tokens = register_and_login(promocode_client)

    response = promocode_client.post(
        "/api/v1/promocodes/activate",
        json={"code": "UNKNOWN"},
        headers=auth_headers(tokens),
    )

    assert response.status_code == 404


def test_poincare_challenge_success(promocode_client: TestClient) -> None:
    _, tokens = register_and_login(promocode_client)

    response = promocode_client.post(
        "/api/v1/promocodes/poincare-challenge",
        json={"proof_url": "https://example.com/poincare-proof"},
        headers=auth_headers(tokens),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == "POINCARE_CHALLENGE"
    assert body["balance"] == 1100
    assert "URL format only" in body["message"]


def test_poincare_challenge_invalid_url_returns_422(
    promocode_client: TestClient,
) -> None:
    _, tokens = register_and_login(promocode_client)

    response = promocode_client.post(
        "/api/v1/promocodes/poincare-challenge",
        json={"proof_url": "not-a-url"},
        headers=auth_headers(tokens),
    )

    assert response.status_code == 422
