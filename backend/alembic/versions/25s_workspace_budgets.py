"""add workspace model budgets

Revision ID: 25s_workspace_budgets
Revises: 24r_knowledge_embeddings
"""

from alembic import op
import sqlalchemy as sa

revision = "25s_workspace_budgets"
down_revision = "24r_knowledge_embeddings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("monthly_token_limit", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("users", sa.Column("monthly_cost_limit", sa.Numeric(12, 6), nullable=False, server_default="0"))
    op.add_column("users", sa.Column("budget_warning_percent", sa.Integer(), nullable=False, server_default="80"))


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_column("budget_warning_percent")
        batch.drop_column("monthly_cost_limit")
        batch.drop_column("monthly_token_limit")
