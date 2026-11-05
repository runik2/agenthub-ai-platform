"""safe integration tools

Revision ID: 10d_integration_tools
Revises: 9c1_agent_memories
"""
from alembic import op
import sqlalchemy as sa

revision = "10d_integration_tools"
down_revision = "9c1_agent_memories"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("integration_tools", sa.Column("id", sa.String(36), primary_key=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("name", sa.String(120), nullable=False), sa.Column("description", sa.Text(), nullable=False), sa.Column("kind", sa.String(30), nullable=False), sa.Column("method", sa.String(10), nullable=False), sa.Column("base_url", sa.String(500), nullable=False), sa.Column("allowed_path", sa.String(300), nullable=False), sa.Column("requires_approval", sa.Boolean(), nullable=False), sa.Column("is_active", sa.Boolean(), nullable=False))
    op.create_index("ix_integration_tools_owner_id", "integration_tools", ["owner_id"])


def downgrade() -> None:
    op.drop_table("integration_tools")
