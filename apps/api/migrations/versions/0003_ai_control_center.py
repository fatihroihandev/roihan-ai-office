"""model_capabilities dan model_usage

Revision ID: 0003
Revises: 0002
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "model_capabilities",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("model_id", sa.String(), nullable=False),
        sa.Column("available", sa.Boolean(), nullable=False),
        sa.Column("is_paid", sa.Boolean(), nullable=False),
        sa.Column("context_limit", sa.Integer(), nullable=True),
        sa.Column("max_output", sa.Integer(), nullable=True),
        sa.Column("supports_tools", sa.Boolean(), nullable=True),
        sa.Column("supports_structured", sa.Boolean(), nullable=True),
        sa.Column("supports_vision", sa.Boolean(), nullable=True),
        sa.Column("supports_streaming", sa.Boolean(), nullable=True),
        sa.Column("cost_estimate_idr_per_1k", sa.Float(), nullable=True),
        sa.Column("validation_status", sa.String(), nullable=False),
        sa.Column("benchmark", sa.JSON(), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("refreshed_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("provider", "model_id", name="uq_model_provider_model"),
    )
    op.create_table(
        "model_usage",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("model", sa.String(), nullable=False),
        sa.Column("purpose", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("error_kind", sa.String(), nullable=True),
        sa.Column("request_id", sa.String(), nullable=True),
        sa.Column("correlation_id", sa.String(), nullable=True),
        sa.Column("prompt_sha256", sa.String(), nullable=True),
        sa.Column("prompt_chars", sa.Integer(), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("is_paid", sa.Boolean(), nullable=False),
        sa.Column("cost_idr", sa.Float(), nullable=False),
    )
    op.create_index("ix_model_usage_created", "model_usage", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_model_usage_created", table_name="model_usage")
    op.drop_table("model_usage")
    op.drop_table("model_capabilities")
