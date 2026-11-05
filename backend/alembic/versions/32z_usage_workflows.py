"""record workflow id for model usage

Revision ID: 32z_usage_workflows
Revises: 31y_integration_runs
"""

from alembic import op
import sqlalchemy as sa


revision = "32z_usage_workflows"
down_revision = "31y_integration_runs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("llm_usage", recreate="always") as batch:
        batch.add_column(sa.Column("workflow_id", sa.String(36), nullable=True))
    op.create_index("ix_llm_usage_workflow_id", "llm_usage", ["workflow_id"])


def downgrade() -> None:
    op.drop_index("ix_llm_usage_workflow_id", table_name="llm_usage")
    with op.batch_alter_table("llm_usage", recreate="always") as batch:
        batch.drop_column("workflow_id")
