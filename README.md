# PredictPay BookingGuard

> **Сервис оценки риска отмены гостиничного бронирования**  
> Учебный production-like ML-сервис: не просто модель в ноутбуке, а полноценная сервисная обвязка вокруг ML.

PredictPay BookingGuard прогнозирует риск отмены гостиничного бронирования и показывает, как ML-модель можно упаковать в продуктовый сервис: с REST API, PostgreSQL, авторизацией, кредитным биллингом, асинхронным инференсом, UI, логами, метриками и тестами.

Главная идея проекта — не «выжать максимум из модели», а показать **production-like архитектуру вокруг ML**: модель обучается и сохраняется как trusted artifact, backend валидирует входные данные, PostgreSQL хранит состояние, Celery выполняет inference асинхронно, а Streamlit даёт понятный пользовательский интерфейс.

---

## Что реализовано

| Блок | Что внутри |
|---|---|
| Backend | `FastAPI`, REST API, `/docs`, `/health`, `/metrics` |
| База данных | `PostgreSQL` как source of truth для users, balances, transactions, predictions, promocodes, refresh tokens |
| ORM и миграции | `SQLAlchemy 2.x` + `Alembic` |
| Авторизация | `JWT access/refresh flow`, refresh-токены хранятся только как `SHA-256 hash` |
| Биллинг | баланс, `reserved_balance`, reserve → charge/refund lifecycle |
| Промокоды | `WELCOME100`, `ANISIMOV100`, `SPRINGFIELD100`, секретное задание |
| ML | `sklearn Pipeline` + `RandomForestClassifier`, 12-feature contract, leakage exclusion |
| Async inference | `Celery + Redis`, очереди `default` и `priority` |
| UI | русскоязычный `Streamlit dashboard`, REST-only клиент |
| Observability | structured JSON logs, `X-Request-ID`, Prometheus-compatible `/metrics`, `Flower` |
| Тесты | `172 passed`, coverage gate `>70%`, последняя проверка `92.76%` |

---

## Архитектура в одном взгляде

```text
                    ┌──────────────────────────────┐
                    │      Streamlit Dashboard      │
                    │  русскоязычный REST-only UI   │
                    └──────────────┬───────────────┘
                                   │ REST + JWT
                                   ▼
┌─────────────────────────────────────────────────────────────────┐
│                        FastAPI Backend                           │
│ auth │ billing │ promocodes │ predictions │ health │ metrics     │
└──────────────┬───────────────────────────────┬──────────────────┘
               │                               │
               │ SQLAlchemy                    │ Celery task:
               │                               │ prediction_id only
               ▼                               ▼
┌──────────────────────────────┐      ┌───────────────────────────┐
│          PostgreSQL           │      │       Redis broker         │
│ source of truth: users,       │      │ queues: default/priority   │
│ balances, transactions,       │      └──────────────┬────────────┘
│ predictions, promocodes       │                     │
└──────────────────────────────┘                     ▼
                                      ┌───────────────────────────┐
                                      │       Celery Worker        │
                                      │ loads trusted sklearn      │
                                      │ joblib artifact            │
                                      └──────────────┬────────────┘
                                                     │
                                                     ▼
                                      ┌───────────────────────────┐
                                      │ storage/models/*.joblib    │
                                      │ generated locally, ignored │
                                      │ by git                     │
                                      └───────────────────────────┘
```

Дополнительные точки наблюдения:

- `Flower`: `http://localhost:5555`
- `Metrics`: `http://localhost:8000/metrics`
- backend logs: structured JSON в stdout

Подробное описание архитектуры вынесено в [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md), а пошаговый сценарий показа проекта — в [`docs/DEMO_SCRIPT.md`](docs/DEMO_SCRIPT.md).

---

## Быстрый запуск через Docker Compose

Из корня репозитория:

```bash
docker compose build --pull=false
docker compose up -d
docker compose exec backend alembic upgrade head
docker compose exec backend python -m app.seed.seed_demo_data
docker compose exec backend python -m app.ml.train_model
```

После запуска:

