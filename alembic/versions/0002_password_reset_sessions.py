"""add password reset sessions

Revision ID: 0002_password_reset_sessions
Revises: 0001_initial_schema
Create Date: 2026-07-10 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0002_password_reset_sessions"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "password_reset_sessions",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("original_token_hash", sa.String(length=64), nullable=False),
        sa.Column("reset_code_hash", sa.String(length=64), nullable=False),
        sa.Column("password_fingerprint", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(op.f("ix_password_reset_sessions_user_id"), "password_reset_sessions", ["user_id"], unique=False)
    op.create_index(op.f("ix_password_reset_sessions_original_token_hash"), "password_reset_sessions", ["original_token_hash"], unique=True)
    op.create_index(op.f("ix_password_reset_sessions_reset_code_hash"), "password_reset_sessions", ["reset_code_hash"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_password_reset_sessions_reset_code_hash"), table_name="password_reset_sessions")
    op.drop_index(op.f("ix_password_reset_sessions_original_token_hash"), table_name="password_reset_sessions")
    op.drop_index(op.f("ix_password_reset_sessions_user_id"), table_name="password_reset_sessions")
    op.drop_table("password_reset_sessions")
