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
    "Reserved credits for prediction": "Резерв credits под прогноз",
    "Prediction charge confirmed": "Списание за прогноз подтверждено",
    "Prediction failed, credits refunded": "Credits за прогноз возвращены",
    "Poincaré challenge bonus activated": "Бонус POINCARE_CHALLENGE начислен",
}

PROMOCODE_DESCRIPTIONS = {
    "WELCOME100": "Приветственный бонус: +100 credits.",
    "ANISIMOV100": "Пасхалка курса в честь преподавателя: Анисимов Ян Олегович.",
    "SPRINGFIELD100": "Мультяшная пасхалка для демо.",
    "POINCARE_CHALLENGE": "Бонус за ссылку на доказательство гипотезы Пуанкаре.",
}

PREDICTION_COLUMNS = {
    "id": "ID",
    "status": "Статус",
    "prediction": "Прогноз",
    "cancellation_probability": "Вероятность отмены",
    "risk_label": "Риск",
    "cost_credits": "Стоимость, credits",
    "model_name": "Модель",
    "model_version": "Версия модели",
    "error_message": "Ошибка",
    "celery_task_id": "ID Celery-задачи",
    "created_at": "Создано",
    "completed_at": "Завершено",
}

TRANSACTION_COLUMNS = {
    "id": "ID",
    "amount": "Сумма",
    "transaction_type": "Тип операции",
    "status": "Статус",
    "reason": "Причина",
    "prediction_id": "ID прогноза",
    "promocode_id": "ID промокода",
    "created_at": "Создано",
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
        return f"Промокод активирован: {code}"
    return REASON_LABELS.get(value, value)


def translate_error_message(value: str) -> str:
    replacements = {
        "Invalid credentials": "Неверный email или пароль.",
        "Inactive user": "Пользователь неактивен.",
        "Insufficient credits": "Недостаточно credits для операции.",
        "Could not validate credentials": "Не удалось проверить авторизацию. Войдите заново.",
        "Backend is unavailable. Please try again later.": "Backend недоступен. Попробуйте позже.",
    }
    return replacements.get(value, value)


def promocode_description(code: str, fallback: str | None = None) -> str:
    return PROMOCODE_DESCRIPTIONS.get(code, fallback or "-")


def localize_promocode_rows(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "Код": item.get("code"),
            "Бонус": item.get("credits_amount"),
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
        row = {}
        for source, target in PREDICTION_COLUMNS.items():
            value = item.get(source)
            if source == "status":
                value = translate_status(value)
            elif source == "risk_label":
                value = translate_risk(value)
            row[target] = value
        rows.append(row)
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
            row[target] = value
        rows.append(row)
    return rows
