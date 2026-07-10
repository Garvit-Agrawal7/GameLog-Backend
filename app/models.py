from fastapi_users_db_sqlalchemy import SQLAlchemyBaseUserTableUUID
from uuid import UUID

from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class User(SQLAlchemyBaseUserTableUUID, Base):
    __tablename__ = "users"

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
