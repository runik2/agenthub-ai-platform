"""version knowledge documents and support reindexing

Revision ID: 21o_knowledge_versions
Revises: 20n_webhook_idempotency
"""

from uuid import uuid4

from alembic import op
import sqlalchemy as sa

revision = "21o_knowledge_versions"
down_revision = "20n_webhook_idempotency"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "knowledge_documents", sa.Column("version", sa.Integer(), nullable=False, server_default="1")
    )
    op.create_table(
        "knowledge_document_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "document_id",
            sa.String(36),
            sa.ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("chunk_count", sa.Integer(), nullable=False),
    )
    op.create_index(
        "ix_knowledge_document_versions_document_id",
        "knowledge_document_versions",
        ["document_id"],
    )
    rows = op.get_bind().execute(
        sa.text(
            "SELECT id, content, chunk_count, created_at, updated_at "
            "FROM knowledge_documents"
        )
    ).mappings()
    op.bulk_insert(
        sa.table(
            "knowledge_document_versions",
            sa.column("id", sa.String(36)),
            sa.column("created_at", sa.DateTime(timezone=True)),
            sa.column("updated_at", sa.DateTime(timezone=True)),
            sa.column("document_id", sa.String(36)),
            sa.column("version", sa.Integer()),
            sa.column("content", sa.Text()),
            sa.column("chunk_count", sa.Integer()),
        ),
        [
            {
                "id": str(uuid4()),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "document_id": row["id"],
                "version": 1,
                "content": row["content"],
                "chunk_count": row["chunk_count"],
            }
            for row in rows
        ],
    )


def downgrade() -> None:
    op.drop_table("knowledge_document_versions")
    with op.batch_alter_table("knowledge_documents") as batch:
        batch.drop_column("version")
