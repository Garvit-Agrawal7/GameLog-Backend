from pydantic import BaseModel
from uuid import UUID


class UserRead(BaseModel):
    id: UUID
    email: str
    is_active: bool
    is_superuser: bool
    username: str


class UserCreate(BaseModel):
    email: str
    password: str
    username: str


class UserUpdate(BaseModel):
    email: str | None = None
    password: str | None = None
    username: str | None = None


class LoginRequest(BaseModel):
    identifier: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead


class SignupResponse(BaseModel):
    message: str


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    password: str


class VerifyEmailRequest(BaseModel):
    email: str
    code: str


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
