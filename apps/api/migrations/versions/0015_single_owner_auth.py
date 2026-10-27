"""Single-owner authentication and active session tables (Addendum v2.1)

Revision ID: 0015
Revises: 0014
"""
from alembic import op
import sqlalchemy as sa

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "owner_users",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=100), nullable=False, server_default="Owner"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_login_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_owner_users_email", "owner_users", ["email"], unique=True)

    op.create_table(
        "owner_sessions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("user_id", sa.String(), sa.ForeignKey("owner_users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_token", sa.String(length=128), nullable=False),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=255), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_owner_sessions_user_id", "owner_sessions", ["user_id"])
    op.create_index("ix_owner_sessions_token", "owner_sessions", ["session_token"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_owner_sessions_token", table_name="owner_sessions")
    op.drop_index("ix_owner_sessions_user_id", table_name="owner_sessions")
    op.drop_table("owner_sessions")

    op.drop_index("ix_owner_users_email", table_name="owner_users")
    op.drop_table("owner_users")
