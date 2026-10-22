"""artefak SEO/analitik pemasaran dan metrik pencarian manual

Revision ID: 0011
Revises: 0010
"""
from alembic import op
import sqlalchemy as sa

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def _ts(name="created_at", nullable=False):
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable)


def upgrade() -> None:
    op.create_table(
        "marketing_artifacts", sa.Column("id", sa.String(), primary_key=True), _ts(),
        sa.Column("task_id", sa.String(), sa.ForeignKey("tasks.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("kind", sa.String(), nullable=False), sa.Column("title", sa.String(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False), sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("verified_count", sa.Integer(), nullable=False), sa.Column("unverified_count", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.String(), nullable=False), sa.Column("handed_off_task_id", sa.String(), nullable=True),
    )
    op.create_index("ix_marketing_artifacts_kind", "marketing_artifacts", ["kind", "created_at"])
    op.create_table(
        "seo_metrics", sa.Column("id", sa.String(), primary_key=True), _ts(),
        sa.Column("metric", sa.String(), nullable=False), sa.Column("value", sa.Float(), nullable=False),
        sa.Column("period", sa.String(), nullable=False), sa.Column("page", sa.String(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True), sa.Column("recorded_by", sa.String(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("seo_metrics")
    op.drop_table("marketing_artifacts")
