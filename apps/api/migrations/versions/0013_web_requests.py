"""catatan permintaan web agent

Revision ID: 0013
Revises: 0012
"""
from alembic import op
import sqlalchemy as sa

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "web_requests", sa.Column("id", sa.String(), primary_key=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("kind", sa.String(), nullable=False), sa.Column("target", sa.Text(), nullable=False), sa.Column("status", sa.String(), nullable=False),
        sa.Column("bytes", sa.Integer(), nullable=False), sa.Column("detail", sa.String(), nullable=True), sa.Column("task_id", sa.String(), nullable=True),
    )
    op.create_index("ix_web_requests_created", "web_requests", ["created_at"])


def downgrade() -> None:
    op.drop_table("web_requests")
