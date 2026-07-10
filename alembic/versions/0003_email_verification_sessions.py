"""add email verification sessions

Revision ID: 0003_email_verification_sessions
Revises: 0002_password_reset_sessions
Create Date: 2026-07-10 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_email_verification_sessions"
down_revision = "0002_password_reset_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "email_verification_sessions",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(op.f("ix_email_verification_sessions_user_id"), "email_verification_sessions", ["user_id"], unique=False)
    op.create_index(op.f("ix_email_verification_sessions_code_hash"), "email_verification_sessions", ["code_hash"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_email_verification_sessions_code_hash"), table_name="email_verification_sessions")
    op.drop_index(op.f("ix_email_verification_sessions_user_id"), table_name="email_verification_sessions")
    op.drop_table("email_verification_sessions")
