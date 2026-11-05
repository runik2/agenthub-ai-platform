"""attach team members to a shared workspace

Revision ID: 19m_team_workspaces
Revises: 18l_provider_ownership
"""

from alembic import op
import sqlalchemy as sa

revision = "19m_team_workspaces"
down_revision = "18l_provider_ownership"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("workspace_id", sa.String(36), nullable=True))
    op.create_index("ix_users_workspace_id", "users", ["workspace_id"])
    op.execute("UPDATE users SET workspace_id = id WHERE role = 'admin'")
    op.execute(
        "UPDATE users SET workspace_id = "
        "(SELECT id FROM users WHERE role = 'admin' ORDER BY created_at ASC LIMIT 1) "
        "WHERE workspace_id IS NULL"
    )
    with op.batch_alter_table("users") as batch:
        batch.create_foreign_key(
            "fk_users_workspace_id_users", "users", ["workspace_id"], ["id"], ondelete="CASCADE"
        )


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_constraint("fk_users_workspace_id_users", type_="foreignkey")
        batch.drop_column("workspace_id")
