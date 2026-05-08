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
