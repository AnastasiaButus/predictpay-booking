from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.prediction import Prediction


class MLModel(Base):
    __tablename__ = "ml_models"
    __table_args__ = (
        UniqueConstraint("name", "version", name="uq_ml_models_name_version"),
        CheckConstraint(
            "model_type IN ('sklearn_pipeline')", name="ck_ml_models_model_type_allowed"
        ),
        CheckConstraint("length(file_path) > 0", name="ck_ml_models_file_path_not_empty"),
        Index("ix_ml_models_is_active", "is_active"),
        Index("ix_ml_models_name_version", "name", "version"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[str] = mapped_column(
        String(50), nullable=False, default="1.0.0", server_default="1.0.0"
    )
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    model_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="sklearn_pipeline",
        server_default="sklearn_pipeline",
    )
    input_schema: Mapped[dict] = mapped_column(JSONB, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    predictions: Mapped[list["Prediction"]] = relationship(back_populates="ml_model")
