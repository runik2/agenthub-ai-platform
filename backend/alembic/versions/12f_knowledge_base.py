"""knowledge base documents and chunks

Revision ID: 12f_knowledge_base
Revises: 11e_prompt_versions
"""
from alembic import op
import sqlalchemy as sa

revision = "12f_knowledge_base"
down_revision = "11e_prompt_versions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("knowledge_documents", sa.Column("id", sa.String(36), primary_key=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("agent_id", sa.String(36), sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=True), sa.Column("title", sa.String(255), nullable=False), sa.Column("source_type", sa.String(30), nullable=False), sa.Column("content", sa.Text(), nullable=False), sa.Column("chunk_count", sa.Integer(), nullable=False))
    op.create_index("ix_knowledge_documents_owner_id", "knowledge_documents", ["owner_id"])
    op.create_index("ix_knowledge_documents_agent_id", "knowledge_documents", ["agent_id"])
    op.create_table("knowledge_chunks", sa.Column("id", sa.String(36), primary_key=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.Column("document_id", sa.String(36), sa.ForeignKey("knowledge_documents.id", ondelete="CASCADE"), nullable=False), sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("agent_id", sa.String(36), sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=True), sa.Column("chunk_index", sa.Integer(), nullable=False), sa.Column("content", sa.Text(), nullable=False))
    op.create_index("ix_knowledge_chunks_document_id", "knowledge_chunks", ["document_id"])
    op.create_index("ix_knowledge_chunks_owner_id", "knowledge_chunks", ["owner_id"])
    op.create_index("ix_knowledge_chunks_agent_id", "knowledge_chunks", ["agent_id"])


def downgrade() -> None:
    op.drop_table("knowledge_chunks")
    op.drop_table("knowledge_documents")
