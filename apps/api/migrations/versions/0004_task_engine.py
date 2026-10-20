"""task engine: tasks, dependencies, attempts, events, routing decisions

Revision ID: 0004
Revises: 0003
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tasks",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("project_id", sa.String(), sa.ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("parent_task_id", sa.String(), sa.ForeignKey("tasks.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("action_type", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("acceptance_criteria", sa.JSON(), nullable=False),
        sa.Column("risk_level", sa.String(), nullable=False),
        sa.Column("requires_approval", sa.Boolean(), nullable=False),
        sa.Column("approved", sa.Boolean(), nullable=False),
        sa.Column("difficulty_factors", sa.JSON(), nullable=True),
        sa.Column("difficulty_score", sa.Float(), nullable=True),
        sa.Column("difficulty_category", sa.String(), nullable=True),
        sa.Column("preferred_model", sa.String(), nullable=True),
        sa.Column("requires_tools", sa.Boolean(), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("attempts_baseline", sa.Integer(), nullable=False),
        sa.Column("max_retries", sa.Integer(), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("blocked_reason", sa.String(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("last_error_kind", sa.String(), nullable=True),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("verification", sa.JSON(), nullable=True),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_tasks_status", "tasks", ["status"])
    op.create_index("ix_tasks_project", "tasks", ["project_id"])
    op.create_table(
        "task_dependencies",
        sa.Column("task_id", sa.String(), sa.ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("depends_on_id", sa.String(), sa.ForeignKey("tasks.id", ondelete="RESTRICT"), primary_key=True),
    )
    op.create_table(
        "task_attempts",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("task_id", sa.String(), sa.ForeignKey("tasks.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("error_kind", sa.String(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("retryable", sa.Boolean(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider", sa.String(), nullable=True),
        sa.Column("model", sa.String(), nullable=True),
        sa.Column("usage", sa.JSON(), nullable=True),
    )
    op.create_index("ix_task_attempts_task", "task_attempts", ["task_id"])
    op.create_table(
        "task_events",
        sa.Column("seq", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("task_id", sa.String(), nullable=False),
        sa.Column("project_id", sa.String(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("from_status", sa.String(), nullable=True),
        sa.Column("to_status", sa.String(), nullable=True),
        sa.Column("reason", sa.String(), nullable=True),
        sa.Column("actor", sa.String(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sqlite_autoincrement=True,
    )
    op.create_index("ix_task_events_task", "task_events", ["task_id"])
    op.create_table(
        "routing_decisions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("task_id", sa.String(), sa.ForeignKey("tasks.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("attempt_id", sa.String(), nullable=True),
        sa.Column("difficulty_score", sa.Float(), nullable=True),
        sa.Column("difficulty_category", sa.String(), nullable=True),
        sa.Column("risk_level", sa.String(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("model", sa.String(), nullable=False),
        sa.Column("num_ctx", sa.Integer(), nullable=False),
        sa.Column("candidates", sa.JSON(), nullable=False),
        sa.Column("reasons", sa.JSON(), nullable=False),
    )
    op.create_index("ix_routing_task", "routing_decisions", ["task_id"])


def downgrade() -> None:
    for t, i in [("routing_decisions", "ix_routing_task"), ("task_events", "ix_task_events_task"),
                 ("task_attempts", "ix_task_attempts_task")]:
        op.drop_index(i, table_name=t)
        op.drop_table(t)
    op.drop_table("task_dependencies")
    op.drop_index("ix_tasks_project", table_name="tasks")
    op.drop_index("ix_tasks_status", table_name="tasks")
    op.drop_table("tasks")
