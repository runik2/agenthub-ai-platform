"""record prompt version used by evaluation runs

Revision ID: 28v_evaluation_prompt_versions
Revises: 27u_prompt_authors
"""

from alembic import op
import sqlalchemy as sa

revision = "28v_evaluation_prompt_versions"
down_revision = "27u_prompt_authors"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("evaluation_runs", recreate="always") as batch:
        batch.add_column(sa.Column("prompt_version_id", sa.String(36), nullable=True))
        batch.create_foreign_key(
            "fk_evaluation_runs_prompt_version_id",
            "prompt_versions",
            ["prompt_version_id"],
            ["id"],
            ondelete="SET NULL",
        )
    op.create_index("ix_evaluation_runs_prompt_version_id", "evaluation_runs", ["prompt_version_id"])


def downgrade() -> None:
    op.drop_index("ix_evaluation_runs_prompt_version_id", table_name="evaluation_runs")
    with op.batch_alter_table("evaluation_runs", recreate="always") as batch:
        batch.drop_constraint("fk_evaluation_runs_prompt_version_id", type_="foreignkey")
        batch.drop_column("prompt_version_id")
