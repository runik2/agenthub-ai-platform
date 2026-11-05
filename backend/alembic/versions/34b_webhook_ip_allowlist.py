"""add source IP allowlist to webhook endpoints

Revision ID: 34b_webhook_ip_allowlist
Revises: 33a_workflow_versions
"""

from alembic import op
import sqlalchemy as sa


revision = "34b_webhook_ip_allowlist"
down_revision = "33a_workflow_versions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("webhook_endpoints", recreate="always") as batch:
        batch.add_column(sa.Column("allowed_ips", sa.JSON(), nullable=False, server_default="[]"))


def downgrade() -> None:
    with op.batch_alter_table("webhook_endpoints", recreate="always") as batch:
        batch.drop_column("allowed_ips")
