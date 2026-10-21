"""content workspace, campaigns, metrics, outbox, client handoff

Revision ID: 0009
Revises: 0008
"""
from alembic import op
import sqlalchemy as sa

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def _ts(name="created_at", nullable=False):
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable)


def _pk():
    return sa.Column("id", sa.String(), primary_key=True)


def upgrade() -> None:
    op.create_table(
        "campaigns", _pk(), _ts(),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("product_id", sa.String(), sa.ForeignKey("products.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("version_id", sa.String(), nullable=True), sa.Column("objective", sa.Text(), nullable=False),
        sa.Column("channels", sa.JSON(), nullable=False), sa.Column("status", sa.String(), nullable=False),
        _ts("starts_on", True), _ts("ends_on", True), sa.Column("budget_idr", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.String(), nullable=False), _ts("updated_at"),
    )
    op.create_table(
        "content_assets", _pk(), _ts(),
        sa.Column("campaign_id", sa.String(), sa.ForeignKey("campaigns.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("product_id", sa.String(), sa.ForeignKey("products.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("version_id", sa.String(), nullable=True), sa.Column("task_id", sa.String(), nullable=True),
        sa.Column("kind", sa.String(), nullable=False), sa.Column("channel", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False), sa.Column("body", sa.Text(), nullable=False),
        sa.Column("body_hash", sa.String(), nullable=False), sa.Column("status", sa.String(), nullable=False),
        sa.Column("claim_check", sa.JSON(), nullable=True), _ts("scheduled_for", True),
        sa.Column("created_by", sa.String(), nullable=False), _ts("updated_at"),
    )
    op.create_index("ix_content_campaign", "content_assets", ["campaign_id"])
    op.create_table(
        "campaign_metrics", _pk(), _ts(),
        sa.Column("campaign_id", sa.String(), sa.ForeignKey("campaigns.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("metric", sa.String(), nullable=False), sa.Column("value", sa.Integer(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True), sa.Column("recorded_by", sa.String(), nullable=False),
    )
    op.create_index("ix_campaign_metrics_campaign", "campaign_metrics", ["campaign_id"])
    op.create_table(
        "outbound_messages", _pk(), _ts(),
        sa.Column("kind", sa.String(), nullable=False), sa.Column("ref_id", sa.String(), nullable=False),
        sa.Column("lead_id", sa.String(), nullable=True), sa.Column("channel", sa.String(), nullable=False),
        sa.Column("subject", sa.String(), nullable=False), sa.Column("body", sa.Text(), nullable=False),
        sa.Column("body_hash", sa.String(), nullable=False), sa.Column("task_id", sa.String(), nullable=False),
        sa.Column("approval_id", sa.String(), nullable=False), sa.Column("status", sa.String(), nullable=False),
        _ts("dispatched_at", True), sa.Column("dispatched_by", sa.String(), nullable=True),
    )
    op.create_index("ix_outbound_ref", "outbound_messages", ["kind", "ref_id"])
    op.create_index("ix_outbound_lead", "outbound_messages", ["lead_id"])
    op.create_table(
        "client_handoffs", _pk(), _ts(),
        sa.Column("opportunity_id", sa.String(), sa.ForeignKey("sales_opportunities.id", ondelete="RESTRICT"), nullable=False, unique=True),
        sa.Column("project_id", sa.String(), sa.ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("requirements", sa.JSON(), nullable=False), sa.Column("task_ids", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("client_handoffs")
    for i in ("ix_outbound_lead", "ix_outbound_ref"):
        op.drop_index(i, table_name="outbound_messages")
    op.drop_table("outbound_messages")
    op.drop_index("ix_campaign_metrics_campaign", table_name="campaign_metrics")
    op.drop_table("campaign_metrics")
    op.drop_index("ix_content_campaign", table_name="content_assets")
    op.drop_table("content_assets")
    op.drop_table("campaigns")
