from datetime import datetime
from typing import Any


STATUS_LABELS = {
    "pending": "в очереди",
    "processing": "обрабатывается",
    "completed": "завершено",
    "failed": "ошибка",
}

RISK_LABELS = {
    "low": "низкий риск",
    "medium": "средний риск",
    "high": "высокий риск",
}

TRANSACTION_TYPE_LABELS = {
    "top_up": "пополнение",
    "promo_bonus": "промокод",
    "prediction_reserve": "резерв под прогноз",
    "prediction_charge": "подтверждение списания",
    "prediction_refund": "возврат за прогноз",
}

REASON_LABELS = {
    "Mock payment top-up": "Тестовое пополнение баланса",
    "Reserved credits for prediction": "Резерв билетов банка приколов под прогноз",
    "Prediction charge confirmed": "Списание за прогноз подтверждено",
    "Prediction failed, credits refunded": "Билеты банка приколов за прогноз возвращены",
    "Poincaré challenge bonus activated": "Бонус за секретное задание начислен",
}

PROMOCODE_DESCRIPTIONS = {
    "WELCOME100": "Приветственный бонус: +100 билетов банка приколов.",
    "ANISIMOV100": "Пасхалка курса в честь преподавателя: Анисимов Ян Олегович.",
    "SPRINGFIELD100": "Пасхалка для тех, кто узнал город и стиль аватарки преподавателя.",
    "POINCARE_CHALLENGE": "Секретное задание на большой бонус.",
}

SECRET_CHALLENGE_TITLE = "Секретное задание на большой бонус"
SECRET_CHALLENGE_TEXT = "Докажите утверждение: всякое замкнутое односвязное трёхмерное многообразие гомеоморфно трёхмерной сфере."
SECRET_CHALLENGE_MVP_NOTE = "MVP ожидает ссылку на материал и проверяет только формат URL; математическая корректность доказательства не проверяется."
ADR_HELP_TEXT = "Условные денежные единицы."

HOTEL_LABELS = {
    "City Hotel": "Городской отель",
    "Resort Hotel": "Курортный отель",
}

DEPOSIT_TYPE_LABELS = {
    "No Deposit": "Без депозита",
    "Non Refund": "Невозвратный депозит",
    "Refundable": "Возвратный депозит",
}

CUSTOMER_TYPE_LABELS = {
    "Transient": "Индивидуальный клиент",
    "Transient-Party": "Индивидуальный клиент / группа",
    "Contract": "Контрактный клиент",
    "Group": "Группа",
}

MARKET_SEGMENT_LABELS = {
    "Online TA": "Онлайн-турагентство",
    "Offline TA/TO": "Офлайн-турагентство / туроператор",
    "Direct": "Прямое бронирование",
    "Groups": "Группы",
    "Corporate": "Корпоративный канал",
    "Complementary": "Бесплатное/комплиментарное размещение",
    "Aviation": "Авиационный сегмент",
}

PREDICTION_COLUMNS = {
    "created_at": "Создано",
    "completed_at": "Завершено",
    "status": "Статус",
    "prediction": "Прогноз",
    "cancellation_probability": "Вероятность отмены",
    "risk_label": "Риск",
    "cost_credits": "Стоимость",
    "model": "Модель",
    "comment": "Комментарий",
}

TRANSACTION_COLUMNS = {
    "created_at": "Дата и время",
    "transaction_type": "Тип операции",
    "amount": "Сумма",
    "status": "Статус",
    "reason": "Комментарий",
}


def translate_status(value: str | None) -> str:
    if value is None:
        return "-"
    return STATUS_LABELS.get(value, value)


def translate_risk(value: str | None) -> str:
    if value is None:
        return "-"
    return RISK_LABELS.get(value, value)


def translate_transaction_type(value: str | None) -> str:
    if value is None:
        return "-"
    return TRANSACTION_TYPE_LABELS.get(value, value)


def translate_reason(value: str | None) -> str:
    if not value:
        return "-"
    if value.startswith("Promocode activated:"):
        code = value.split(":", maxsplit=1)[1].strip()
        if code == "POINCARE_CHALLENGE":
            return "Бонус за секретное задание начислен"
        return f"Промокод активирован: {code}"
    return REASON_LABELS.get(value, value)


