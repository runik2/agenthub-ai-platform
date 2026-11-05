"""record user attribution for model usage

Revision ID: 35c_usage_users
Revises: 34b_webhook_ip_allowlist
"""

from alembic import op
import sqlalchemy as sa


revision = "35c_usage_users"
down_revision = "34b_webhook_ip_allowlist"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("llm_usage", recreate="always") as batch:
        batch.add_column(
            sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
        )
    op.create_index("ix_llm_usage_user_id", "llm_usage", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_llm_usage_user_id", table_name="llm_usage")
    with op.batch_alter_table("llm_usage", recreate="always") as batch:
        batch.drop_column("user_id")
