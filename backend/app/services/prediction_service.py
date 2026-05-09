from collections.abc import Callable
from time import perf_counter
from typing import Any

from sqlalchemy.orm import Session

from app.core.exceptions import ModelMetadataNotFoundError, PredictionNotFoundError
from app.ml.predictor import HotelCancellationPredictor
from app.models.prediction import Prediction
from app.repositories.ml_model_repository import MLModelRepository
from app.repositories.prediction_repository import PredictionRepository
from app.services.billing_service import BillingService


PREDICTION_COST_CREDITS = 10


class PredictionService:
    def __init__(
        self,
        db: Session,
        predictor_factory: Callable[[str], Any] = HotelCancellationPredictor,
    ) -> None:
        self.db = db
        self.predictions = PredictionRepository(db)
        self.models = MLModelRepository(db)
        self.billing = BillingService(db)
        self.predictor_factory = predictor_factory

    def create_prediction_sync(
        self,
        user_id: int,
        features: dict,
    ) -> Prediction:
        model_metadata = self.models.get_active_default_model()
        if model_metadata is None:
            raise ModelMetadataNotFoundError(
                "Active model metadata is not seeded. Run seed_demo_data."
            )

        prediction = self.predictions.create_prediction(
            user_id=user_id,
            model_id=model_metadata.id,
            features=features,
            cost_credits=PREDICTION_COST_CREDITS,
        )

        self.billing.reserve_prediction_credits(
            user_id=user_id,
            prediction_id=prediction.id,
            amount=PREDICTION_COST_CREDITS,
        )

        started_at = perf_counter()
        try:
            self.predictions.update_started(prediction)
            predictor = self.predictor_factory(model_metadata.file_path)
            result = predictor.predict_one(features)
        except Exception as exc:
            duration_ms = self._duration_ms(started_at)
            self.predictions.update_failed(prediction, str(exc), duration_ms=duration_ms)
            self.billing.refund_prediction_credits(
                user_id=user_id,
                prediction_id=prediction.id,
                amount=PREDICTION_COST_CREDITS,
            )
            raise

        duration_ms = self._duration_ms(started_at)
        self.predictions.update_completed(
            prediction,
            result_payload=result,
            duration_ms=duration_ms,
        )
        self.billing.confirm_prediction_charge(
            user_id=user_id,
            prediction_id=prediction.id,
            amount=PREDICTION_COST_CREDITS,
        )
        self.db.refresh(prediction)
        return prediction

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

    def _duration_ms(self, started_at: float) -> int:
        return max(0, int((perf_counter() - started_at) * 1000))


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
        "created_at": prediction.created_at,
        "completed_at": prediction.completed_at,
    }
