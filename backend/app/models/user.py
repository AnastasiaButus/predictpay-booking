from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, DateTime, Index, Integer, String, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.prediction import Prediction
    from app.models.promocode_activation import PromocodeActivation
    from app.models.refresh_token import RefreshToken
    from app.models.transaction import Transaction


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('user', 'admin')", name="ck_users_role_allowed"),
        CheckConstraint("plan IN ('free', 'pro')", name="ck_users_plan_allowed"),
        CheckConstraint("balance >= 0", name="ck_users_balance_non_negative"),
        CheckConstraint(
            "reserved_balance >= 0", name="ck_users_reserved_balance_non_negative"
        ),
        Index("ix_users_email", "email"),
        Index("ix_users_role", "role"),
        Index("ix_users_plan", "plan"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(
        String(20), nullable=False, default="user", server_default="user"
    )
    plan: Mapped[str] = mapped_column(
        String(20), nullable=False, default="free", server_default="free"
    )
    balance: Mapped[int] = mapped_column(
        Integer, nullable=False, default=100, server_default=text("100")
    )
    reserved_balance: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    predictions: Mapped[list["Prediction"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="user")
    promocode_activations: Mapped[list["PromocodeActivation"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
