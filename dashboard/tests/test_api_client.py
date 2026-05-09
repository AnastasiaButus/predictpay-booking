import pytest

from dashboard.api_client import (
    APIError,
    BookingGuardAPIClient,
    _extract_error_message,
    build_auth_headers,
)
from dashboard.localization import (
    ADR_HELP_TEXT,
    CUSTOMER_TYPE_LABELS,
    DEPOSIT_TYPE_LABELS,
    HOTEL_LABELS,
    MARKET_SEGMENT_LABELS,
    SECRET_CHALLENGE_MVP_NOTE,
    SECRET_CHALLENGE_TEXT,
    SECRET_CHALLENGE_TITLE,
    format_datetime_short,
    format_funny_tickets,
    format_signed_funny_tickets,
    localize_prediction_rows,
    localize_promocode_rows,
    localize_transaction_rows,
    translate_reason,
    translate_risk,
    translate_status,
    translate_transaction_type,
    translate_error_message,
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


def test_hotel_label_mapping() -> None:
    assert HOTEL_LABELS["City Hotel"] == "Городской отель"
    assert HOTEL_LABELS["Resort Hotel"] == "Курортный отель"


def test_deposit_type_label_mapping() -> None:
    assert DEPOSIT_TYPE_LABELS["No Deposit"] == "Без депозита"
    assert DEPOSIT_TYPE_LABELS["Non Refund"] == "Невозвратный депозит"
    assert DEPOSIT_TYPE_LABELS["Refundable"] == "Возвратный депозит"


def test_customer_type_label_mapping() -> None:
    assert CUSTOMER_TYPE_LABELS["Transient"] == "Индивидуальный клиент"
    assert CUSTOMER_TYPE_LABELS["Transient-Party"] == "Индивидуальный клиент / группа"
    assert CUSTOMER_TYPE_LABELS["Contract"] == "Контрактный клиент"
    assert CUSTOMER_TYPE_LABELS["Group"] == "Группа"


def test_market_segment_label_mapping() -> None:
    assert MARKET_SEGMENT_LABELS["Online TA"] == "Онлайн-турагентство"
    assert MARKET_SEGMENT_LABELS["Offline TA/TO"] == "Офлайн-турагентство / туроператор"
    assert MARKET_SEGMENT_LABELS["Direct"] == "Прямое бронирование"
    assert MARKET_SEGMENT_LABELS["Groups"] == "Группы"
    assert MARKET_SEGMENT_LABELS["Corporate"] == "Корпоративный канал"
    assert MARKET_SEGMENT_LABELS["Complementary"] == "Бесплатное/комплиментарное размещение"
    assert MARKET_SEGMENT_LABELS["Aviation"] == "Авиационный сегмент"


def test_backend_values_are_preserved_for_prediction_options() -> None:
    assert set(HOTEL_LABELS) == {"City Hotel", "Resort Hotel"}
    assert set(DEPOSIT_TYPE_LABELS) == {"No Deposit", "Non Refund", "Refundable"}
    assert set(CUSTOMER_TYPE_LABELS) == {
        "Transient",
        "Transient-Party",
        "Contract",
        "Group",
    }
    assert set(MARKET_SEGMENT_LABELS) == {
        "Online TA",
        "Offline TA/TO",
        "Direct",
        "Groups",
        "Corporate",
        "Complementary",
        "Aviation",
    }


def test_format_funny_tickets_one() -> None:
    assert format_funny_tickets(1) == "1 билет банка приколов"
    assert format_funny_tickets(21) == "21 билет банка приколов"
    assert format_funny_tickets(101) == "101 билет банка приколов"


def test_format_funny_tickets_few() -> None:
    assert format_funny_tickets(2) == "2 билета банка приколов"
    assert format_funny_tickets(3) == "3 билета банка приколов"
    assert format_funny_tickets(4) == "4 билета банка приколов"
    assert format_funny_tickets(22) == "22 билета банка приколов"


def test_format_funny_tickets_many() -> None:
    assert format_funny_tickets(5) == "5 билетов банка приколов"
    assert format_funny_tickets(10) == "10 билетов банка приколов"
    assert format_funny_tickets(25) == "25 билетов банка приколов"
    assert format_funny_tickets(100) == "100 билетов банка приколов"
    assert format_funny_tickets(1000) == "1000 билетов банка приколов"


def test_format_funny_tickets_teens() -> None:
    assert format_funny_tickets(11) == "11 билетов банка приколов"
    assert format_funny_tickets(12) == "12 билетов банка приколов"
    assert format_funny_tickets(14) == "14 билетов банка приколов"


def test_format_datetime_short_iso_z() -> None:
    assert format_datetime_short("2026-05-09T07:27:53.651923Z") == "09.05.2026 07:27"


def test_format_datetime_short_iso_offset() -> None:
    assert (
        format_datetime_short("2026-05-09T07:27:53.651923+00:00")
        == "09.05.2026 07:27"
    )


def test_format_datetime_short_invalid_value() -> None:
    assert format_datetime_short("not-a-date") == "not-a-date"
    assert format_datetime_short(None) == "—"


def test_adr_label_or_help_text_exists() -> None:
    assert ADR_HELP_TEXT == "Условные денежные единицы."


def test_secret_challenge_copy() -> None:
    assert SECRET_CHALLENGE_TITLE == "Секретное задание на большой бонус"
    assert "Докажите утверждение" in SECRET_CHALLENGE_TEXT
    assert "MVP ожидает ссылку на материал" in SECRET_CHALLENGE_MVP_NOTE
    assert "POINCARE_CHALLENGE" not in SECRET_CHALLENGE_TITLE


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
        == "Бонус за секретное задание начислен"
    )


