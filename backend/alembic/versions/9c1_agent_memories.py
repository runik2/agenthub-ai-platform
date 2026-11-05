"""agent memories

Revision ID: 9c1_agent_memories
Revises: 8b1_human_approvals
"""
from alembic import op
import sqlalchemy as sa

revision = "9c1_agent_memories"
down_revision = "8b1_human_approvals"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_memories",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("agent_id", sa.String(36), sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("category", sa.String(40), nullable=False),
        sa.Column("source", sa.String(80), nullable=False),
        sa.Column("is_pinned", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_agent_memories_owner_id", "agent_memories", ["owner_id"])
    op.create_index("ix_agent_memories_agent_id", "agent_memories", ["agent_id"])


def downgrade() -> None:
    op.drop_table("agent_memories")
