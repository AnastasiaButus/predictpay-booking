# PredictPay BookingGuard

Educational production-like ML service for predicting hotel booking cancellation risk.

Current step: project skeleton, minimal FastAPI backend health endpoint, and configuration skeleton.

## Backend

Run from the repository root after installing dependencies:

```bash
python -m uvicorn app.main:app --app-dir backend --reload
```

Useful endpoints:

- `GET /health`
- `GET /docs`

## Local Docker run

```bash
docker compose up --build
```

- backend: `http://localhost:8000`
- health: `http://localhost:8000/health`
- docs: `http://localhost:8000/docs`
- postgres: `localhost:5432`
- redis: `localhost:6379`

## Database and migrations

```bash
docker compose up --build -d
docker compose exec backend alembic upgrade head
docker compose exec backend alembic current
docker compose down
```

## Testing

```bash
.\.venv\Scripts\python.exe -m pytest backend/tests
.\.venv\Scripts\python.exe -m pytest backend/tests/integration/test_health_api.py
.\.venv\Scripts\python.exe -m pytest backend/tests/integration/test_db_schema.py
```

## Auth API

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/logout`
- `GET /api/v1/users/me`

Passwords are stored as hashes. Refresh tokens are stored only as SHA-256 hashes.
Balance is not stored in JWT tokens.

## Seed demo data

```bash
docker compose up -d
docker compose exec backend alembic upgrade head
docker compose exec backend python -m app.seed.seed_demo_data
docker compose exec postgres psql -U predictpay -d predictpay -c "select name, version, is_active from ml_models;"
docker compose exec postgres psql -U predictpay -d predictpay -c "select code, credits_amount, max_activations, current_activations, is_active from promocodes;"
```

## Billing API

- `GET /api/v1/billing/balance`
- `POST /api/v1/billing/top-up`
- `GET /api/v1/billing/transactions`

`balance` is immediately available credit. `reserved_balance` is credit held for
future prediction lifecycle operations. Top-up creates a completed transaction,
and the MVP treats the payment gateway as mocked. Reserve, confirm charge, and
refund are service-level methods for future prediction processing.

## Promocodes API

- `GET /api/v1/promocodes`
- `POST /api/v1/promocodes/activate`
- `POST /api/v1/promocodes/poincare-challenge`

Seeded demo codes: `WELCOME100`, `ANISIMOV100`, `SPRINGFIELD100`, and
`POINCARE_CHALLENGE`. Activation creates a `promo_bonus` transaction and repeated
activation by the same user is blocked. The Poincare challenge validates URL
format only in the MVP; mathematical correctness is not verified.