| Сервис | URL |
|---|---|
| Backend API | http://localhost:8000 |
| Healthcheck | http://localhost:8000/health |
| Swagger / OpenAPI docs | http://localhost:8000/docs |
| Streamlit dashboard | http://localhost:8501 |
| Flower | http://localhost:5555 |
| Metrics | http://localhost:8000/metrics |
| PostgreSQL | `localhost:5432` |
| Redis | `localhost:6379` |

Остановить стек:

```bash
docker compose down
```

---

## Backend local run без Docker

После установки зависимостей:

```bash
python -m uvicorn app.main:app --app-dir backend --reload
```

Основные endpoints:

- `GET /health`
- `GET /docs`
- `GET /metrics`

---

## База данных и миграции

```bash
docker compose up --build -d
docker compose exec backend alembic upgrade head
docker compose exec backend alembic current
docker compose down
```

Схема БД создаётся через Alembic migration. `Base.metadata.create_all()` не используется как основной механизм схемы.

---

## Тесты и coverage gate

Базовые проверки:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests
.\.venv\Scripts\python.exe -m pytest dashboard/tests
.\.venv\Scripts\python.exe -m compileall backend/app backend/tests dashboard
```

Формальный coverage gate: команда падает, если покрытие ниже `70%`.

```powershell
$runId = [guid]::NewGuid().ToString("N")
$pytestTemp = Join-Path $env:TEMP "predictpay_pytest_tmp_$runId"
$pytestCache = Join-Path $env:TEMP "predictpay_pytest_cache_$runId"

.\.venv\Scripts\python.exe -m pytest backend/tests dashboard/tests `
  --cov=backend/app `
  --cov=dashboard `
  --cov-config=.coveragerc `
  --cov-report=term-missing `
  --cov-report=html:htmlcov `
  --cov-fail-under=70 `
  --basetemp "$pytestTemp" `
  -o cache_dir="$pytestCache"
```

Последняя локальная проверка:

```text
172 passed
TOTAL coverage: 92.76%
Required test coverage of 70% reached.
```

Generated coverage artifacts (`.coverage`, `htmlcov/`) игнорируются git.

---

## Auth API

| Method | Endpoint | Что делает |
|---|---|---|
| `POST` | `/api/v1/auth/register` | регистрация |
| `POST` | `/api/v1/auth/login` | login, выдача access/refresh tokens |
| `POST` | `/api/v1/auth/refresh` | обновление пары токенов |
| `POST` | `/api/v1/auth/logout` | отзыв refresh token |
| `GET` | `/api/v1/users/me` | текущий пользователь |

Security notes:

- пароли хранятся только как hash;
- refresh-токены хранятся только как `SHA-256 hash`;
- баланс, тариф и другие mutable-поля не кладутся в JWT.

---

## Seed demo data

```bash
docker compose up -d
docker compose exec backend alembic upgrade head
docker compose exec backend python -m app.seed.seed_demo_data
```

Проверка seed data:

```bash
docker compose exec postgres psql -U predictpay -d predictpay -c "select name, version, is_active from ml_models;"
docker compose exec postgres psql -U predictpay -d predictpay -c "select code, credits_amount, max_activations, current_activations, is_active from promocodes;"
```

Seed создаёт:

- metadata модели `hotel_cancellation_model`, version `1.0.0`;
- demo-промокоды `WELCOME100`, `ANISIMOV100`, `SPRINGFIELD100`, `POINCARE_CHALLENGE`.

---

## Billing API

| Method | Endpoint | Что делает |
|---|---|---|
| `GET` | `/api/v1/billing/balance` | текущий баланс |
| `POST` | `/api/v1/billing/top-up` | mock-пополнение |
| `GET` | `/api/v1/billing/transactions` | история операций |

В UI баланс и стоимость показываются как **билеты банка приколов**. В backend остаётся техническая терминология:

- `balance` — доступные credits;
- `reserved_balance` — credits, зарезервированные под prediction lifecycle;
- `transactions` — аудит всех операций.

### Billing lifecycle

```text
submit prediction
        │
        ▼
