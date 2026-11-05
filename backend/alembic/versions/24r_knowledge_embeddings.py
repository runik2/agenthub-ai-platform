"""store semantic embeddings for knowledge chunks

Revision ID: 24r_knowledge_embeddings
Revises: 23q_team_invitations
"""

from alembic import op
import sqlalchemy as sa

revision = "24r_knowledge_embeddings"
down_revision = "23q_team_invitations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("knowledge_chunks", sa.Column("embedding", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("knowledge_chunks", "embedding")
