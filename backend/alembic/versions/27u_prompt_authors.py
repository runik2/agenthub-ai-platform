"""track prompt version authors

Revision ID: 27u_prompt_authors
Revises: 26t_agent_fallback_provider
"""

from alembic import op
import sqlalchemy as sa

revision = "27u_prompt_authors"
down_revision = "26t_agent_fallback_provider"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("prompt_versions", recreate="always") as batch:
        batch.add_column(sa.Column("author_id", sa.String(36), nullable=True))
        batch.create_foreign_key(
            "fk_prompt_versions_author_id",
            "users",
            ["author_id"],
            ["id"],
            ondelete="SET NULL",
        )
    op.create_index("ix_prompt_versions_author_id", "prompt_versions", ["author_id"])


def downgrade() -> None:
    op.drop_index("ix_prompt_versions_author_id", table_name="prompt_versions")
    with op.batch_alter_table("prompt_versions", recreate="always") as batch:
        batch.drop_constraint("fk_prompt_versions_author_id", type_="foreignkey")
        batch.drop_column("author_id")
