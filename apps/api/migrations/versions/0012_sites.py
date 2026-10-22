"""situs web yang dipasarkan Marketing/SEO

Revision ID: 0012
Revises: 0011
"""
from alembic import op
import sqlalchemy as sa

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sites", sa.Column("id", sa.String(), primary_key=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("name", sa.String(), nullable=False), sa.Column("url", sa.String(), nullable=False),
        sa.Column("project_id", sa.String(), sa.ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("language", sa.String(), nullable=False), sa.Column("source_origin", sa.String(), nullable=True), sa.Column("status", sa.String(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("sites")
