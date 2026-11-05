"""human approval gate for tasks

Revision ID: 8b1_human_approvals
Revises: 7f2_tasks_workflows_schedules
"""

from alembic import op
import sqlalchemy as sa

revision = "8b1_human_approvals"
down_revision = "7f2_tasks_workflows_schedules"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("tasks") as batch:
        batch.add_column(sa.Column("requires_approval", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.add_column(sa.Column("approval_note", sa.Text(), nullable=True))
        batch.add_column(sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("approved_by_id", sa.String(length=36), nullable=True))
        batch.create_foreign_key("fk_tasks_approved_by_id_users", "users", ["approved_by_id"], ["id"], ondelete="SET NULL")


def downgrade() -> None:
    with op.batch_alter_table("tasks") as batch:
        batch.drop_constraint("fk_tasks_approved_by_id_users", type_="foreignkey")
        batch.drop_column("approved_by_id")
        batch.drop_column("approved_at")
        batch.drop_column("approval_note")
        batch.drop_column("requires_approval")
