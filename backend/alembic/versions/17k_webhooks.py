"""signed incoming webhooks and delivery logs

Revision ID: 17k_webhooks
Revises: 16j_login_protection
"""
from alembic import op
import sqlalchemy as sa

revision = "17k_webhooks"
down_revision = "16j_login_protection"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("webhook_endpoints", sa.Column("id", sa.String(36), primary_key=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("workflow_id", sa.String(36), sa.ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False), sa.Column("name", sa.String(120), nullable=False), sa.Column("slug", sa.String(120), nullable=False), sa.Column("secret_encrypted", sa.Text(), nullable=False), sa.Column("enabled", sa.Boolean(), nullable=False), sa.Column("last_received_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_webhook_endpoints_owner_id", "webhook_endpoints", ["owner_id"])
    op.create_index("ix_webhook_endpoints_workflow_id", "webhook_endpoints", ["workflow_id"])
    op.create_index("ix_webhook_endpoints_slug", "webhook_endpoints", ["slug"])
    op.create_table("webhook_deliveries", sa.Column("id", sa.String(36), primary_key=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.Column("endpoint_id", sa.String(36), sa.ForeignKey("webhook_endpoints.id", ondelete="CASCADE"), nullable=False), sa.Column("task_id", sa.String(36), sa.ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True), sa.Column("status", sa.String(20), nullable=False), sa.Column("signature_valid", sa.Boolean(), nullable=False), sa.Column("payload", sa.JSON(), nullable=False), sa.Column("error", sa.Text(), nullable=True))
    op.create_index("ix_webhook_deliveries_endpoint_id", "webhook_deliveries", ["endpoint_id"])


def downgrade() -> None:
    op.drop_table("webhook_deliveries")
    op.drop_table("webhook_endpoints")