def test_translate_invalid_secret_challenge_url_message() -> None:
    assert (
        translate_error_message("body.proof_url: Input should be a valid URL")
        == "В MVP нужно отправить ссылку на материал."
    )


def test_localize_promocode_rows_hides_secret_challenge_code() -> None:
    rows = localize_promocode_rows(
        [
            {
                "code": "POINCARE_CHALLENGE",
                "credits_amount": 1000,
                "description": "raw",
            }
        ]
    )

    assert rows[0]["Код"] == "Секретное задание на большой бонус"
    assert rows[0]["Бонус"] == "1000 билетов банка приколов"


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
                "created_at": "2026-05-09T08:42:51.381372Z",
                "completed_at": "2026-05-09T08:43:51.381372+00:00",
            }
        ]
    )

    assert rows == [
        {
            "Создано": "09.05.2026 08:42",
            "Завершено": "09.05.2026 08:43",
            "Статус": "завершено",
            "Прогноз": "отмена вероятна",
            "Вероятность отмены": "82.0%",
            "Риск": "высокий риск",
            "Стоимость": "10 билетов банка приколов",
            "Модель": "hotel_cancellation_model v1.0.0",
            "Комментарий": "—",
        }
    ]


def test_localize_prediction_rows_exact_user_columns() -> None:
    rows = localize_prediction_rows(
        [
            {
                "status": "pending",
                "prediction": None,
                "cancellation_probability": None,
                "risk_label": None,
                "cost_credits": 10,
                "model_name": "hotel_cancellation_model",
                "model_version": "1.0.0",
                "error_message": None,
                "created_at": "2026-05-09T08:42:51.381372Z",
                "completed_at": None,
            }
        ]
    )

    assert list(rows[0]) == [
        "Создано",
        "Завершено",
        "Статус",
        "Прогноз",
        "Вероятность отмены",
        "Риск",
        "Стоимость",
        "Модель",
        "Комментарий",
    ]


