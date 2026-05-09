from time import perf_counter
from typing import Any

from app.core.exceptions import ModelMetadataNotFoundError
from app.db.session import SessionLocal
from app.ml.predictor import HotelCancellationPredictor
from app.repositories.ml_model_repository import MLModelRepository
from app.repositories.prediction_repository import PredictionRepository
from app.services.billing_service import BillingService
from app.workers.celery_app import celery_app


@celery_app.task(name="app.workers.prediction_tasks.process_prediction_task")
def process_prediction_task(prediction_id: int) -> dict[str, Any]:
    db = SessionLocal()
    try:
        predictions = PredictionRepository(db)
        prediction = predictions.get_by_id(prediction_id)
        if prediction is None:
            return {
                "prediction_id": prediction_id,
                "status": "not_found",
                "error": "Prediction not found",
            }

        if prediction.status in {"completed", "failed"}:
            return {
                "prediction_id": prediction.id,
                "status": prediction.status,
                "idempotent": True,
            }

        predictions.update_running(prediction)
        db.commit()

        started_at = perf_counter()
        try:
            model_metadata = MLModelRepository(db).get_active_default_model()
            if model_metadata is None:
                raise ModelMetadataNotFoundError(
                    "Active model metadata is not seeded. Run seed_demo_data."
                )

            predictor = HotelCancellationPredictor(model_metadata.file_path)
            result = predictor.predict_one(prediction.input_data)
            predictions.update_completed(
                prediction,
                result_payload=result,
                duration_ms=_duration_ms(started_at),
            )
            BillingService(db).confirm_prediction_charge(
                user_id=prediction.user_id,
                prediction_id=prediction.id,
                amount=prediction.cost,
            )
            return {
                "prediction_id": prediction.id,
                "status": "completed",
                "prediction": result.get("prediction"),
                "cancellation_probability": result.get("cancellation_probability"),
                "risk_label": result.get("risk_label"),
            }
        except Exception as exc:
            predictions.update_failed(
                prediction,
                error_message=str(exc),
                duration_ms=_duration_ms(started_at),
            )
            BillingService(db).refund_prediction_credits(
                user_id=prediction.user_id,
                prediction_id=prediction.id,
                amount=prediction.cost,
            )
            return {
                "prediction_id": prediction.id,
                "status": "failed",
                "error": str(exc),
            }
    finally:
        db.close()


def _duration_ms(started_at: float) -> int:
    return max(0, int((perf_counter() - started_at) * 1000))
