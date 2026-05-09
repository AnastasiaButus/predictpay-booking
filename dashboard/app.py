from typing import Any

import streamlit as st

from api_client import APIError, BookingGuardAPIClient
from localization import (
    CUSTOMER_TYPE_LABELS,
    DEPOSIT_TYPE_LABELS,
    HOTEL_LABELS,
    MARKET_SEGMENT_LABELS,
    ADR_HELP_TEXT,
    SECRET_CHALLENGE_MVP_NOTE,
    SECRET_CHALLENGE_TEXT,
    SECRET_CHALLENGE_TITLE,
    format_funny_tickets,
    localize_prediction_rows,
    localize_promocode_rows,
    localize_transaction_rows,
    translate_error_message,
    translate_risk,
    translate_status,
)


PAGE_LABELS = {
    "account": "Аккаунт",
    "billing": "Баланс и платежи",
    "promocodes": "Промокоды",
    "new_prediction": "Новый прогноз",
    "prediction_history": "История прогнозов",
    "transactions": "История операций",
    "about": "О проекте / Архитектура",
}


def main() -> None:
    st.set_page_config(page_title="PredictPay BookingGuard", layout="wide")
    init_state()
    client = BookingGuardAPIClient()

    st.title("PredictPay BookingGuard")
    st.caption("Сервис оценки риска отмены гостиничного бронирования")

    if not is_authenticated():
        render_auth_page(client)
        return

    render_sidebar(client)
    page_label = st.sidebar.radio("Навигация", list(PAGE_LABELS.values()))
    page = next(key for key, value in PAGE_LABELS.items() if value == page_label)

    if page == "account":
        render_account_page(client)
    elif page == "billing":
        render_billing_page(client)
    elif page == "promocodes":
        render_promocodes_page(client)
    elif page == "new_prediction":
        render_new_prediction_page(client)
    elif page == "prediction_history":
        render_prediction_history_page(client)
    elif page == "transactions":
        render_transactions_page(client)
    else:
        render_about_page()


