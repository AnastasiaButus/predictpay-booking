from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class BookingFeatures(BaseModel):
    hotel: str
    lead_time: int = Field(ge=0)
    adults: int = Field(ge=0)
    children: int = Field(ge=0)
    previous_cancellations: int = Field(ge=0)
    booking_changes: int = Field(ge=0)
    deposit_type: str
    customer_type: str
    market_segment: str
    required_car_parking_spaces: int = Field(ge=0)
    total_of_special_requests: int = Field(ge=0)
    adr: float = Field(ge=0)

    model_config = ConfigDict(extra="forbid")


class PredictionCreateRequest(BaseModel):
    features: BookingFeatures


class PredictionResponse(BaseModel):
    id: int
    status: str
    prediction: int | None
    cancellation_probability: float | None
    risk_label: str | None
    cost_credits: int
    model_name: str | None
    model_version: str | None
    error_message: str | None
    celery_task_id: str | None
    created_at: datetime
    completed_at: datetime | None


class PredictionHistoryResponse(BaseModel):
    items: list[PredictionResponse]
    limit: int
    offset: int
