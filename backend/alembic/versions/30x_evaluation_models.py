"""record provider and model used by evaluation runs

Revision ID: 30x_evaluation_models
Revises: 29w_task_run_traces
"""

from alembic import op
import sqlalchemy as sa


revision = "30x_evaluation_models"
down_revision = "29w_task_run_traces"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("evaluation_runs", recreate="always") as batch:
        batch.add_column(sa.Column("provider_id", sa.String(36), nullable=True))
        batch.add_column(sa.Column("model_name", sa.String(255), nullable=False, server_default=""))
        batch.create_foreign_key(
            "fk_evaluation_runs_provider_id", "llm_providers", ["provider_id"], ["id"], ondelete="SET NULL"
        )
    op.create_index("ix_evaluation_runs_provider_id", "evaluation_runs", ["provider_id"])


def downgrade() -> None:
    op.drop_index("ix_evaluation_runs_provider_id", table_name="evaluation_runs")
    with op.batch_alter_table("evaluation_runs", recreate="always") as batch:
        batch.drop_column("model_name")
        batch.drop_column("provider_id")
