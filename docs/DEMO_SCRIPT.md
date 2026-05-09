# PredictPay BookingGuard Demo Script

This script is the short acceptance path for the final project defense. It keeps
the demo focused on the production-like ML service architecture: API, database,
billing, async inference, dashboard, and observability.

## Quick Start

Run from the repository root:

```bash
docker compose up -d
docker compose exec backend alembic upgrade head
docker compose exec backend python -m app.seed.seed_demo_data
docker compose exec backend python -m app.ml.train_model
```

If images need to be rebuilt without pulling from Docker Hub:

```bash
docker compose build --pull=false
docker compose up -d
```

## URLs

- FastAPI docs: http://localhost:8000/docs
- Streamlit dashboard: http://localhost:8501
- Flower: http://localhost:5555
- Prometheus metrics: http://localhost:8000/metrics

## Demo Flow

1. Open the Streamlit dashboard at http://localhost:8501.
2. Register a new user or log in.
3. Open the account page and show the current balance.
4. Top up the balance with the mocked payment flow.
5. Activate `WELCOME100`.
6. Show the secret challenge page and submit a URL-like proof link.
7. Submit a hotel cancellation prediction.
8. Poll the prediction until it reaches `completed`.
9. Open transaction history and show `prediction_reserve` and
   `prediction_charge`.
10. Open Flower at http://localhost:5555 and show the Celery task/worker.
11. Open http://localhost:8000/metrics and show Prometheus-compatible metrics.
12. Show backend JSON logs:

```bash
docker compose logs backend --tail=100
```

## Optional API Smoke

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-WebRequest http://127.0.0.1:8000/metrics | Select-Object -ExpandProperty Content
docker compose logs celery_worker --tail=100
docker compose logs flower --tail=100
```

## Cleanup

```bash
docker compose down
```
