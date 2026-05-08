from collections.abc import Generator
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models.prediction  # noqa: F401
import app.models.promocode  # noqa: F401
from app.api.deps import get_db
from app.models.refresh_token import RefreshToken
from app.models.transaction import Transaction
from app.models.user import User


@pytest.fixture
def billing_client(app: FastAPI) -> Generator[TestClient, None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    User.__table__.create(bind=engine)
    RefreshToken.__table__.create(bind=engine)
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
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_db, None)


def register_payload() -> dict[str, str]:
    return {
        "email": f"billing-{uuid4().hex}@example.com",
        "password": "StrongPassword123!",
    }


def register_and_login(client: TestClient) -> tuple[dict[str, str], dict]:
    payload = register_payload()
    register_response = client.post("/api/v1/auth/register", json=payload)
    assert register_response.status_code == 201
    login_response = client.post("/api/v1/auth/login", json=payload)
    assert login_response.status_code == 200
    return payload, login_response.json()


def auth_headers(tokens: dict) -> dict[str, str]:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def test_get_balance_requires_auth(billing_client: TestClient) -> None:
    response = billing_client.get("/api/v1/billing/balance")

    assert response.status_code == 401


def test_get_balance_success(billing_client: TestClient) -> None:
    _, tokens = register_and_login(billing_client)

    response = billing_client.get(
        "/api/v1/billing/balance",
        headers=auth_headers(tokens),
    )

    assert response.status_code == 200
    assert response.json() == {"balance": 100, "reserved_balance": 0}


def test_top_up_success(billing_client: TestClient) -> None:
    _, tokens = register_and_login(billing_client)

    response = billing_client.post(
        "/api/v1/billing/top-up",
        json={"amount": 100},
        headers=auth_headers(tokens),
    )

    assert response.status_code == 200
    assert response.json() == {"balance": 200, "reserved_balance": 0}


def test_top_up_invalid_amount_returns_422(billing_client: TestClient) -> None:
    _, tokens = register_and_login(billing_client)

    response = billing_client.post(
        "/api/v1/billing/top-up",
        json={"amount": 0},
        headers=auth_headers(tokens),
    )

    assert response.status_code == 422


def test_transactions_requires_auth(billing_client: TestClient) -> None:
    response = billing_client.get("/api/v1/billing/transactions")

    assert response.status_code == 401


def test_transactions_returns_only_current_user_transactions(
    billing_client: TestClient,
) -> None:
    _, first_tokens = register_and_login(billing_client)
    _, second_tokens = register_and_login(billing_client)

    first_top_up = billing_client.post(
        "/api/v1/billing/top-up",
        json={"amount": 25},
        headers=auth_headers(first_tokens),
    )
    assert first_top_up.status_code == 200
    second_top_up = billing_client.post(
        "/api/v1/billing/top-up",
        json={"amount": 75},
        headers=auth_headers(second_tokens),
    )
    assert second_top_up.status_code == 200

    response = billing_client.get(
        "/api/v1/billing/transactions",
        headers=auth_headers(first_tokens),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["limit"] == 50
    assert body["offset"] == 0
    assert len(body["items"]) == 1
    assert body["items"][0]["amount"] == 25
    assert body["items"][0]["transaction_type"] == "top_up"
