"""add agent fallback model provider

Revision ID: 26t_agent_fallback_provider
Revises: 25s_workspace_budgets
"""

from alembic import op
import sqlalchemy as sa

revision = "26t_agent_fallback_provider"
down_revision = "25s_workspace_budgets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("agents", recreate="always") as batch:
        batch.add_column(sa.Column("fallback_provider_id", sa.String(36), nullable=True))
        batch.create_foreign_key(
            "fk_agents_fallback_provider_id",
            "llm_providers",
            ["fallback_provider_id"],
            ["id"],
            ondelete="SET NULL",
        )
    op.create_index("ix_agents_fallback_provider_id", "agents", ["fallback_provider_id"])


def downgrade() -> None:
    op.drop_index("ix_agents_fallback_provider_id", table_name="agents")
    with op.batch_alter_table("agents", recreate="always") as batch:
        batch.drop_constraint("fk_agents_fallback_provider_id", type_="foreignkey")
        batch.drop_column("fallback_provider_id")
