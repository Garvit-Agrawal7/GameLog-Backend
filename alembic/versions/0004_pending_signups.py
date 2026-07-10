"""replace email verification sessions with pending signups

Revision ID: 0004_pending_signups
Revises: 0003_email_verification_sessions
Create Date: 2026-07-10 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0004_pending_signups"
down_revision = "0003_email_verification_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pending_signups",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("username", sa.String(length=150), nullable=False),
        sa.Column("password_hash", sa.String(length=1024), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(op.f("ix_pending_signups_email"), "pending_signups", ["email"], unique=True)
    op.create_index(op.f("ix_pending_signups_username"), "pending_signups", ["username"], unique=True)
    op.create_index(op.f("ix_pending_signups_code_hash"), "pending_signups", ["code_hash"], unique=True)

    op.drop_index(op.f("ix_email_verification_sessions_code_hash"), table_name="email_verification_sessions")
    op.drop_index(op.f("ix_email_verification_sessions_user_id"), table_name="email_verification_sessions")
    op.drop_table("email_verification_sessions")

    op.drop_index(op.f("ix_users_username"), table_name="users")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_column("users", "is_verified")
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(op.f("ix_users_username"), "users", ["username"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_users_username"), table_name="users")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.add_column("users", sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.text("0")))
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(op.f("ix_users_username"), "users", ["username"], unique=True)

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

    op.drop_index(op.f("ix_pending_signups_code_hash"), table_name="pending_signups")
    op.drop_index(op.f("ix_pending_signups_username"), table_name="pending_signups")
    op.drop_index(op.f("ix_pending_signups_email"), table_name="pending_signups")
    op.drop_table("pending_signups")
