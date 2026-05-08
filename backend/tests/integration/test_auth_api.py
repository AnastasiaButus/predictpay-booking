from collections.abc import Generator
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
from app.models.refresh_token import RefreshToken
from app.models.user import User


@pytest.fixture
def auth_client(app: FastAPI) -> Generator[TestClient, None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    User.__table__.create(bind=engine)
    RefreshToken.__table__.create(bind=engine)
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


def unique_email(prefix: str = "user") -> str:
    return f"{prefix}-{uuid4().hex}@example.com"


def register_payload(email: str | None = None, password: str = "StrongPassword123!") -> dict:
    return {
        "email": email or unique_email(),
        "password": password,
    }


def register_user(auth_client: TestClient, email: str | None = None) -> dict:
    payload = register_payload(email=email)
    response = auth_client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    return payload


def login_user(auth_client: TestClient, email: str, password: str) -> dict:
    response = auth_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200
    return response.json()


def test_register_user_success(auth_client: TestClient) -> None:
    payload = register_payload()

    response = auth_client.post("/api/v1/auth/register", json=payload)

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == payload["email"]
    assert body["role"] == "user"
    assert body["plan"] == "free"
    assert body["balance"] == 100
    assert "hashed_password" not in body


def test_register_duplicate_email_returns_409(auth_client: TestClient) -> None:
    payload = register_payload()
    first_response = auth_client.post("/api/v1/auth/register", json=payload)
    assert first_response.status_code == 201

    duplicate_response = auth_client.post("/api/v1/auth/register", json=payload)

    assert duplicate_response.status_code == 409


def test_login_success(auth_client: TestClient) -> None:
    payload = register_user(auth_client)

    response = auth_client.post("/api/v1/auth/login", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 1800


def test_login_wrong_password_returns_401(auth_client: TestClient) -> None:
    payload = register_user(auth_client)

    response = auth_client.post(
        "/api/v1/auth/login",
        json={"email": payload["email"], "password": "WrongPassword123!"},
    )

    assert response.status_code == 401


def test_users_me_without_token_returns_401(auth_client: TestClient) -> None:
    response = auth_client.get("/api/v1/users/me")

    assert response.status_code == 401


def test_users_me_with_token_returns_200(auth_client: TestClient) -> None:
    payload = register_user(auth_client)
    tokens = login_user(auth_client, payload["email"], payload["password"])

    response = auth_client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == payload["email"]
    assert "hashed_password" not in body


def test_refresh_success(auth_client: TestClient) -> None:
    payload = register_user(auth_client)
    tokens = login_user(auth_client, payload["email"], payload["password"])

    response = auth_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["refresh_token"] != tokens["refresh_token"]

    reused_response = auth_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert reused_response.status_code == 401


def test_logout_revokes_refresh_token(auth_client: TestClient) -> None:
    payload = register_user(auth_client)
    tokens = login_user(auth_client, payload["email"], payload["password"])

    logout_response = auth_client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": tokens["refresh_token"]},
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )

    assert logout_response.status_code == 200
    assert logout_response.json()["message"] == "Logged out"

    refresh_response = auth_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert refresh_response.status_code == 401
