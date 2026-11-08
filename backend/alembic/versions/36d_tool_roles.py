"""per-tool role permissions"""

from alembic import op
import sqlalchemy as sa

revision = "36d_tool_roles"
down_revision = "35c_usage_users"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("integration_tools") as batch:
        batch.add_column(
            sa.Column(
                "allowed_roles",
                sa.JSON(),
                nullable=False,
                server_default='["admin", "manager", "operator"]',
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("integration_tools") as batch:
        batch.drop_column("allowed_roles")
