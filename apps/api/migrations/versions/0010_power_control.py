"""office power control: status global, perintah, checkpoint, pemulihan, operasi eksternal

Revision ID: 0010
Revises: 0009
"""
from alembic import op
import sqlalchemy as sa

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def _ts(name="created_at", nullable=False):
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable)


def _pk():
    return sa.Column("id", sa.String(), primary_key=True)


def upgrade() -> None:
    op.create_table(
        "power_state", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("state", sa.String(), nullable=False), sa.Column("shutdown_clean", sa.Boolean(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True), sa.Column("active_command_id", sa.String(), nullable=True),
        sa.Column("detail", sa.JSON(), nullable=True), _ts("changed_at"),
    )
    op.create_table(
        "power_commands", _pk(), _ts(),
        sa.Column("action", sa.String(), nullable=False), sa.Column("requested_by", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False), sa.Column("params", sa.JSON(), nullable=True),
        sa.Column("progress", sa.JSON(), nullable=False), sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True), _ts("finished_at", True),
    )
    op.create_table(
        "task_checkpoints", _pk(), _ts(),
        sa.Column("project_id", sa.String(), nullable=False), sa.Column("task_id", sa.String(), nullable=False),
        sa.Column("attempt_id", sa.String(), nullable=True), sa.Column("agent_role", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False), sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("task_status", sa.String(), nullable=False), sa.Column("last_step", sa.String(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False), sa.Column("payload_sha256", sa.String(), nullable=False),
        sa.Column("validation", sa.JSON(), nullable=True),
    )
    op.create_index("ix_task_checkpoints_task", "task_checkpoints", ["task_id", "created_at"])
    op.create_table(
        "recovery_log", _pk(), _ts(),
        sa.Column("command_id", sa.String(), nullable=True), sa.Column("source", sa.String(), nullable=False),
        sa.Column("task_id", sa.String(), nullable=True), sa.Column("project_id", sa.String(), nullable=True),
        sa.Column("action", sa.String(), nullable=False), sa.Column("checkpoint_id", sa.String(), nullable=True),
        sa.Column("detail", sa.JSON(), nullable=True),
    )
    op.create_index("ix_recovery_log_command", "recovery_log", ["command_id"])
    op.create_table(
        "recovery_items", _pk(), _ts(),
        sa.Column("task_id", sa.String(), nullable=True), sa.Column("project_id", sa.String(), nullable=True),
        sa.Column("kind", sa.String(), nullable=False), sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("detail", sa.JSON(), nullable=True), sa.Column("status", sa.String(), nullable=False),
        _ts("resolved_at", True), sa.Column("resolved_by", sa.String(), nullable=True), sa.Column("resolution", sa.String(), nullable=True),
    )
    op.create_index("ix_recovery_items_status", "recovery_items", ["status"])
    op.create_table(
        "external_operations", _pk(), _ts(),
        sa.Column("task_id", sa.String(), nullable=True), sa.Column("kind", sa.String(), nullable=False),
        sa.Column("idempotency_key", sa.String(), nullable=False, unique=True), sa.Column("status", sa.String(), nullable=False),
        sa.Column("payload_sha256", sa.String(), nullable=True), sa.Column("result", sa.JSON(), nullable=True), _ts("updated_at"),
    )


def downgrade() -> None:
    for t in ("external_operations", "recovery_items", "recovery_log", "task_checkpoints", "power_commands", "power_state"):
        op.drop_table(t)
