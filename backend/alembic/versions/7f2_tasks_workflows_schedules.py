"""durable execution tables"""
from alembic import op
import sqlalchemy as sa
revision = "7f2_tasks_workflows_schedules"
down_revision = "3afdb6f7903d"
branch_labels = None
depends_on = None
def _common():
    return [sa.Column("id", sa.String(36), primary_key=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False)]
def upgrade() -> None:
    op.create_table("workflows", *_common(), sa.Column("owner_id", sa.String(36), nullable=False), sa.Column("name", sa.String(255), nullable=False), sa.Column("description", sa.Text(), nullable=False), sa.Column("enabled", sa.Boolean(), nullable=False), sa.Column("steps", sa.JSON(), nullable=False), sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"))
    for c in ("created_at", "owner_id"): op.create_index(f"ix_workflows_{c}", "workflows", [c])
    op.create_table("tasks", *_common(), sa.Column("owner_id", sa.String(36), nullable=False), sa.Column("agent_id", sa.String(36)), sa.Column("workflow_id", sa.String(36)), sa.Column("name", sa.String(255), nullable=False), sa.Column("input", sa.Text(), nullable=False), sa.Column("status", sa.String(20), nullable=False), sa.Column("result", sa.Text()), sa.Column("error", sa.Text()), sa.Column("max_retries", sa.Integer(), nullable=False), sa.Column("attempts", sa.Integer(), nullable=False), sa.Column("next_run_at", sa.DateTime(timezone=True)), sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="SET NULL"), sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"], ondelete="SET NULL"))
    for c in ("created_at", "owner_id", "status"): op.create_index(f"ix_tasks_{c}", "tasks", [c])
    op.create_table("task_runs", *_common(), sa.Column("task_id", sa.String(36), nullable=False), sa.Column("status", sa.String(20), nullable=False), sa.Column("attempt", sa.Integer(), nullable=False), sa.Column("result", sa.Text()), sa.Column("error", sa.Text()), sa.Column("started_at", sa.DateTime(timezone=True)), sa.Column("finished_at", sa.DateTime(timezone=True)), sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"))
    for c in ("created_at", "task_id"): op.create_index(f"ix_task_runs_{c}", "task_runs", [c])
    op.create_table("schedules", *_common(), sa.Column("owner_id", sa.String(36), nullable=False), sa.Column("workflow_id", sa.String(36), nullable=False), sa.Column("name", sa.String(255), nullable=False), sa.Column("cron", sa.String(100), nullable=False), sa.Column("enabled", sa.Boolean(), nullable=False), sa.Column("last_run_at", sa.DateTime(timezone=True)), sa.Column("run_count", sa.Integer(), nullable=False), sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"], ondelete="CASCADE"))
    for c in ("created_at", "owner_id", "workflow_id"): op.create_index(f"ix_schedules_{c}", "schedules", [c])
def downgrade() -> None:
    for t in ("schedules", "task_runs", "tasks", "workflows"): op.drop_table(t)
