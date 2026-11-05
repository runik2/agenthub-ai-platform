"""add workspace invitation links

Revision ID: 23q_team_invitations
Revises: 22p_password_reset_tokens
"""

from alembic import op
import sqlalchemy as sa

revision = "23q_team_invitations"
down_revision = "22p_password_reset_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "team_invitations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("workspace_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("invited_by_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_team_invitations_workspace_id", "team_invitations", ["workspace_id"])
    op.create_index("ix_team_invitations_invited_by_id", "team_invitations", ["invited_by_id"])
    op.create_index("ix_team_invitations_email", "team_invitations", ["email"])
    op.create_index("ix_team_invitations_token_hash", "team_invitations", ["token_hash"], unique=True)


def downgrade() -> None:
    op.drop_table("team_invitations")
