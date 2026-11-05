"""store workflow step traces on task runs

Revision ID: 29w_task_run_traces
Revises: 28v_evaluation_prompt_versions
"""

from alembic import op
import sqlalchemy as sa


revision = "29w_task_run_traces"
down_revision = "28v_evaluation_prompt_versions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("task_runs", recreate="always") as batch:
        batch.add_column(sa.Column("steps", sa.JSON(), nullable=False, server_default="[]"))


def downgrade() -> None:
    with op.batch_alter_table("task_runs", recreate="always") as batch:
        batch.drop_column("steps")
