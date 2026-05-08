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
