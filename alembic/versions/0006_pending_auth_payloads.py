"""add pending auth payloads

Revision ID: 0006_pending_auth_payloads
Revises: 0005_rate_limit_hits
Create Date: 2026-07-11 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0006_pending_auth_payloads"
down_revision = "0005_rate_limit_hits"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pending_auth_payloads",
        sa.Column("session_token", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column("steamid", sa.String(length=32), nullable=False),
        sa.Column("games", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(op.f("ix_pending_auth_payloads_expires_at"), "pending_auth_payloads", ["expires_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_pending_auth_payloads_expires_at"), table_name="pending_auth_payloads")
    op.drop_table("pending_auth_payloads")
