"""scope model providers to a workspace owner

Revision ID: 18l_provider_ownership
Revises: 17k_webhooks
"""

from alembic import op
import sqlalchemy as sa

revision = "18l_provider_ownership"
down_revision = "17k_webhooks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("llm_providers", sa.Column("owner_id", sa.String(36), nullable=True))
    op.create_index("ix_llm_providers_owner_id", "llm_providers", ["owner_id"])
    op.execute(
        "UPDATE llm_providers SET owner_id = "
        "(SELECT id FROM users ORDER BY created_at ASC LIMIT 1)"
    )
    with op.batch_alter_table("llm_providers") as batch:
        batch.alter_column("owner_id", existing_type=sa.String(36), nullable=False)
        batch.create_foreign_key(
            "fk_llm_providers_owner_id_users", "users", ["owner_id"], ["id"], ondelete="CASCADE"
        )


def downgrade() -> None:
    with op.batch_alter_table("llm_providers") as batch:
        batch.drop_constraint("fk_llm_providers_owner_id_users", type_="foreignkey")
        batch.drop_column("owner_id")
