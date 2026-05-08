"""initial schema

Revision ID: 20260509_0001
Revises:
Create Date: 2026-05-09 00:00:00.000000
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260509_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(), nullable=False),
        sa.Column("role", sa.String(length=20), server_default="user", nullable=False),
        sa.Column("plan", sa.String(length=20), server_default="free", nullable=False),
        sa.Column("balance", sa.Integer(), server_default=sa.text("100"), nullable=False),
        sa.Column(
            "reserved_balance", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("balance >= 0", name="ck_users_balance_non_negative"),
        sa.CheckConstraint("plan IN ('free', 'pro')", name="ck_users_plan_allowed"),
        sa.CheckConstraint(
            "reserved_balance >= 0", name="ck_users_reserved_balance_non_negative"
        ),
        sa.CheckConstraint("role IN ('user', 'admin')", name="ck_users_role_allowed"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=False)
    op.create_index("ix_users_plan", "users", ["plan"], unique=False)
    op.create_index("ix_users_role", "users", ["role"], unique=False)

    op.create_table(
        "ml_models",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column(
            "version", sa.String(length=50), server_default="1.0.0", nullable=False
        ),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column(
            "model_type",
            sa.String(length=50),
            server_default="sklearn_pipeline",
            nullable=False,
        ),
        sa.Column(
            "input_schema",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("length(file_path) > 0", name="ck_ml_models_file_path_not_empty"),
        sa.CheckConstraint(
            "model_type IN ('sklearn_pipeline')", name="ck_ml_models_model_type_allowed"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", "version", name="uq_ml_models_name_version"),
    )
    op.create_index("ix_ml_models_is_active", "ml_models", ["is_active"], unique=False)
    op.create_index(
        "ix_ml_models_name_version", "ml_models", ["name", "version"], unique=False
    )

    op.create_table(
        "promocodes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("credits_amount", sa.Integer(), nullable=False),
        sa.Column(
            "max_activations", sa.Integer(), server_default=sa.text("1"), nullable=False
        ),
        sa.Column(
            "current_activations",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "credits_amount > 0", name="ck_promocodes_credits_amount_positive"
        ),
        sa.CheckConstraint(
            "current_activations <= max_activations",
            name="ck_promocodes_current_activations_lte_max",
        ),
        sa.CheckConstraint(
            "current_activations >= 0",
            name="ck_promocodes_current_activations_non_negative",
        ),
        sa.CheckConstraint(
            "max_activations > 0", name="ck_promocodes_max_activations_positive"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_promocodes_code", "promocodes", ["code"], unique=False)
    op.create_index("ix_promocodes_expires_at", "promocodes", ["expires_at"], unique=False)
    op.create_index("ix_promocodes_is_active", "promocodes", ["is_active"], unique=False)

    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(
        "ix_refresh_tokens_expires_at", "refresh_tokens", ["expires_at"], unique=False
    )
    op.create_index(
        "ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"], unique=False
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"], unique=False)

    op.create_table(
        "predictions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("model_id", sa.Integer(), nullable=False),
        sa.Column("celery_task_id", sa.String(length=255), nullable=True),
        sa.Column(
            "queue_name", sa.String(length=50), server_default="default", nullable=False
        ),
        sa.Column(
            "status", sa.String(length=20), server_default="pending", nullable=False
        ),
        sa.Column(
            "input_data",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("cost", sa.Integer(), server_default=sa.text("10"), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("cost > 0", name="ck_predictions_cost_positive"),
        sa.CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0",
            name="ck_predictions_duration_ms_non_negative",
        ),
        sa.CheckConstraint(
            "queue_name IN ('default', 'priority')",
            name="ck_predictions_queue_name_allowed",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'completed', 'failed')",
            name="ck_predictions_status_allowed",
        ),
        sa.ForeignKeyConstraint(["model_id"], ["ml_models.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("celery_task_id"),
    )
    op.create_index(
        "ix_predictions_celery_task_id", "predictions", ["celery_task_id"], unique=False
    )
    op.create_index("ix_predictions_created_at", "predictions", ["created_at"], unique=False)
    op.create_index("ix_predictions_model_id", "predictions", ["model_id"], unique=False)
    op.create_index("ix_predictions_status", "predictions", ["status"], unique=False)
    op.create_index(
        "ix_predictions_user_id_created_at",
        "predictions",
        ["user_id", "created_at"],
        unique=False,
    )
    op.create_index("ix_predictions_user_id", "predictions", ["user_id"], unique=False)
    op.create_index(
        "ix_predictions_user_id_status",
        "predictions",
        ["user_id", "status"],
        unique=False,
    )

    op.create_table(
        "promocode_activations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("promocode_id", sa.Integer(), nullable=False),
        sa.Column(
            "activated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["promocode_id"], ["promocodes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "promocode_id", name="uq_promocode_activations_user_promocode"
        ),
    )
    op.create_index(
        "ix_promocode_activations_promocode_id",
        "promocode_activations",
        ["promocode_id"],
        unique=False,
    )
    op.create_index(
        "ix_promocode_activations_user_id",
        "promocode_activations",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_promocode_activations_user_promocode",
        "promocode_activations",
        ["user_id", "promocode_id"],
        unique=False,
    )

    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("transaction_type", sa.String(length=50), nullable=False),
        sa.Column(
            "status", sa.String(length=20), server_default="completed", nullable=False
        ),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("prediction_id", sa.Integer(), nullable=True),
        sa.Column("promocode_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('completed', 'failed')",
            name="ck_transactions_status_allowed",
        ),
        sa.CheckConstraint(
            "transaction_type IN ("
            "'top_up', 'promo_bonus', 'prediction_reserve', "
            "'prediction_charge', 'prediction_refund'"
            ")",
            name="ck_transactions_type_allowed",
        ),
        sa.CheckConstraint(
            "transaction_type != 'prediction_charge' OR amount = 0",
            name="ck_transactions_prediction_charge_amount_zero",
        ),
        sa.ForeignKeyConstraint(["prediction_id"], ["predictions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["promocode_id"], ["promocodes.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_transactions_created_at", "transactions", ["created_at"], unique=False)
    op.create_index(
        "ix_transactions_prediction_id", "transactions", ["prediction_id"], unique=False
    )
    op.create_index(
        "ix_transactions_promocode_id", "transactions", ["promocode_id"], unique=False
    )
    op.create_index(
        "ix_transactions_transaction_type",
        "transactions",
        ["transaction_type"],
        unique=False,
    )
    op.create_index("ix_transactions_user_id", "transactions", ["user_id"], unique=False)
    op.create_index(
        "ix_transactions_user_id_created_at",
        "transactions",
        ["user_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_transactions_user_id_created_at", table_name="transactions")
    op.drop_index("ix_transactions_user_id", table_name="transactions")
    op.drop_index("ix_transactions_transaction_type", table_name="transactions")
    op.drop_index("ix_transactions_promocode_id", table_name="transactions")
    op.drop_index("ix_transactions_prediction_id", table_name="transactions")
    op.drop_index("ix_transactions_created_at", table_name="transactions")
    op.drop_table("transactions")

    op.drop_index(
        "ix_promocode_activations_user_promocode",
        table_name="promocode_activations",
    )
    op.drop_index("ix_promocode_activations_user_id", table_name="promocode_activations")
    op.drop_index(
        "ix_promocode_activations_promocode_id",
        table_name="promocode_activations",
    )
    op.drop_table("promocode_activations")

    op.drop_index("ix_predictions_user_id_status", table_name="predictions")
    op.drop_index("ix_predictions_user_id", table_name="predictions")
    op.drop_index("ix_predictions_user_id_created_at", table_name="predictions")
    op.drop_index("ix_predictions_status", table_name="predictions")
    op.drop_index("ix_predictions_model_id", table_name="predictions")
    op.drop_index("ix_predictions_created_at", table_name="predictions")
    op.drop_index("ix_predictions_celery_task_id", table_name="predictions")
    op.drop_table("predictions")

    op.drop_index("ix_refresh_tokens_user_id", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_token_hash", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_expires_at", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")

    op.drop_index("ix_promocodes_is_active", table_name="promocodes")
    op.drop_index("ix_promocodes_expires_at", table_name="promocodes")
    op.drop_index("ix_promocodes_code", table_name="promocodes")
    op.drop_table("promocodes")

    op.drop_index("ix_ml_models_name_version", table_name="ml_models")
    op.drop_index("ix_ml_models_is_active", table_name="ml_models")
    op.drop_table("ml_models")

    op.drop_index("ix_users_role", table_name="users")
    op.drop_index("ix_users_plan", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
