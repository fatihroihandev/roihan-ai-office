"""campaign SEO, approved keywords, and append-only campaign history

Revision ID: 0014
Revises: 0013
"""
from alembic import op
import sqlalchemy as sa

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "seo_campaigns",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("website_url", sa.String(length=1000), nullable=False),
        sa.Column("allowed_domains", sa.JSON(), nullable=False),
        sa.Column("site_id", sa.String(), sa.ForeignKey("sites.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("project_id", sa.String(), sa.ForeignKey("projects.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("target_country", sa.String(length=80), nullable=True),
        sa.Column("target_language", sa.String(length=40), nullable=True),
        sa.Column("target_location", sa.String(length=160), nullable=True),
        sa.Column("primary_keywords", sa.JSON(), nullable=False),
        sa.Column("objective", sa.Text(), nullable=False),
        sa.Column("target_value", sa.Float(), nullable=True),
        sa.Column("baseline", sa.JSON(), nullable=False),
        sa.Column("baseline_source", sa.Text(), nullable=False),
        sa.Column("starts_on", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_on", sa.DateTime(timezone=True), nullable=True),
        sa.Column("api_budget_idr", sa.Integer(), nullable=False),
        sa.Column("external_budget_idr", sa.Integer(), nullable=False),
        sa.Column("autonomy", sa.String(), nullable=False),
        sa.Column("approval_policy", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_seo_campaigns_status", "seo_campaigns", ["status", "created_at"])
    op.create_table(
        "seo_keywords",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("campaign_id", sa.String(), sa.ForeignKey("seo_campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("keyword", sa.String(length=240), nullable=False),
        sa.Column("intent", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("target_page", sa.String(length=1000), nullable=True),
        sa.Column("volume", sa.Integer(), nullable=True),
        sa.Column("competition", sa.String(length=80), nullable=True),
        sa.Column("evidence_quote", sa.Text(), nullable=False),
        sa.Column("approval_status", sa.String(), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("campaign_id", "keyword", name="uq_seo_keyword_campaign_text"),
    )
    op.create_index("ix_seo_keywords_campaign", "seo_keywords", ["campaign_id", "approval_status"])
    op.create_table(
        "seo_campaign_events",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("campaign_id", sa.String(), sa.ForeignKey("seo_campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(length=80), nullable=False),
        sa.Column("actor", sa.String(), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
    )
    op.create_index("ix_seo_campaign_events_campaign", "seo_campaign_events", ["campaign_id", "created_at"])
    op.create_table(
        "seo_recommendations",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("campaign_id", sa.String(), sa.ForeignKey("seo_campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("artifact_id", sa.String(), sa.ForeignKey("marketing_artifacts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("finding_id", sa.String(length=100), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("severity", sa.String(length=30), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("recommendation", sa.Text(), nullable=False),
        sa.Column("impact_basis", sa.String(), nullable=False),
        sa.Column("confidence", sa.String(), nullable=False),
        sa.Column("effort", sa.String(), nullable=False),
        sa.Column("risk", sa.String(), nullable=False),
        sa.Column("dependencies", sa.JSON(), nullable=False),
        sa.Column("acceptance_criteria", sa.JSON(), nullable=False),
        sa.Column("verification_method", sa.Text(), nullable=False),
        sa.Column("priority_order", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("decision_note", sa.Text(), nullable=True),
        sa.UniqueConstraint("campaign_id", "artifact_id", "finding_id", name="uq_seo_recommendation_finding"),
    )
    op.create_index("ix_seo_recommendations_campaign", "seo_recommendations", ["campaign_id", "status", "priority_order"])


def downgrade() -> None:
    op.drop_table("seo_recommendations")
    op.drop_table("seo_campaign_events")
    op.drop_table("seo_keywords")
    op.drop_table("seo_campaigns")
