from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Integer, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base

if TYPE_CHECKING:
    from app.models.promocode import Promocode
    from app.models.user import User


class PromocodeActivation(Base):
    __tablename__ = "promocode_activations"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "promocode_id", name="uq_promocode_activations_user_promocode"
        ),
        Index("ix_promocode_activations_user_id", "user_id"),
        Index("ix_promocode_activations_promocode_id", "promocode_id"),
        Index("ix_promocode_activations_user_promocode", "user_id", "promocode_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    promocode_id: Mapped[int] = mapped_column(
        ForeignKey("promocodes.id", ondelete="CASCADE"), nullable=False
    )
    activated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="promocode_activations")
    promocode: Mapped["Promocode"] = relationship(back_populates="activations")
