"""engineering: executions, test_runs, test_results

Revision ID: 0005
Revises: 0004
"""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "executions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("task_id", sa.String(), sa.ForeignKey("tasks.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("attempt_id", sa.String(), nullable=True),
        sa.Column("project_id", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("argv", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("exit_code", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("timed_out", sa.Boolean(), nullable=False),
        sa.Column("output_truncated", sa.Boolean(), nullable=False),
        sa.Column("stdout", sa.Text(), nullable=False),
        sa.Column("stderr", sa.Text(), nullable=False),
        sa.Column("sandbox", sa.String(), nullable=False),
    )
    op.create_index("ix_executions_task", "executions", ["task_id"])
    op.create_table(
        "test_runs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("task_id", sa.String(), sa.ForeignKey("tasks.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("attempt_id", sa.String(), nullable=True),
        sa.Column("execution_id", sa.String(), sa.ForeignKey("executions.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("project_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("total", sa.Integer(), nullable=False),
        sa.Column("passed", sa.Integer(), nullable=False),
        sa.Column("failed", sa.Integer(), nullable=False),
        sa.Column("errors", sa.Integer(), nullable=False),
        sa.Column("skipped", sa.Integer(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
    )
    op.create_index("ix_test_runs_task", "test_runs", ["task_id"])
    op.create_table(
        "test_results",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("test_run_id", sa.String(), sa.ForeignKey("test_runs.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("classname", sa.String(), nullable=True),
        sa.Column("outcome", sa.String(), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
    )
    op.create_index("ix_test_results_run", "test_results", ["test_run_id"])


def downgrade() -> None:
    for t, i in [("test_results", "ix_test_results_run"), ("test_runs", "ix_test_runs_task"), ("executions", "ix_executions_task")]:
        op.drop_index(i, table_name=t)
        op.drop_table(t)
