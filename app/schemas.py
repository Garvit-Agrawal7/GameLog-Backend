from pydantic import BaseModel
from fastapi_users import schemas
from uuid import UUID


class UserRead(schemas.BaseUser[UUID]):
    username: str


class UserCreate(schemas.BaseUserCreate):
    username: str


class UserUpdate(schemas.BaseUserUpdate):
    username: str | None = None


class LoginRequest(BaseModel):
    identifier: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    password: str


class LibraryGame(BaseModel):
    game_id: int
    title: str
    cover_url: str
    genres: list[str]
    summary: str
    rating: float
    hours_played: int
    time_to_beat_hours: int | None = None
    status: str | None = None
    user_rating: int | None = None
    year: int
    in_library: bool
    last_updated: str


class UserWithLibrary(UserRead):
    library: list[LibraryGame]
