"""two factor authentication fields

Revision ID: 15i_two_factor
Revises: 14h_refresh_sessions
"""
from alembic import op
import sqlalchemy as sa

revision = "15i_two_factor"
down_revision = "14h_refresh_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("two_factor_secret", sa.String(64), nullable=True))
    op.add_column("users", sa.Column("two_factor_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("users", "two_factor_enabled")
    op.drop_column("users", "two_factor_secret")
