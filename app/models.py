from uuid import UUID
from datetime import datetime

from sqlalchemy import Boolean, JSON, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(1024), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    username: Mapped[str] = mapped_column(String(150), unique=True, index=True, nullable=False)


class UserLibraryGame(Base):
    __tablename__ = "user_library_games"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    game_id: Mapped[int] = mapped_column(index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    cover_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    genres: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    rating: Mapped[float] = mapped_column(nullable=False, default=0.0)
    hours_played: Mapped[int] = mapped_column(nullable=False, default=0)
    time_to_beat_hours: Mapped[int | None] = mapped_column(nullable=True)
    status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    user_rating: Mapped[int | None] = mapped_column(nullable=True)
    year: Mapped[int] = mapped_column(nullable=False, default=0)
    in_library: Mapped[bool] = mapped_column(nullable=False, default=True)
    last_updated: Mapped[str] = mapped_column(String(64), nullable=False)


class PasswordResetSession(Base):
    __tablename__ = "password_reset_sessions"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    original_token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    reset_code_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    password_fingerprint: Mapped[str] = mapped_column(String(255), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PendingSignup(Base):
    __tablename__ = "pending_signups"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    username: Mapped[str] = mapped_column(String(150), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(1024), nullable=False)
    code_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PendingAuthPayload(Base):
    __tablename__ = "pending_auth_payloads"

    session_token: Mapped[str] = mapped_column(String(64), primary_key=True)
    id: Mapped[str] = mapped_column(String(32), nullable=False)
    provider: Mapped[str] = mapped_column(String(16), nullable=False)
    games: Mapped[list] = mapped_column(JSON, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RateLimitHit(Base):
    __tablename__ = "rate_limit_hits"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    bucket: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    client_ip: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
