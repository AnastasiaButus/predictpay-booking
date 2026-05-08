from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base

if TYPE_CHECKING:
    from app.models.ml_model import MLModel
    from app.models.transaction import Transaction
    from app.models.user import User


class Prediction(Base):
    __tablename__ = "predictions"
    __table_args__ = (
        CheckConstraint(
            "queue_name IN ('default', 'priority')",
            name="ck_predictions_queue_name_allowed",
        ),
        CheckConstraint(
            "status IN ('pending', 'processing', 'completed', 'failed')",
            name="ck_predictions_status_allowed",
        ),
        CheckConstraint("cost > 0", name="ck_predictions_cost_positive"),
        CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0",
            name="ck_predictions_duration_ms_non_negative",
        ),
        Index("ix_predictions_user_id", "user_id"),
        Index("ix_predictions_model_id", "model_id"),
        Index("ix_predictions_status", "status"),
        Index("ix_predictions_user_id_status", "user_id", "status"),
        Index("ix_predictions_created_at", "created_at"),
        Index("ix_predictions_celery_task_id", "celery_task_id"),
        Index("ix_predictions_user_id_created_at", "user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    model_id: Mapped[int] = mapped_column(
        ForeignKey("ml_models.id", ondelete="RESTRICT"), nullable=False
    )
    celery_task_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    queue_name: Mapped[str] = mapped_column(
        String(50), nullable=False, default="default", server_default="default"
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", server_default="pending"
    )
    input_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    result: Mapped[dict | None] = mapped_column(JSONB)
    error_message: Mapped[str | None] = mapped_column(Text)
    cost: Mapped[int] = mapped_column(
        Integer, nullable=False, default=10, server_default=text("10")
    )
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped["User"] = relationship(back_populates="predictions")
    ml_model: Mapped["MLModel"] = relationship(back_populates="predictions")
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="prediction")
