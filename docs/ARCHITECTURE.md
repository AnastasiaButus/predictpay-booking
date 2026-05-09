# PredictPay BookingGuard — архитектура

PredictPay BookingGuard — учебный production-like ML-сервис для оценки риска отмены гостиничного бронирования. ML-модель здесь намеренно остаётся простой: основная ценность проекта — сервисная архитектура вокруг модели.

Проект показывает полный путь от пользовательского запроса до асинхронного inference и фиксации результата в базе данных: REST API, PostgreSQL, JWT auth, credit billing, Celery/Redis, Streamlit dashboard, Flower, `/metrics`, structured JSON logs и coverage gate.

## 1. High-level схема

```text
Streamlit dashboard
        │
        │ REST + JWT
        ▼
FastAPI backend ─────────────── PostgreSQL
        │                         ▲
        │ Celery task             │ source of truth
        │ prediction_id only       │ users/balances/predictions/transactions
        ▼                         │
Redis broker ───────────────► Celery worker
                                  │
                                  ▼
                      trusted sklearn Pipeline artifact

FastAPI также отдаёт /metrics, а Flower показывает Celery workers/tasks.
```

## 2. Компоненты

| Компонент | Роль |
|---|---|
| `FastAPI` | API layer: health, auth, users, billing, promocodes, predictions, OpenAPI docs, request logging, `/metrics` |
| `PostgreSQL` | source of truth для пользователей, refresh tokens, model metadata, predictions, transactions, promocodes, activations |
| `SQLAlchemy + Alembic` | ORM-модели и миграции схемы |
| `Redis` | Celery broker/result backend; не хранит деньги и не является source of truth |
| `Celery worker` | асинхронно выполняет prediction tasks из очередей `default` и `priority` |
| `Streamlit` | русскоязычный REST-only dashboard для demo и защиты |
| `Flower` | локальный мониторинг Celery workers/tasks |
| `/metrics` | Prometheus-compatible metrics endpoint |
| JSON logs | structured stdout logs с `request_id` |

## 3. Auth flow

```text
register/login
      │
      ├─ password hash
      ├─ access JWT
      └─ refresh token hash in PostgreSQL
```

1. Пользователь регистрируется или входит через FastAPI.
2. Пароль хранится только как hash.
3. Access token возвращается клиенту.
4. Refresh token хранится в PostgreSQL только как `SHA-256 hash`.
5. Protected endpoints получают текущего пользователя из access token и DB.
6. Баланс, тариф и другие mutable-поля не кладутся в JWT.

## 4. Billing flow

PostgreSQL хранит два значения:

- `balance` — доступные credits;
- `reserved_balance` — credits, зарезервированные под prediction lifecycle.

```text
submit prediction
        │
        ▼
reserve
balance -= 10
reserved_balance += 10
        │
        ├── success ──► charge
        │              reserved_balance -= 10
        │              transaction: prediction_charge amount=0
        │
        └── failure ──► refund
                       reserved_balance -= 10
                       balance += 10
                       transaction: prediction_refund amount=+10
```

Все изменения баланса сопровождаются transaction records. Redis не используется для хранения баланса.

## 5. Promocode flow

1. Пользователь активирует обычный код или отправляет ответ на секретное задание.
2. Backend проверяет:
   - активность промокода;
   - срок действия;
   - лимит активаций;
   - повторную активацию тем же пользователем.
3. Успешная активация:
   - увеличивает `user.balance`;
   - увеличивает `current_activations`;
   - создаёт `promocode_activation`;
   - создаёт transaction `promo_bonus`.

Секретное задание `POINCARE_CHALLENGE` в MVP проверяет только URL-like формат ответа. Математическая корректность доказательства не проверяется.

## 6. Async prediction lifecycle

```text
POST /api/v1/predictions
        │
        ├─ validate 12-feature contract
        ├─ reject leakage columns
        ├─ check active prediction limit
        ├─ create pending prediction
        ├─ reserve 10 credits
        ├─ enqueue Celery task(prediction_id)
        ▼
Celery worker
        ├─ mark processing
        ├─ load trusted sklearn joblib artifact
        ├─ run inference
        ├─ completed + charge
        └─ failed + refund
```

Клиент не ждёт inference внутри HTTP request. Он получает `pending` и делает polling:

- `GET /api/v1/predictions/{id}`;
- `GET /api/v1/predictions/history`.

## 7. Active prediction limits

| User type | Limit | Queue |
|---|---:|---|
| `free` | 3 active predictions | `default` |
| `pro` | 10 active predictions | `priority` |
| `admin` | 10 active predictions | `priority` |

Active statuses:

```text
pending
processing
```

Проверка лимита выполняется до создания prediction row и до резервирования credits. Если лимит достигнут, API возвращает `409 Conflict`, а баланс остаётся без изменений.

## 8. ML layer

Модельный слой состоит из трёх частей:

1. `features.py` — фиксированный feature contract.
2. `train_model.py` — training script, который создаёт trusted local artifact.
3. `predictor.py` — `HotelCancellationPredictor`, который загружает artifact и выполняет inference.

Feature contract:

```text
hotel
lead_time
adults
children
previous_cancellations
booking_changes
deposit_type
customer_type
market_segment
required_car_parking_spaces
total_of_special_requests
adr
```

Leakage columns исключены и rejected:

```text
reservation_status
reservation_status_date
```

Risk labels:

```text
low    probability < 0.35
medium 0.35 <= probability < 0.65
high   probability >= 0.65
```

User-uploaded models не поддерживаются: `joblib` загружается только как trusted local artifact.

## 9. Dashboard boundaries

Dashboard — это отдельный REST API client:

- не подключается к PostgreSQL напрямую;
- не вызывает Celery напрямую;
- не импортирует backend repositories/services/Predictor;
- хранит JWT в `st.session_state`;
- показывает русские labels, но отправляет в backend canonical feature values;
- скрывает технические ID в пользовательских таблицах.

## 10. Observability

Backend отдаёт structured JSON logs в stdout.

Request logs включают:

- method;
- path template;
- status code;
- duration;
- client host;
- `request_id`.

Sensitive data не логируется:

- request bodies;
- passwords;
- JWT;
- refresh tokens;
- `Authorization` headers.

`/metrics` отдаёт Prometheus-compatible text metrics:

- `predictpay_http_requests_total`;
- `predictpay_http_request_duration_seconds`;
- `predictpay_predictions_submitted_total`;
- `predictpay_app_info`.

Flower показывает Celery workers и tasks в local/demo режиме.

## 11. Транзакционные границы и MVP-ограничения

PostgreSQL остаётся source of truth, но граница DB ↔ broker не является production-grade distributed transaction.

Текущая защита:

- enqueue failure после reserve обрабатывается refund-ом;
- completed/failed tasks являются no-op при повторной обработке;
- double charge/refund guards остаются в BillingService.

Future improvement:

- outbox pattern;
- recovery job для зависших `pending/processing` predictions;
- более строгий production-grade idempotency layer.

## 12. Что не входит в MVP

- user-uploaded models;
- real payment gateway;
- S3/MinIO model registry;
- Grafana dashboard;
- production auth для Flower;
- production-grade distributed transaction между PostgreSQL и Redis/Celery;
- CI/CD pipeline.
