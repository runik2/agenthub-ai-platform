"""login throttling fields

Revision ID: 16j_login_protection
Revises: 15i_two_factor
"""
from alembic import op
import sqlalchemy as sa

revision = "16j_login_protection"
down_revision = "15i_two_factor"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("failed_login_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("users", sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "locked_until")
    op.drop_column("users", "failed_login_count")
