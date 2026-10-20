"""product catalog: products, product_versions, product_features, product_release_checks

Revision ID: 0007
Revises: 0006
"""
from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "products",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("line", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("target_customers", sa.Text(), nullable=True),
        sa.Column("pricing_model", sa.Text(), nullable=True),
        sa.Column("pricing_approved_value", sa.Text(), nullable=True),
        sa.Column("pricing_approved_by", sa.String(), nullable=True),
        sa.Column("pricing_approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("project_id", sa.String(), sa.ForeignKey("projects.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "product_versions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("product_id", sa.String(), sa.ForeignKey("products.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("version", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("release_notes", sa.Text(), nullable=True),
        sa.Column("commit", sa.String(), nullable=True),
        sa.Column("limitations", sa.JSON(), nullable=False),
        sa.Column("limitations_confirmed", sa.Boolean(), nullable=False),
        sa.Column("materials_reviewed", sa.Boolean(), nullable=False),
        sa.Column("materials_reviewed_by", sa.String(), nullable=True),
        sa.Column("materials_reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("marketing_permission", sa.String(), nullable=False),
        sa.Column("permission_granted_by", sa.String(), nullable=True),
        sa.Column("permission_granted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("permission_reason", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("product_id", "version", name="uq_product_version"),
    )
    op.create_index("ix_product_versions_product", "product_versions", ["product_id"])
    op.create_table(
        "product_features",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version_id", sa.String(), sa.ForeignKey("product_versions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("attested_by", sa.String(), nullable=True),
        sa.Column("attested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attestation_reason", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_product_features_version", "product_features", ["version_id"])
    op.create_table(
        "product_release_checks",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version_id", sa.String(), sa.ForeignKey("product_versions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("target", sa.String(), nullable=False),
        sa.Column("ready", sa.Boolean(), nullable=False),
        sa.Column("items", sa.JSON(), nullable=False),
        sa.Column("evaluated_by", sa.String(), nullable=False),
    )
    op.create_index("ix_release_checks_version", "product_release_checks", ["version_id"])


def downgrade() -> None:
    for t, i in [("product_release_checks", "ix_release_checks_version"), ("product_features", "ix_product_features_version"),
                 ("product_versions", "ix_product_versions_product")]:
        op.drop_index(i, table_name=t)
        op.drop_table(t)
    op.drop_table("products")
