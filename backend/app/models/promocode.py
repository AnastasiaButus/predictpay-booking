from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.promocode_activation import PromocodeActivation
    from app.models.transaction import Transaction


class Promocode(Base):
    __tablename__ = "promocodes"
    __table_args__ = (
        CheckConstraint("credits_amount > 0", name="ck_promocodes_credits_amount_positive"),
        CheckConstraint("max_activations > 0", name="ck_promocodes_max_activations_positive"),
        CheckConstraint(
            "current_activations >= 0",
            name="ck_promocodes_current_activations_non_negative",
        ),
        CheckConstraint(
            "current_activations <= max_activations",
            name="ck_promocodes_current_activations_lte_max",
        ),
        Index("ix_promocodes_code", "code"),
        Index("ix_promocodes_is_active", "is_active"),
        Index("ix_promocodes_expires_at", "expires_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    credits_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    max_activations: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )
    current_activations: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    activations: Mapped[list["PromocodeActivation"]] = relationship(
        back_populates="promocode", cascade="all, delete-orphan"
    )
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="promocode")
