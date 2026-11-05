"""agent evaluation cases and runs

Revision ID: 13g_evaluations
Revises: 12f_knowledge_base
"""
from alembic import op
import sqlalchemy as sa

revision = "13g_evaluations"
down_revision = "12f_knowledge_base"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("evaluation_cases", sa.Column("id", sa.String(36), primary_key=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("agent_id", sa.String(36), sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False), sa.Column("name", sa.String(255), nullable=False), sa.Column("prompt", sa.Text(), nullable=False), sa.Column("expected", sa.Text(), nullable=False), sa.Column("enabled", sa.Boolean(), nullable=False))
    op.create_index("ix_evaluation_cases_owner_id", "evaluation_cases", ["owner_id"])
    op.create_index("ix_evaluation_cases_agent_id", "evaluation_cases", ["agent_id"])
    op.create_table("evaluation_runs", sa.Column("id", sa.String(36), primary_key=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("case_id", sa.String(36), sa.ForeignKey("evaluation_cases.id", ondelete="CASCADE"), nullable=False), sa.Column("agent_id", sa.String(36), sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False), sa.Column("status", sa.String(20), nullable=False), sa.Column("passed", sa.Boolean(), nullable=False), sa.Column("output", sa.Text(), nullable=False), sa.Column("latency_ms", sa.Integer(), nullable=False), sa.Column("cost", sa.Numeric(12, 6), nullable=False), sa.Column("error", sa.Text(), nullable=True))
    op.create_index("ix_evaluation_runs_owner_id", "evaluation_runs", ["owner_id"])
    op.create_index("ix_evaluation_runs_case_id", "evaluation_runs", ["case_id"])
    op.create_index("ix_evaluation_runs_agent_id", "evaluation_runs", ["agent_id"])


def downgrade() -> None:
    op.drop_table("evaluation_runs")
    op.drop_table("evaluation_cases")
