from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ml_model import MLModel


DEFAULT_MODEL_NAME = "hotel_cancellation_model"
DEFAULT_MODEL_VERSION = "1.0.0"


class MLModelRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_active_model_by_name_version(
        self,
        name: str,
        version: str,
    ) -> MLModel | None:
        return self.db.scalar(
            select(MLModel).where(
                MLModel.name == name,
                MLModel.version == version,
                MLModel.is_active.is_(True),
            )
        )

    def get_active_default_model(self) -> MLModel | None:
        return self.get_active_model_by_name_version(
            DEFAULT_MODEL_NAME,
            DEFAULT_MODEL_VERSION,
        )
