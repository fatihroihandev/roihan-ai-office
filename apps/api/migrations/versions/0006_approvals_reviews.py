"""approvals, code_reviews, dan tasks.review_status

Revision ID: 0006
Revises: 0005
"""
from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("review_status", sa.String(), nullable=True))
    op.create_table(
        "approvals",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("task_id", sa.String(), sa.ForeignKey("tasks.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("project_id", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("action_type", sa.String(), nullable=False),
        sa.Column("risk_level", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("payload_hash", sa.String(), nullable=False),
        sa.Column("requested_by", sa.String(), nullable=False),
        sa.Column("decided_by", sa.String(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_reason", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_approvals_task", "approvals", ["task_id"])
    op.create_index("ix_approvals_status", "approvals", ["status"])
    op.create_table(
        "code_reviews",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("task_id", sa.String(), sa.ForeignKey("tasks.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("project_id", sa.String(), nullable=False),
        sa.Column("reviewed_task_ids", sa.JSON(), nullable=False),
        sa.Column("commit", sa.String(), nullable=True),
        sa.Column("verdict", sa.String(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("verdict_reasons", sa.JSON(), nullable=False),
        sa.Column("criteria", sa.JSON(), nullable=False),
        sa.Column("findings", sa.JSON(), nullable=False),
        sa.Column("unresolved_risks", sa.JSON(), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
    )
    op.create_index("ix_code_reviews_task", "code_reviews", ["task_id"])


def downgrade() -> None:
    op.drop_index("ix_code_reviews_task", table_name="code_reviews")
    op.drop_table("code_reviews")
    op.drop_index("ix_approvals_status", table_name="approvals")
    op.drop_index("ix_approvals_task", table_name="approvals")
    op.drop_table("approvals")
    op.drop_column("tasks", "review_status")
