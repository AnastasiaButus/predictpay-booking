from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.prediction import Prediction
    from app.models.promocode import Promocode
    from app.models.user import User


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('completed', 'failed')",
            name="ck_transactions_status_allowed",
        ),
        CheckConstraint(
            "transaction_type IN ("
            "'top_up', 'promo_bonus', 'prediction_reserve', "
            "'prediction_charge', 'prediction_refund'"
            ")",
            name="ck_transactions_type_allowed",
        ),
        CheckConstraint(
            "transaction_type != 'prediction_charge' OR amount = 0",
            name="ck_transactions_prediction_charge_amount_zero",
        ),
        Index("ix_transactions_user_id", "user_id"),
        Index("ix_transactions_user_id_created_at", "user_id", "created_at"),
        Index("ix_transactions_transaction_type", "transaction_type"),
        Index("ix_transactions_prediction_id", "prediction_id"),
        Index("ix_transactions_promocode_id", "promocode_id"),
        Index("ix_transactions_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    transaction_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="completed", server_default="completed"
    )
    reason: Mapped[str | None] = mapped_column(Text)
    prediction_id: Mapped[int | None] = mapped_column(
        ForeignKey("predictions.id", ondelete="SET NULL")
    )
    promocode_id: Mapped[int | None] = mapped_column(
        ForeignKey("promocodes.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="transactions")
    prediction: Mapped["Prediction | None"] = relationship(back_populates="transactions")
    promocode: Mapped["Promocode | None"] = relationship(back_populates="transactions")