reserve 10 tickets
balance -= 10
reserved_balance += 10
        │
        ├── worker success ──► charge
        │                      reserved_balance -= 10
        │                      transaction: prediction_charge amount=0
        │
        └── worker failure ──► refund
                               reserved_balance -= 10
                               balance += 10
                               transaction: prediction_refund amount=+10
```

PostgreSQL остаётся source of truth для баланса и статуса prediction. Redis не используется как хранилище денег или состояния пользователя.

---

## Promocodes API

| Method | Endpoint | Что делает |
|---|---|---|
| `GET` | `/api/v1/promocodes` | активные demo-промокоды |
| `POST` | `/api/v1/promocodes/activate` | активация обычного промокода |
| `POST` | `/api/v1/promocodes/poincare-challenge` | секретное задание |

Demo codes:

- `WELCOME100` — приветственный бонус.
- `ANISIMOV100` — пасхалка в честь преподавателя курса.
- `SPRINGFIELD100` — пасхалка для тех, кто узнал город и стиль аватарки преподавателя.
- `POINCARE_CHALLENGE` — внутреннее имя секретного задания.

Activation creates `promo_bonus` transaction. Repeated activation by the same user is blocked.

### Секретное задание

В UI пользователь не видит имя `POINCARE_CHALLENGE`. Он видит задание в духе:

> Докажите, что всякое замкнутое односвязное трёхмерное многообразие гомеоморфно трёхмерной сфере.

MVP не проверяет математическую корректность доказательства: backend валидирует только URL-like формат ответа. Это demo easter egg, а не настоящий proof checker.

---

## ML training pipeline

MVP использует фиксированный trusted `sklearn` model artifact, созданный локальным training script. User-uploaded models не поддерживаются.

Feature contract содержит 12 признаков:

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

Leakage columns исключены из обучения и rejected на inference:

```text
reservation_status
reservation_status_date
```

### Local training

```bash
cd backend
..\.venv\Scripts\python.exe -m app.ml.train_model
cd ..
```

### Docker training

```bash
docker compose build backend
docker compose up -d
docker compose exec backend python -m app.ml.train_model
```

Можно положить реальный датасет локально:

```text
backend/data/hotel_bookings.csv
```

Если файла нет, training script использует маленький synthetic fallback dataset. Это нужно только для воспроизводимого demo smoke. Метрики на synthetic fallback нельзя интерпретировать как качество модели.

Для обучения на реальных данных:

1. Скачать Hotel Booking Demand dataset с Kaggle вручную.
2. Положить `hotel_bookings.csv` в `backend/data/hotel_bookings.csv`.
3. Запустить `python -m app.ml.train_model` из папки `backend`.
4. Проверить `storage/models/hotel_cancellation_model_metrics.json`.

Generated `joblib`, metrics JSON и CSV игнорируются git.

---

## Predictor

`HotelCancellationPredictor` загружает trusted local joblib artifact:

```text
storage/models/hotel_cancellation_model.joblib
```

Joblib artifacts должны быть только локальными trusted artifacts. User-uploaded joblib files в MVP не поддерживаются.

Создать artifact:

```bash
cd backend
..\.venv\Scripts\python.exe -m app.ml.train_model --data-path data/hotel_bookings.csv
cd ..
```

Predictor:

- валидирует 12-feature contract;
- rejects extra fields;
- rejects leakage columns;
- приводит numeric fields к числам;
- возвращает structured result: `prediction`, `cancellation_probability`, `risk_label`, `model_name`, `model_version`, `features_used`.

Risk labels:

```text
low    probability < 0.35
medium 0.35 <= probability < 0.65
high   probability >= 0.65
```

---

## Prediction API

| Method | Endpoint | Что делает |
|---|---|---|
| `POST` | `/api/v1/predictions` | создать async prediction task |
| `GET` | `/api/v1/predictions/{id}` | получить статус/результат |
| `GET` | `/api/v1/predictions/history` | история прогнозов пользователя |

Стоимость одного прогноза:

```text
10 билетов банка приколов
```

Prediction lifecycle:

```text
POST /api/v1/predictions
        │
        ├─ validate 12 features
        ├─ check active prediction limit
        ├─ create pending prediction
        ├─ reserve 10 credits
        ├─ enqueue Celery task
        ▼