def format_funny_tickets(amount: int | None) -> str:
    if amount is None:
        return "-"
    sign = "-" if amount < 0 else ""
    absolute = abs(int(amount))
    last_two = absolute % 100
    last_digit = absolute % 10
    if 11 <= last_two <= 14:
        word = "билетов"
    elif last_digit == 1:
        word = "билет"
    elif 2 <= last_digit <= 4:
        word = "билета"
    else:
        word = "билетов"
    return f"{sign}{absolute} {word} банка приколов"


def format_signed_funny_tickets(amount: int | None) -> str:
    if amount is None:
        return "-"
    value = int(amount)
    if value > 0:
        return f"+{format_funny_tickets(value)}"
    return format_funny_tickets(value)


def format_datetime_short(value: Any) -> str:
    if not value:
        return "—"
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        normalized = value.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return value
    else:
        return str(value)
    return parsed.strftime("%d.%m.%Y %H:%M")


def format_probability(value: Any) -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value):.1%}"
    except (TypeError, ValueError):
        return str(value)


def format_prediction_label(value: Any) -> str:
    if value is None:
        return "—"
    if int(value) == 1:
        return "отмена вероятна"
    if int(value) == 0:
        return "отмена не ожидается"
    return str(value)


def format_model_label(name: Any, version: Any) -> str:
    if not name:
        return "—"
    if version:
        return f"{name} v{version}"
    return str(name)


def translate_error_message(value: str) -> str:
    if "proof_url" in value or "valid URL" in value or "URL" in value:
        return "В MVP нужно отправить ссылку на материал."
    replacements = {
        "Invalid credentials": "Неверный email или пароль.",
        "Inactive user": "Пользователь неактивен.",
        "Insufficient credits": "Недостаточно билетов банка приколов для операции.",
        "Could not validate credentials": "Не удалось проверить авторизацию. Войдите заново.",
        "Backend is unavailable. Please try again later.": "Backend недоступен. Попробуйте позже.",
    }
    return replacements.get(value, value)


def promocode_description(code: str, fallback: str | None = None) -> str:
    return PROMOCODE_DESCRIPTIONS.get(code, fallback or "-")


def localize_promocode_rows(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "Код": SECRET_CHALLENGE_TITLE
            if item.get("code") == "POINCARE_CHALLENGE"
            else item.get("code"),
            "Бонус": format_funny_tickets(item.get("credits_amount")),
            "Описание": promocode_description(
                str(item.get("code", "")),
                item.get("description"),
            ),
        }
        for item in items
    ]


def localize_prediction_rows(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for item in items:
        rows.append(
            {
                PREDICTION_COLUMNS["created_at"]: format_datetime_short(
                    item.get("created_at")
                ),
                PREDICTION_COLUMNS["completed_at"]: format_datetime_short(
                    item.get("completed_at")
                ),
                PREDICTION_COLUMNS["status"]: translate_status(item.get("status")),
                PREDICTION_COLUMNS["prediction"]: format_prediction_label(
                    item.get("prediction")
                ),
                PREDICTION_COLUMNS["cancellation_probability"]: format_probability(
                    item.get("cancellation_probability")
                ),
                PREDICTION_COLUMNS["risk_label"]: translate_risk(
                    item.get("risk_label")
                ),
                PREDICTION_COLUMNS["cost_credits"]: format_funny_tickets(
                    item.get("cost_credits")
                ),
                PREDICTION_COLUMNS["model"]: format_model_label(
                    item.get("model_name"),
                    item.get("model_version"),
                ),
                PREDICTION_COLUMNS["comment"]: item.get("error_message") or "—",
            }
        )
    return rows


def localize_transaction_rows(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for item in items:
        row = {}
        for source, target in TRANSACTION_COLUMNS.items():
            value = item.get(source)
            if source == "transaction_type":
                value = translate_transaction_type(value)
            elif source == "status":
                value = translate_status(value)
            elif source == "reason":
                value = translate_reason(value)
            elif source == "amount":
                value = format_signed_funny_tickets(value)
            elif source == "created_at":
                value = format_datetime_short(value)
            row[target] = value
        rows.append(row)
    return rows
