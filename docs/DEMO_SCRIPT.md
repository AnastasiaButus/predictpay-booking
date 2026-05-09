# PredictPay BookingGuard — сценарий демонстрации

Этот сценарий нужен для короткой и уверенной защиты проекта. Он фокусируется не на ML-модели как таковой, а на production-like сервисной архитектуре вокруг неё: API, база данных, биллинг, асинхронный inference, dashboard, observability и тесты.

## 1. Подготовка окружения

Запуск из корня репозитория:

```bash
docker compose build --pull=false
docker compose up -d
docker compose exec backend alembic upgrade head
docker compose exec backend python -m app.seed.seed_demo_data
docker compose exec backend python -m app.ml.train_model
```

Проверить сервисы:

```bash
docker compose ps
```

Ожидаемо подняты:

- `backend`;
- `postgres`;
- `redis`;
- `celery_worker`;
- `dashboard`;
- `flower`.

## 2. Основные URL

| Что показать | URL |
|---|---|
| Streamlit dashboard | http://localhost:8501 |
| FastAPI docs | http://localhost:8000/docs |
| Flower | http://localhost:5555 |
| Metrics | http://localhost:8000/metrics |
| Healthcheck | http://localhost:8000/health |

## 3. Короткий demo flow

### Шаг 1. Dashboard и пользовательский сценарий

Открыть:

```text
http://localhost:8501
```

Показать:

1. Регистрация нового пользователя или login.
2. Страница аккаунта.
3. Баланс в **билетах банка приколов**.
4. Mock top-up или активация `WELCOME100`.
5. Секретное задание без явного показа внутреннего кода `POINCARE_CHALLENGE`.
6. Создание прогноза отмены бронирования.
7. Polling статуса до `completed`.
8. История прогнозов без технических ID.
9. История операций с `prediction_reserve` и `prediction_charge` в пользовательском виде.

### Шаг 2. Что происходит под капотом

Пояснить:

```text
POST /api/v1/predictions
        │
        ├─ validate 12 features
        ├─ check active prediction limit
        ├─ create pending prediction
        ├─ reserve 10 credits
        ├─ enqueue Celery task
        ▼
Celery worker
        ├─ processing
        ├─ inference через trusted sklearn artifact
        ├─ completed / failed
        └─ charge / refund
```

### Шаг 3. Flower

Открыть:

```text
http://localhost:5555
```

Показать:

- worker активен;
- task `app.workers.prediction_tasks.process_prediction_task` виден;
- prediction task завершился успешно.

### Шаг 4. Metrics

Открыть:

```text
http://localhost:8000/metrics
```

Показать Prometheus-compatible metrics:

- HTTP request count;
- request duration;
- prediction submissions;
- app info.

### Шаг 5. JSON logs

Команда:

```bash
docker compose logs backend --tail=100
```

Показать:

- structured JSON logs;
- `request_id`;
- method/path/status/duration;
- отсутствие JWT/password/body в логах.

## 4. API smoke через PowerShell

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/metrics
```

Логи worker и Flower:

```bash
docker compose logs celery_worker --tail=100
docker compose logs flower --tail=100
```

## 5. Тесты и coverage

Быстрая проверка:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests
.\.venv\Scripts\python.exe -m pytest dashboard/tests
```

Формальная проверка coverage gate:

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

Последний зафиксированный результат:

```text
172 passed
TOTAL coverage: 92.76%
Required test coverage of 70% reached.
```

## 6. Что сказать про ограничения

Коротко и честно:

- модель простая, потому что фокус проекта — production-like обвязка;
- synthetic fallback нужен только для demo smoke, не для оценки качества;
- реальные `CSV`, `joblib`, metrics JSON не коммитятся;
- Flower без auth только для local/demo;
- Grafana, S3/MinIO, real payments и outbox/recovery job — future improvements.

## 7. Остановка

```bash
docker compose down
```
