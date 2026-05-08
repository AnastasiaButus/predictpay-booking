import sys
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(BACKEND_ROOT))

from app.main import app as fastapi_app  # noqa: E402
from tests.fixtures.booking_payloads import (  # noqa: E402
    INVALID_BOOKING_PAYLOAD,
    VALID_BOOKING_PAYLOAD,
)
from tests.fixtures.promocodes import (  # noqa: E402
    POINCARE_CHALLENGE_PAYLOAD,
    WELCOME_PROMOCODE_PAYLOAD,
)
from tests.fixtures.users import ADMIN_USER_PAYLOAD, VALID_USER_PAYLOAD  # noqa: E402


@pytest.fixture
def app() -> FastAPI:
    return fastapi_app


@pytest.fixture
def client(app: FastAPI) -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def valid_user_payload() -> dict[str, str]:
    return VALID_USER_PAYLOAD.copy()


@pytest.fixture
def admin_user_payload() -> dict[str, str]:
    return ADMIN_USER_PAYLOAD.copy()


@pytest.fixture
def valid_booking_payload() -> dict:
    return {
        "model_id": VALID_BOOKING_PAYLOAD["model_id"],
        "features": VALID_BOOKING_PAYLOAD["features"].copy(),
    }


@pytest.fixture
def invalid_booking_payload() -> dict:
    return {
        "model_id": INVALID_BOOKING_PAYLOAD["model_id"],
        "features": INVALID_BOOKING_PAYLOAD["features"].copy(),
    }


@pytest.fixture
def welcome_promocode_payload() -> dict[str, str]:
    return WELCOME_PROMOCODE_PAYLOAD.copy()


@pytest.fixture
def poincare_challenge_payload() -> dict[str, str]:
    return POINCARE_CHALLENGE_PAYLOAD.copy()
