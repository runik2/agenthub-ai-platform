"""add integration execution journal

Revision ID: 31y_integration_runs
Revises: 30x_evaluation_models
"""

from alembic import op
import sqlalchemy as sa


revision = "31y_integration_runs"
down_revision = "30x_evaluation_models"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "integration_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tool_id", sa.String(36), sa.ForeignKey("integration_tools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workflow_id", sa.String(36), nullable=True),
        sa.Column("method", sa.String(10), nullable=False),
        sa.Column("url", sa.String(500), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("request_preview", sa.Text(), nullable=False, server_default=""),
        sa.Column("response_preview", sa.Text(), nullable=False, server_default=""),
        sa.Column("error", sa.Text(), nullable=True),
    )
    op.create_index("ix_integration_runs_owner_id", "integration_runs", ["owner_id"])
    op.create_index("ix_integration_runs_tool_id", "integration_runs", ["tool_id"])
    op.create_index("ix_integration_runs_workflow_id", "integration_runs", ["workflow_id"])


def downgrade() -> None:
    op.drop_table("integration_runs")
