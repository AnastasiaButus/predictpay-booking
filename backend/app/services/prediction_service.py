from collections.abc import Callable
from typing import Any

from celery.result import AsyncResult
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import (
    ActivePredictionLimitError,
    ModelMetadataNotFoundError,
    PredictionEnqueueError,
    PredictionNotFoundError,
)
from app.core.metrics import record_prediction_submitted
from app.models.prediction import Prediction
from app.models.user import User
from app.repositories.billing_repository import BillingRepository
from app.repositories.ml_model_repository import MLModelRepository
from app.repositories.prediction_repository import PredictionRepository
from app.services.billing_service import BillingService


class PredictionService:
    def __init__(
        self,
        db: Session,
        task_sender: Callable[[int, str], AsyncResult] | None = None,
    ) -> None:
        self.db = db
        self.predictions = PredictionRepository(db)
        self.models = MLModelRepository(db)
        self.billing = BillingService(db)
        self.billing_repository = BillingRepository(db)
        self.task_sender = task_sender or self._send_prediction_task

    def create_prediction_async(
        self,
        user_id: int,
        features: dict,
    ) -> Prediction:
        user = self.billing_repository.get_user(user_id)
        if user is None:
            raise PredictionNotFoundError("User not found")

        self._ensure_active_prediction_limit(user)

        model_metadata = self.models.get_active_default_model()
        if model_metadata is None:
            raise ModelMetadataNotFoundError(
                "Active model metadata is not seeded. Run seed_demo_data."
            )

        prediction = self.predictions.create_prediction(
            user_id=user.id,
            model_id=model_metadata.id,
            features=features,
            cost_credits=settings.PREDICTION_COST_CREDITS,
        )

        self.billing.reserve_prediction_credits(
            user_id=user.id,
            prediction_id=prediction.id,
            amount=settings.PREDICTION_COST_CREDITS,
        )

        queue = self._queue_for_user(user)
        try:
            async_result = self.task_sender(prediction.id, queue)
            self.predictions.update_task_enqueued(
                prediction,
                celery_task_id=async_result.id,
            )
            self.db.commit()
            record_prediction_submitted(
                queue_name=queue,
                plan=user.plan,
                status="queued",
            )
            self.db.refresh(prediction)
            return prediction
        except Exception as exc:
            self.predictions.update_failed(
                prediction,
                "Failed to enqueue prediction task",
            )
            self.billing.refund_prediction_credits(
                user_id=user.id,
                prediction_id=prediction.id,
                amount=settings.PREDICTION_COST_CREDITS,
            )
            raise PredictionEnqueueError("Failed to enqueue prediction task") from exc

    def get_prediction(self, user_id: int, prediction_id: int) -> Prediction:
        prediction = self.predictions.get_by_id_for_user(
            prediction_id=prediction_id,
            user_id=user_id,
        )
        if prediction is None:
            raise PredictionNotFoundError("Prediction not found")
        return prediction

    def list_predictions(
        self,
        user_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Prediction]:
        return self.predictions.list_by_user(user_id=user_id, limit=limit, offset=offset)

    def _ensure_active_prediction_limit(self, user: User) -> None:
        active_count = self.predictions.count_active_by_user(user.id)
        limit = self._active_prediction_limit(user)
        if active_count >= limit:
            raise ActivePredictionLimitError(
                f"Active prediction limit reached: {limit}"
            )

    def _active_prediction_limit(self, user: User) -> int:
        if user.role == "admin" or user.plan == "pro":
            return settings.PRO_ACTIVE_PREDICTION_LIMIT
        return settings.FREE_ACTIVE_PREDICTION_LIMIT

    def _queue_for_user(self, user: User) -> str:
        if user.role == "admin" or user.plan == "pro":
            return "priority"
        return "default"

    def _send_prediction_task(self, prediction_id: int, queue: str) -> AsyncResult:
        from app.workers.prediction_tasks import process_prediction_task

        return process_prediction_task.apply_async(args=[prediction_id], queue=queue)


def prediction_to_response(prediction: Prediction) -> dict[str, Any]:
    result = prediction.result or {}
    return {
        "id": prediction.id,
        "status": prediction.status,
        "prediction": result.get("prediction"),
        "cancellation_probability": result.get("cancellation_probability"),
        "risk_label": result.get("risk_label"),
        "cost_credits": prediction.cost,
        "model_name": result.get("model_name"),
        "model_version": result.get("model_version"),
        "error_message": prediction.error_message,
        "celery_task_id": prediction.celery_task_id,
        "created_at": prediction.created_at,
        "completed_at": prediction.completed_at,
    }