GET /api/v1/predictions/{id}
        │
        ├─ pending
        ├─ processing
        ├─ completed
        └─ failed
```

Active prediction limits:

| User type | Active predictions |
|---|---:|
| free | 3 |
| pro | 10 |
| admin | 10 |

Active statuses: `pending`, `processing`.

Если лимит достигнут, API возвращает `409 Conflict`; prediction row не создаётся, credits не резервируются.

Queue selection:

| User type | Queue |
|---|---|
| free | `default` |
| pro/admin | `priority` |

Redis используется только как Celery broker/result backend. PostgreSQL остаётся source of truth для баланса и статуса prediction.

---

## Dashboard

`Streamlit dashboard` — русскоязычный MVP-интерфейс для demo и защиты.

Важно:

- dashboard ходит в backend только через REST API;
- dashboard не подключается напрямую к PostgreSQL;
- dashboard не вызывает Celery напрямую;
- dashboard не импортирует backend repositories/services/Predictor;
- JWT хранится в `st.session_state`;
- технические ID скрыты из пользовательских таблиц;
- даты в UI показываются в коротком формате;
- баланс и стоимости показываются как **билеты банка приколов**;
- categorical feature values отображаются по-русски, но в backend отправляются canonical values: `City Hotel`, `No Deposit`, `Transient`, `Online TA` и другие.

Запуск:

```bash
docker compose up -d
docker compose exec backend alembic upgrade head
docker compose exec backend python -m app.seed.seed_demo_data
docker compose exec backend python -m app.ml.train_model
```

Открыть:

```text
http://localhost:8501
```

Promocodes в UI показаны как MVP demo showcase. В production-сценарии промокоды могли бы быть таргетированными, скрытыми или раздаваться через внешние marketing channels.

---

## Observability / Ops

| Что | URL |
|---|---|
| Backend docs | http://localhost:8000/docs |
| Metrics | http://localhost:8000/metrics |
| Dashboard | http://localhost:8501 |
| Flower | http://localhost:5555 |

Useful commands:

```bash
docker compose up -d
docker compose ps
docker compose logs backend --tail=100
docker compose logs celery_worker --tail=100
docker compose logs flower --tail=100
```

PowerShell smoke:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/metrics
```

### JSON logs

Backend logs are structured JSON logs written to stdout.

HTTP request logs include:

- method;
- path template;
- status code;
- duration;
- client host;
- `request_id`.

If request includes `X-Request-ID`, backend preserves it. Otherwise it generates one and returns it in response headers.

Sensitive data is intentionally not logged:

- request bodies;
- passwords;
- JWT;
- refresh tokens;
- `Authorization` headers.

### Metrics

`/metrics` exposes Prometheus-compatible text metrics:

- HTTP request count;
- HTTP request duration;
- queued prediction submissions;
- app info.

Metrics не содержат `user`, `email`, `user_id` labels.

### Flower

Flower доступен локально:

```text
http://localhost:5555
```

Flower показывает Celery workers и tasks.

Security note: Flower runs without authentication in this MVP and is intended for local/demo mode only.

---

## Что не входит в MVP

Осознанные ограничения:

- нет user-uploaded models;
- нет real payment gateway;
- нет S3/MinIO для model registry;
- нет Grafana dashboard;
- нет production-grade distributed transaction между DB и broker;
- Flower без auth — только local/demo;
- synthetic dataset fallback — только smoke-check, не показатель качества модели.

---

## Возможные улучшения

- Grafana dashboard поверх `/metrics`.
- S3/MinIO или model registry для хранения model artifacts.
- Outbox pattern или recovery job для зависших `pending/processing` predictions.
- Real payment integration.
- Admin UI для управления пользователями, промокодами и моделями.
- CI/CD pipeline.
- Production auth для Flower/ops endpoints.
