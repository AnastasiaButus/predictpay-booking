import pytest

from dashboard.api_client import (
    APIError,
    BookingGuardAPIClient,
    _extract_error_message,
    build_auth_headers,
)
from dashboard.localization import (
    localize_prediction_rows,
    localize_transaction_rows,
    translate_reason,
    translate_risk,
    translate_status,
    translate_transaction_type,
)


class FakeResponse:
    def __init__(self, status_code: int, payload=None) -> None:
        self.status_code = status_code
        self._payload = payload
        self.content = b"" if payload is None else b"{}"

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class FakeSession:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append({"method": method, "url": url, **kwargs})
        return self.response


def test_build_auth_headers() -> None:
    assert build_auth_headers("token") == {"Authorization": "Bearer token"}


def test_login_success_with_mocked_requests() -> None:
    session = FakeSession(
        FakeResponse(
            200,
            {
                "access_token": "access",
                "refresh_token": "refresh",
                "token_type": "bearer",
            },
        )
    )
    client = BookingGuardAPIClient(base_url="http://backend:8000", session=session)

    result = client.login("demo@example.com", "StrongPassword123!")

    assert result["access_token"] == "access"
    assert session.calls[0]["method"] == "POST"
    assert session.calls[0]["url"] == "http://backend:8000/api/v1/auth/login"
    assert session.calls[0]["json"] == {
        "email": "demo@example.com",
        "password": "StrongPassword123!",
    }


def test_get_balance_sends_bearer_token() -> None:
    session = FakeSession(FakeResponse(200, {"balance": 100, "reserved_balance": 0}))
    client = BookingGuardAPIClient(base_url="http://backend:8000", session=session)

    client.get_balance("access-token")

    assert session.calls[0]["headers"] == {"Authorization": "Bearer access-token"}


def test_create_prediction_payload_shape() -> None:
    session = FakeSession(FakeResponse(200, {"id": 1, "status": "pending"}))
    client = BookingGuardAPIClient(base_url="http://backend:8000", session=session)
    features = {"hotel": "City Hotel", "lead_time": 120}

    client.create_prediction("access-token", features)

    assert session.calls[0]["method"] == "POST"
    assert session.calls[0]["url"] == "http://backend:8000/api/v1/predictions"
    assert session.calls[0]["json"] == {"features": features}
    assert session.calls[0]["headers"] == {"Authorization": "Bearer access-token"}


def test_api_error_message_extraction() -> None:
    response = FakeResponse(
        422,
        {
            "detail": [
                {
                    "loc": ["body", "features", "adr"],
                    "msg": "Input should be greater than or equal to 0",
                }
            ]
        },
    )

    assert (
        _extract_error_message(response)
        == "body.features.adr: Input should be greater than or equal to 0"
    )


def test_api_error_is_raised_with_message() -> None:
    session = FakeSession(FakeResponse(402, {"detail": "Insufficient credits"}))
    client = BookingGuardAPIClient(base_url="http://backend:8000", session=session)

    with pytest.raises(APIError) as exc_info:
        client.get_balance("access-token")

    assert exc_info.value.message == "Insufficient credits"
    assert exc_info.value.status_code == 402


def test_translate_status() -> None:
    assert translate_status("pending") == "в очереди"
    assert translate_status("processing") == "обрабатывается"
    assert translate_status("completed") == "завершено"
    assert translate_status("failed") == "ошибка"


def test_translate_risk_label() -> None:
    assert translate_risk("low") == "низкий риск"
    assert translate_risk("medium") == "средний риск"
    assert translate_risk("high") == "высокий риск"


def test_translate_transaction_type() -> None:
    assert translate_transaction_type("top_up") == "пополнение"
    assert translate_transaction_type("promo_bonus") == "промокод"
    assert translate_transaction_type("prediction_reserve") == "резерв под прогноз"
    assert translate_transaction_type("prediction_charge") == "подтверждение списания"
    assert translate_transaction_type("prediction_refund") == "возврат за прогноз"


def test_translate_reason() -> None:
    assert translate_reason("Mock payment top-up") == "Тестовое пополнение баланса"
    assert (
        translate_reason("Promocode activated: WELCOME100")
        == "Промокод активирован: WELCOME100"
    )
    assert (
        translate_reason("Poincaré challenge bonus activated")
        == "Бонус POINCARE_CHALLENGE начислен"
    )


def test_localize_prediction_rows() -> None:
    rows = localize_prediction_rows(
        [
            {
                "id": 1,
                "status": "completed",
                "prediction": 1,
                "cancellation_probability": 0.82,
                "risk_label": "high",
                "cost_credits": 10,
                "model_name": "hotel_cancellation_model",
                "model_version": "1.0.0",
                "error_message": None,
                "celery_task_id": "task-id",
                "created_at": "2026-05-09",
                "completed_at": "2026-05-09",
            }
        ]
    )

    assert rows == [
        {
            "ID": 1,
            "Статус": "завершено",
            "Прогноз": 1,
            "Вероятность отмены": 0.82,
            "Риск": "высокий риск",
            "Стоимость, credits": 10,
            "Модель": "hotel_cancellation_model",
            "Версия модели": "1.0.0",
            "Ошибка": None,
            "ID Celery-задачи": "task-id",
            "Создано": "2026-05-09",
            "Завершено": "2026-05-09",
        }
    ]


def test_localize_transaction_rows() -> None:
    rows = localize_transaction_rows(
        [
            {
                "id": 1,
                "amount": -10,
                "transaction_type": "prediction_reserve",
                "status": "completed",
                "reason": "Reserved credits for prediction",
                "prediction_id": 2,
                "promocode_id": None,
                "created_at": "2026-05-09",
            }
        ]
    )

    assert rows == [
        {
            "ID": 1,
            "Сумма": -10,
            "Тип операции": "резерв под прогноз",
            "Статус": "завершено",
            "Причина": "Резерв credits под прогноз",
            "ID прогноза": 2,
            "ID промокода": None,
            "Создано": "2026-05-09",
        }
    ]
