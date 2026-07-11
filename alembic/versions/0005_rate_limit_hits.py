"""add rate limit hits

Revision ID: 0005_rate_limit_hits
Revises: 0004_pending_signups
Create Date: 2026-07-11 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0005_rate_limit_hits"
down_revision = "0004_pending_signups"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rate_limit_hits",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("bucket", sa.String(length=64), nullable=False),
        sa.Column("client_ip", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(op.f("ix_rate_limit_hits_bucket"), "rate_limit_hits", ["bucket"], unique=False)
    op.create_index(op.f("ix_rate_limit_hits_client_ip"), "rate_limit_hits", ["client_ip"], unique=False)
    op.create_index(op.f("ix_rate_limit_hits_expires_at"), "rate_limit_hits", ["expires_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_rate_limit_hits_expires_at"), table_name="rate_limit_hits")
    op.drop_index(op.f("ix_rate_limit_hits_client_ip"), table_name="rate_limit_hits")
    op.drop_index(op.f("ix_rate_limit_hits_bucket"), table_name="rate_limit_hits")
    op.drop_table("rate_limit_hits")
