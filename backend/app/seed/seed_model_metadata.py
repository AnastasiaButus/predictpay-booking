from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ml_model import MLModel


MODEL_FEATURES = [
    "hotel",
    "lead_time",
    "adults",
    "children",
    "previous_cancellations",
    "booking_changes",
    "deposit_type",
    "customer_type",
    "market_segment",
    "required_car_parking_spaces",
    "total_of_special_requests",
    "adr",
]

MODEL_INPUT_SCHEMA = {
    "features": MODEL_FEATURES,
    "target": "is_canceled",
    "leakage_excluded": ["reservation_status", "reservation_status_date"],
}

MODEL_METADATA = {
    "name": "hotel_cancellation_model",
    "version": "1.0.0",
    "file_path": "storage/models/hotel_cancellation_model.joblib",
    "model_type": "sklearn_pipeline",
    "input_schema": MODEL_INPUT_SCHEMA,
    "is_active": True,
}


def seed_model_metadata(db: Session) -> MLModel:
    model = db.scalar(
        select(MLModel).where(
            MLModel.name == MODEL_METADATA["name"],
            MLModel.version == MODEL_METADATA["version"],
        )
    )

    if model is None:
        model = MLModel(**MODEL_METADATA)
        db.add(model)
    else:
        model.file_path = MODEL_METADATA["file_path"]
        model.model_type = MODEL_METADATA["model_type"]
        model.input_schema = MODEL_METADATA["input_schema"]
        model.is_active = MODEL_METADATA["is_active"]

    db.flush()
    return model
