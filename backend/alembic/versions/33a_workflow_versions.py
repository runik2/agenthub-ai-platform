"""store immutable workflow configuration history

Revision ID: 33a_workflow_versions
Revises: 32z_usage_workflows
"""

from alembic import op
import sqlalchemy as sa


revision = "33a_workflow_versions"
down_revision = "32z_usage_workflows"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workflow_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workflow_id", sa.String(36), sa.ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("steps", sa.JSON(), nullable=False),
        sa.Column("note", sa.String(255), nullable=False, server_default=""),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_workflow_versions_owner_id", "workflow_versions", ["owner_id"])
    op.create_index("ix_workflow_versions_workflow_id", "workflow_versions", ["workflow_id"])
    op.create_index("ix_workflow_versions_created_by", "workflow_versions", ["created_by"])


def downgrade() -> None:
    op.drop_table("workflow_versions")
