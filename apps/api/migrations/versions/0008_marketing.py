"""marketing: companies, lead_sources, leads, interactions, suppression, opportunities, requirements, research, outreach

Revision ID: 0008
Revises: 0007
"""
from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def _ts(name="created_at", nullable=False):
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable)


def upgrade() -> None:
    op.add_column("tasks", sa.Column("params", sa.JSON(), nullable=True))

    op.create_table(
        "companies",
        sa.Column("id", sa.String(), primary_key=True), _ts(),
        sa.Column("name", sa.String(), nullable=False), sa.Column("normalized_name", sa.String(), nullable=False),
        sa.Column("domain", sa.String(), nullable=True), sa.Column("industry", sa.String(), nullable=True),
        sa.Column("size_band", sa.String(), nullable=False), sa.Column("city", sa.String(), nullable=True),
        sa.Column("website", sa.String(), nullable=True), sa.Column("description", sa.Text(), nullable=True),
        _ts("updated_at"),
    )
    op.create_index("ix_companies_norm", "companies", ["normalized_name"])
    op.create_index("ix_companies_domain", "companies", ["domain"])

    op.create_table(
        "lead_sources",
        sa.Column("id", sa.String(), primary_key=True), _ts(),
        sa.Column("source_type", sa.String(), nullable=False), sa.Column("url", sa.Text(), nullable=True),
        sa.Column("title", sa.String(), nullable=True), _ts("collected_at"),
        sa.Column("collected_by", sa.String(), nullable=False), sa.Column("method", sa.String(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
    )

    op.create_table(
        "leads",
        sa.Column("id", sa.String(), primary_key=True), _ts(),
        sa.Column("company_id", sa.String(), sa.ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("source_id", sa.String(), sa.ForeignKey("lead_sources.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("product_id", sa.String(), sa.ForeignKey("products.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("status", sa.String(), nullable=False), sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("score_breakdown", sa.JSON(), nullable=True), sa.Column("basis", sa.String(), nullable=False),
        sa.Column("owner", sa.String(), nullable=False),
        sa.Column("contact_name", sa.String(), nullable=True), sa.Column("contact_title", sa.String(), nullable=True),
        sa.Column("contact_email", sa.String(), nullable=True), sa.Column("contact_phone", sa.String(), nullable=True),
        sa.Column("email_hash", sa.String(), nullable=True), sa.Column("do_not_contact", sa.Boolean(), nullable=False),
        _ts("forwarded_at", True), _ts("collected_at"), _ts("last_interaction_at", True), _ts("anonymized_at", True),
        sa.Column("created_by", sa.String(), nullable=False), _ts("updated_at"),
    )
    op.create_index("ix_leads_status", "leads", ["status"])
    op.create_index("ix_leads_email_hash", "leads", ["email_hash"])
    op.create_index("ix_leads_company", "leads", ["company_id"])

    op.create_table(
        "lead_interactions",
        sa.Column("id", sa.String(), primary_key=True), _ts(),
        sa.Column("lead_id", sa.String(), sa.ForeignKey("leads.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("kind", sa.String(), nullable=False), _ts("occurred_at"),
        sa.Column("summary", sa.Text(), nullable=False), sa.Column("recorded_by", sa.String(), nullable=False),
    )
    op.create_index("ix_lead_interactions_lead", "lead_interactions", ["lead_id"])

    op.create_table(
        "suppression_entries",
        sa.Column("id", sa.String(), primary_key=True), _ts(),
        sa.Column("kind", sa.String(), nullable=False), sa.Column("value_hash", sa.String(), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.UniqueConstraint("kind", "value_hash", name="uq_suppression"),
    )

    op.create_table(
        "sales_opportunities",
        sa.Column("id", sa.String(), primary_key=True), _ts(),
        sa.Column("lead_id", sa.String(), sa.ForeignKey("leads.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("title", sa.String(), nullable=False), sa.Column("stage", sa.String(), nullable=False),
        sa.Column("value_estimate_idr", sa.Integer(), nullable=True), sa.Column("won_value_idr", sa.Integer(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True), sa.Column("outcome_reason", sa.Text(), nullable=True),
        _ts("closed_at", True), sa.Column("created_by", sa.String(), nullable=False), _ts("updated_at"),
    )
    op.create_index("ix_opportunities_lead", "sales_opportunities", ["lead_id"])

    op.create_table(
        "client_requirements",
        sa.Column("id", sa.String(), primary_key=True), _ts(),
        sa.Column("opportunity_id", sa.String(), sa.ForeignKey("sales_opportunities.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("text", sa.Text(), nullable=False), sa.Column("priority", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False), sa.Column("recorded_by", sa.String(), nullable=False),
    )
    op.create_index("ix_requirements_opportunity", "client_requirements", ["opportunity_id"])

    op.create_table(
        "market_research",
        sa.Column("id", sa.String(), primary_key=True), _ts(),
        sa.Column("task_id", sa.String(), sa.ForeignKey("tasks.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("product_id", sa.String(), sa.ForeignKey("products.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("topic", sa.String(), nullable=False), sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("items", sa.JSON(), nullable=False), sa.Column("sources", sa.JSON(), nullable=False),
        sa.Column("verified_count", sa.Integer(), nullable=False), sa.Column("unverified_count", sa.Integer(), nullable=False),
    )
    op.create_index("ix_market_research_task", "market_research", ["task_id"])

    op.create_table(
        "outreach_records",
        sa.Column("id", sa.String(), primary_key=True), _ts(),
        sa.Column("lead_id", sa.String(), sa.ForeignKey("leads.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("product_id", sa.String(), sa.ForeignKey("products.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("version_id", sa.String(), nullable=True), sa.Column("task_id", sa.String(), nullable=True),
        sa.Column("channel", sa.String(), nullable=False), sa.Column("subject", sa.String(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False), sa.Column("status", sa.String(), nullable=False),
        sa.Column("claim_check", sa.JSON(), nullable=True), sa.Column("created_by", sa.String(), nullable=False),
        _ts("sent_at", True), sa.Column("sent_note", sa.Text(), nullable=True), _ts("updated_at"),
    )
    op.create_index("ix_outreach_lead", "outreach_records", ["lead_id"])


def downgrade() -> None:
    for t, i in [("outreach_records", "ix_outreach_lead"), ("market_research", "ix_market_research_task"),
                 ("client_requirements", "ix_requirements_opportunity"), ("sales_opportunities", "ix_opportunities_lead"),
                 ("lead_interactions", "ix_lead_interactions_lead")]:
        op.drop_index(i, table_name=t)
        op.drop_table(t)
    op.drop_table("suppression_entries")
    for i in ("ix_leads_company", "ix_leads_email_hash", "ix_leads_status"):
        op.drop_index(i, table_name="leads")
    op.drop_table("leads")
    op.drop_table("lead_sources")
    op.drop_index("ix_companies_domain", table_name="companies")
    op.drop_index("ix_companies_norm", table_name="companies")
    op.drop_table("companies")
    op.drop_column("tasks", "params")