def test_localize_prediction_rows_drops_internal_fields() -> None:
    rows = localize_prediction_rows(
        [
            {
                "id": 1,
                "celery_task_id": "task-id",
                "created_at": "2026-05-09T08:42:51.381372Z",
                "completed_at": "2026-05-09T08:43:51.381372Z",
                "model_name": "hotel_cancellation_model",
                "model_version": "1.0.0",
            }
        ]
    )

    forbidden_keys = {
        "id",
        "ID",
        "celery_task_id",
        "ID Celery-задачи",
        "created_at",
        "completed_at",
    }
    assert forbidden_keys.isdisjoint(rows[0])


def test_localize_prediction_rows_formats_dates_short() -> None:
    rows = localize_prediction_rows(
        [
            {
                "created_at": "2026-05-09T08:42:51.381372Z",
                "completed_at": "2026-05-09T08:43:51.381372+00:00",
            }
        ]
    )

    assert rows[0]["Создано"] == "09.05.2026 08:42"
    assert rows[0]["Завершено"] == "09.05.2026 08:43"


def test_localize_prediction_rows_formats_probability_percent() -> None:
    rows = localize_prediction_rows([{"cancellation_probability": 0.96}])

    assert rows[0]["Вероятность отмены"] == "96.0%"


def test_localize_prediction_rows_formats_prediction_label() -> None:
    rows = localize_prediction_rows([{"prediction": 1}, {"prediction": 0}])

    assert rows[0]["Прогноз"] == "отмена вероятна"
    assert rows[1]["Прогноз"] == "отмена не ожидается"


def test_localize_prediction_rows_formats_model_version() -> None:
    rows = localize_prediction_rows(
        [{"model_name": "hotel_cancellation_model", "model_version": "1.0.0"}]
    )

    assert rows[0]["Модель"] == "hotel_cancellation_model v1.0.0"


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
                "created_at": "2026-05-09T07:27:53.651923Z",
            }
        ]
    )

    assert rows == [
        {
            "Дата и время": "09.05.2026 07:27",
            "Тип операции": "резерв под прогноз",
            "Сумма": "-10 билетов банка приколов",
            "Статус": "завершено",
            "Комментарий": "Резерв билетов банка приколов под прогноз",
        }
    ]


def test_localize_transaction_rows_hides_internal_ids() -> None:
    rows = localize_transaction_rows(
        [
            {
                "id": 10,
                "amount": 100,
                "transaction_type": "top_up",
                "status": "completed",
                "reason": "Mock payment top-up",
                "prediction_id": 20,
                "promocode_id": 30,
                "created_at": "2026-05-09T07:27:53.651923Z",
            }
        ]
    )

    forbidden_keys = {"ID", "ID прогноза", "ID промокода", "id", "prediction_id", "promocode_id"}
    assert forbidden_keys.isdisjoint(rows[0])


def test_localize_transaction_rows_has_user_columns_only() -> None:
    rows = localize_transaction_rows(
        [
            {
                "id": 1,
                "amount": 0,
                "transaction_type": "prediction_charge",
                "status": "completed",
                "reason": "Prediction charge confirmed",
                "prediction_id": 2,
                "promocode_id": None,
                "created_at": "2026-05-09T07:27:53.651923Z",
            }
        ]
    )

    assert list(rows[0]) == ["Дата и время", "Тип операции", "Сумма", "Статус", "Комментарий"]


def test_localize_transaction_rows_formats_created_at_short() -> None:
    rows = localize_transaction_rows(
        [
            {
                "amount": 100,
                "transaction_type": "top_up",
                "status": "completed",
                "reason": "Mock payment top-up",
                "created_at": "2026-05-09T07:27:53.651923+00:00",
            }
        ]
    )

    assert rows[0]["Дата и время"] == "09.05.2026 07:27"


def test_localize_transaction_rows_formats_signed_ticket_amount() -> None:
    assert format_signed_funny_tickets(100) == "+100 билетов банка приколов"
    assert format_signed_funny_tickets(-10) == "-10 билетов банка приколов"
    assert format_signed_funny_tickets(0) == "0 билетов банка приколов"
