"""deduplicate signed webhook events

Revision ID: 20n_webhook_idempotency
Revises: 19m_team_workspaces
"""

from alembic import op
import sqlalchemy as sa

revision = "20n_webhook_idempotency"
down_revision = "19m_team_workspaces"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("webhook_deliveries", sa.Column("event_id", sa.String(200), nullable=True))
    op.create_index("ix_webhook_deliveries_event_id", "webhook_deliveries", ["event_id"])
    with op.batch_alter_table("webhook_deliveries") as batch:
        batch.create_unique_constraint(
            "uq_webhook_delivery_endpoint_event", ["endpoint_id", "event_id"]
        )


def downgrade() -> None:
    with op.batch_alter_table("webhook_deliveries") as batch:
        batch.drop_constraint("uq_webhook_delivery_endpoint_event", type_="unique")
        batch.drop_column("event_id")
