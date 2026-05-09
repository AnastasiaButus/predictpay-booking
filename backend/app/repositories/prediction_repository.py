from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.prediction import Prediction


class PredictionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_prediction(
        self,
        user_id: int,
        model_id: int,
        features: dict,
        cost_credits: int,
    ) -> Prediction:
        prediction = Prediction(
            user_id=user_id,
            model_id=model_id,
            status="pending",
            input_data=features,
            cost=cost_credits,
        )
        self.db.add(prediction)
        self.db.flush()
        return prediction

    def get_by_id(self, prediction_id: int) -> Prediction | None:
        return self.db.get(Prediction, prediction_id)

    def get_by_id_for_user(
        self,
        prediction_id: int,
        user_id: int,
    ) -> Prediction | None:
        return self.db.scalar(
            select(Prediction).where(
                Prediction.id == prediction_id,
                Prediction.user_id == user_id,
            )
        )

    def update_started(self, prediction: Prediction) -> Prediction:
        prediction.status = "processing"
        prediction.started_at = datetime.now(timezone.utc)
        self.db.flush()
        return prediction

    def update_completed(
        self,
        prediction: Prediction,
        result_payload: dict,
        duration_ms: int | None = None,
    ) -> Prediction:
        prediction.status = "completed"
        prediction.result = result_payload
        prediction.error_message = None
        prediction.duration_ms = duration_ms
        prediction.completed_at = datetime.now(timezone.utc)
        self.db.flush()
        return prediction

    def update_failed(
        self,
        prediction: Prediction,
        error_message: str,
        duration_ms: int | None = None,
    ) -> Prediction:
        prediction.status = "failed"
        prediction.error_message = error_message
        prediction.duration_ms = duration_ms
        prediction.completed_at = datetime.now(timezone.utc)
        self.db.flush()
        return prediction

    def list_by_user(
        self,
        user_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Prediction]:
        return list(
            self.db.scalars(
                select(Prediction)
                .where(Prediction.user_id == user_id)
                .order_by(Prediction.created_at.desc(), Prediction.id.desc())
                .limit(limit)
                .offset(offset)
            )
        )