def init_state() -> None:
    defaults = {
        "access_token": None,
        "refresh_token": None,
        "current_user": None,
        "last_prediction_id": None,
        "last_prediction_status": None,
        "last_prediction_result": None,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def is_authenticated() -> bool:
    return bool(st.session_state.access_token)


def render_auth_page(client: BookingGuardAPIClient) -> None:
    st.subheader("Вход / Регистрация")
    login_tab, register_tab = st.tabs(["Войти", "Зарегистрироваться"])

    with login_tab:
        with st.form("login_form"):
            email = st.text_input("Email", key="login_email")
            password = st.text_input("Пароль", type="password", key="login_password")
            submitted = st.form_submit_button("Войти")
        if submitted:
            try:
                tokens = client.login(email, password)
                st.session_state.access_token = tokens["access_token"]
                st.session_state.refresh_token = tokens["refresh_token"]
                st.session_state.current_user = client.get_me(tokens["access_token"])
                st.success("Вход выполнен.")
                st.rerun()
            except APIError as exc:
                st.error(translate_error_message(exc.message))

    with register_tab:
        with st.form("register_form"):
            email = st.text_input("Email", key="register_email")
            password = st.text_input("Пароль", type="password", key="register_password")
            submitted = st.form_submit_button("Зарегистрироваться")
        if submitted:
            try:
                user = client.register(email, password)
                st.success(f"Пользователь зарегистрирован: {user['email']}. Теперь можно войти.")
            except APIError as exc:
                st.error(translate_error_message(exc.message))


def render_sidebar(client: BookingGuardAPIClient) -> None:
    user = st.session_state.current_user or {}
    st.sidebar.markdown("### Сессия")
    st.sidebar.write(user.get("email", "Пользователь авторизован"))
    st.sidebar.caption(f"Роль: {user.get('role', '-')} · Тариф: {user.get('plan', '-')}")
    if st.sidebar.button("Выйти"):
        try:
            if st.session_state.refresh_token:
                client.logout(st.session_state.access_token, st.session_state.refresh_token)
        except APIError as exc:
            st.sidebar.warning(translate_error_message(exc.message))
        clear_session()
        st.rerun()


def clear_session() -> None:
    for key in (
        "access_token",
        "refresh_token",
        "current_user",
        "last_prediction_id",
        "last_prediction_status",
        "last_prediction_result",
    ):
        st.session_state[key] = None


def render_account_page(client: BookingGuardAPIClient) -> None:
    st.subheader("Аккаунт")
    if st.button("Обновить данные"):
        refresh_account(client)

    user = st.session_state.current_user or {}
    balance = safe_call(lambda: client.get_balance(token()))

    st.markdown("### Текущий пользователь")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Email", user.get("email", "-"))
        st.metric("Роль", user.get("role", "-"))
        st.metric("Тариф", user.get("plan", "-"))
    with col2:
        if balance:
            st.metric("Доступный баланс", format_funny_tickets(balance["balance"]))
            st.metric("Зарезервировано", format_funny_tickets(balance["reserved_balance"]))
        st.metric("Активен", "да" if user.get("is_active") else "нет")


def render_billing_page(client: BookingGuardAPIClient) -> None:
    st.subheader("Баланс и платежи")
    balance = safe_call(lambda: client.get_balance(token()))
    if balance:
        col1, col2 = st.columns(2)
        col1.metric("Доступный баланс", format_funny_tickets(balance["balance"]))
        col2.metric("Зарезервировано", format_funny_tickets(balance["reserved_balance"]))

    st.markdown("### Пополнить баланс")
    with st.form("top_up_form"):
        amount = st.number_input("Сумма пополнения", min_value=1, value=100, step=10)
        submitted = st.form_submit_button("Пополнить")
    if submitted:
        result = safe_call(lambda: client.top_up(token(), int(amount)))
        if result:
            st.success("Баланс пополнен.")
            st.metric("Обновлённый баланс", format_funny_tickets(result["balance"]))

    st.markdown("### Последние операции с билетами банка приколов")
    render_transactions_table(client)


def render_promocodes_page(client: BookingGuardAPIClient) -> None:
    st.subheader("Промокоды")
    st.info(
        "В учебном MVP активные промокоды показаны пользователю как демо-витрина. "
        "В production-сценарии промокоды могут быть персональными или скрытыми."
    )

    promocodes = safe_call(lambda: client.list_promocodes(token()))
    if promocodes:
        st.markdown("### Доступные промокоды")
        render_promocode_showcase(promocodes)

    with st.form("promocode_form"):
        code = st.text_input("Промокод", value="WELCOME100")
        submitted = st.form_submit_button("Активировать")
    if submitted:
        result = safe_call(lambda: client.activate_promocode(token(), code))
        if result:
            st.success(f"Промокод активирован: {result['code']}")
            st.metric("Обновлённый баланс", format_funny_tickets(result["balance"]))

    st.markdown(f"### {SECRET_CHALLENGE_TITLE}")
    st.write(SECRET_CHALLENGE_TEXT)
    st.info(SECRET_CHALLENGE_MVP_NOTE)
    with st.form("poincare_form"):
        proof_url = st.text_input(
            "Ваш ответ",
            placeholder="Введите ответ или вставьте ссылку на материал",
        )
        submitted = st.form_submit_button("Отправить ответ")
    if submitted:
        result = safe_call(lambda: client.activate_poincare_challenge(token(), proof_url))
        if result:
            st.success("Бонус за секретное задание начислен.")
            st.metric("Обновлённый баланс", format_funny_tickets(result["balance"]))


def render_promocode_showcase(promocodes: list[dict[str, Any]]) -> None:
    rows = localize_promocode_rows(promocodes)
    for index in range(0, len(rows), 2):
        columns = st.columns(2)
        for column, item in zip(columns, rows[index : index + 2]):
            with column:
                with st.container(border=True):
                    st.markdown(f"#### {item['Код']}")
                    st.metric("Бонус", f"+{item['Бонус']}")
                    st.write(item["Описание"])


def render_new_prediction_page(client: BookingGuardAPIClient) -> None:
    st.subheader("Новый прогноз")
    features = render_prediction_form()
    if features:
        result = safe_call(lambda: client.create_prediction(token(), features))
        if result:
            st.session_state.last_prediction_id = result["id"]
            st.session_state.last_prediction_status = result["status"]
            st.session_state.last_prediction_result = result
            st.success("Задача поставлена в очередь. Нажмите «Проверить статус», чтобы получить результат.")
            render_prediction_result(result)

    st.markdown("### Проверка статуса")
    if st.session_state.last_prediction_id:
        st.caption(f"Последний ID прогноза: {st.session_state.last_prediction_id}")
        col1, col2 = st.columns([1, 2])
        with col1:
            if st.button("Проверить статус"):
                result = safe_call(
                    lambda: client.get_prediction(
                        token(),
                        int(st.session_state.last_prediction_id),
                    )
                )
                if result:
                    st.session_state.last_prediction_status = result["status"]
                    st.session_state.last_prediction_result = result
                    render_prediction_status_message(result)
        with col2:
            result = st.session_state.last_prediction_result
            if result:
                render_prediction_result(result)
    else:
        st.info("Сначала отправьте прогноз.")


def render_prediction_form() -> dict[str, Any] | None:
    with st.form("prediction_form"):
        col1, col2 = st.columns(2)
        with col1:
            hotel = st.selectbox(
                "Тип отеля",
                list(HOTEL_LABELS),
                format_func=lambda value: HOTEL_LABELS.get(value, value),
            )
            deposit_type = st.selectbox(
                "Тип депозита",
                list(DEPOSIT_TYPE_LABELS),
                format_func=lambda value: DEPOSIT_TYPE_LABELS.get(value, value),
            )
            customer_type = st.selectbox(
                "Тип клиента",
                list(CUSTOMER_TYPE_LABELS),
                format_func=lambda value: CUSTOMER_TYPE_LABELS.get(value, value),
            )
            market_segment = st.selectbox(
                "Канал бронирования",
                list(MARKET_SEGMENT_LABELS),
                format_func=lambda value: MARKET_SEGMENT_LABELS.get(value, value),
            )
        with col2:
            lead_time = st.number_input("Дней до заезда", min_value=0, value=120)
            adults = st.number_input("Взрослые", min_value=0, value=2)
            children = st.number_input("Дети", min_value=0, value=0)
            previous_cancellations = st.number_input("Предыдущие отмены", min_value=0, value=1)
            booking_changes = st.number_input("Изменения бронирования", min_value=0, value=0)
            required_car_parking_spaces = st.number_input("Парковочные места", min_value=0, value=0)
            total_of_special_requests = st.number_input("Особые запросы", min_value=0, value=1)
            adr = st.number_input(
                "Средняя дневная стоимость номера, ADR",
                min_value=0.0,
                value=95.5,
                step=1.0,
                help=ADR_HELP_TEXT,
            )
            st.caption(ADR_HELP_TEXT)

        submitted = st.form_submit_button("Отправить прогноз")

    if not submitted:
        return None
    return {
        "hotel": hotel,
        "lead_time": int(lead_time),
        "adults": int(adults),
        "children": int(children),
        "previous_cancellations": int(previous_cancellations),
        "booking_changes": int(booking_changes),
        "deposit_type": deposit_type,
        "customer_type": customer_type,
        "market_segment": market_segment,
        "required_car_parking_spaces": int(required_car_parking_spaces),
        "total_of_special_requests": int(total_of_special_requests),
        "adr": float(adr),
    }


def render_prediction_status_message(result: dict[str, Any]) -> None:
    if result["status"] == "completed":
        st.success("Прогноз готов.")
        refresh_balance_note()
    elif result["status"] == "failed":
        st.error(result.get("error_message") or "Прогноз завершился ошибкой. Билеты банка приколов возвращены.")
    else:
        st.info("Прогноз ещё в очереди или обрабатывается.")


def render_prediction_result(result: dict[str, Any]) -> None:
    status = translate_status(result.get("status"))
    probability = result.get("cancellation_probability")
    risk = translate_risk(result.get("risk_label"))
    prediction = result.get("prediction")
    model_name = result.get("model_name") or "-"
    model_version = result.get("model_version") or "-"

    st.markdown("#### Результат прогноза")
    cols = st.columns(3)
    cols[0].metric("Статус", status)
    cols[1].metric("Стоимость", format_funny_tickets(result.get("cost_credits")))
    cols[2].metric("Предсказание", prediction if prediction is not None else "-")

    if probability is not None:
        st.metric("Вероятность отмены", f"{probability:.1%}")
    if result.get("risk_label"):
        st.metric("Уровень риска", risk)
    st.caption(f"Модель: {model_name} · версия {model_version}")

    with st.expander("Технический ответ API"):
        st.json(
            {
                "id": result.get("id"),
                "status": result.get("status"),
                "cost_credits": result.get("cost_credits"),
                "celery_task_id": result.get("celery_task_id"),
                "prediction": result.get("prediction"),
                "cancellation_probability": result.get("cancellation_probability"),
                "risk_label": result.get("risk_label"),
                "model_name": result.get("model_name"),
                "model_version": result.get("model_version"),
                "error_message": result.get("error_message"),
            }
        )


def render_prediction_history_page(client: BookingGuardAPIClient) -> None:
    st.subheader("История прогнозов")
    if st.button("Обновить историю прогнозов"):
        pass
    history = safe_call(lambda: client.get_prediction_history(token()))
    if history:
        render_predictions_table(history["items"])


def render_predictions_table(predictions: list[dict[str, Any]]) -> None:
    rows = localize_prediction_rows(predictions)
    st.dataframe(rows, use_container_width=True, hide_index=True)


def render_transactions_page(client: BookingGuardAPIClient) -> None:
    st.subheader("История операций с билетами банка приколов")
    if st.button("Обновить операции"):
        pass
    render_transactions_table(client)


def render_transactions_table(client: BookingGuardAPIClient) -> None:
    transactions = safe_call(lambda: client.get_transactions(token()))
    if transactions:
        st.dataframe(localize_transaction_rows(transactions["items"]), use_container_width=True)


def render_about_page() -> None:
    st.subheader("О проекте / Архитектура")
    st.markdown(
        """
        PredictPay BookingGuard — сервис оценки риска отмены гостиничного бронирования.

        - FastAPI backend — REST API.
        - PostgreSQL — источник истины для пользователей, баланса, транзакций и прогнозов.
        - Redis + Celery — асинхронная очередь для ML-инференса.
        - Streamlit — пользовательский интерфейс, который общается с backend только через REST.
        - Billing lifecycle — reserve → charge/refund.
        - ML — фиксированный trusted sklearn Pipeline.
        - MVP limitation — пользовательская загрузка joblib-моделей не поддерживается.
        """
    )


def refresh_account(client: BookingGuardAPIClient) -> None:
    result = safe_call(lambda: client.get_me(token()))
    if result:
        st.session_state.current_user = result
        st.success("Данные аккаунта обновлены.")


def refresh_balance_note() -> None:
    st.caption("Обновите страницу баланса, чтобы увидеть актуальное списание билетов банка приколов.")


def safe_call(operation):
    try:
        return operation()
    except APIError as exc:
        st.error(translate_error_message(exc.message))
        return None


def token() -> str:
    return st.session_state.access_token


if __name__ == "__main__":
    main()
