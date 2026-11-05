"""prompt version history

Revision ID: 11e_prompt_versions
Revises: 10d_integration_tools
"""
from alembic import op
import sqlalchemy as sa

revision = "11e_prompt_versions"
down_revision = "10d_integration_tools"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("prompt_versions", sa.Column("id", sa.String(36), primary_key=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("agent_id", sa.String(36), sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False), sa.Column("version", sa.Integer(), nullable=False), sa.Column("system_prompt", sa.Text(), nullable=False), sa.Column("note", sa.String(255), nullable=False))
    op.create_index("ix_prompt_versions_owner_id", "prompt_versions", ["owner_id"])
    op.create_index("ix_prompt_versions_agent_id", "prompt_versions", ["agent_id"])


def downgrade() -> None:
    op.drop_table("prompt_versions")
