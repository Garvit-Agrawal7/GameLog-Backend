from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
import hashlib
import secrets
from uuid import UUID, uuid4

from fastapi import Depends, HTTPException, status
from fastapi import Request
from fastapi_users import BaseUserManager, FastAPIUsers, UUIDIDMixin
from fastapi_users.jwt import decode_jwt
from fastapi_users.authentication import AuthenticationBackend, BearerTransport, JWTStrategy
from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.email import send_reset_password_email, send_verification_email
from app.database import get_async_session
from app.models import PasswordResetSession, PendingSignup, User


async def get_user_db(session: AsyncSession = Depends(get_async_session)) -> AsyncGenerator[SQLAlchemyUserDatabase, None]:
    yield SQLAlchemyUserDatabase(session, User)


class UserManager(UUIDIDMixin, BaseUserManager[User, UUID]):
    reset_password_token_secret = settings.secret_key
    verification_token_secret = settings.secret_key

    async def on_after_register(self, user: User, request: Request | None = None) -> None:
        return None

    async def on_after_forgot_password(self, user: User, token: str, request: Request | None = None) -> None:
        await send_reset_password_email(user.email, token)

    async def on_after_reset_password(self, user: User, request: Request | None = None) -> None:
        return None


def hash_reset_value(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def make_reset_code() -> str:
    return secrets.token_urlsafe(32)


def make_verification_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def build_frontend_reset_url(reset_code: str) -> str:
    return f"{settings.frontend_url}reset-password?code={reset_code}"


async def validate_reset_token(user_manager: UserManager, token: str) -> tuple[User, str]:
    try:
        data = decode_jwt(
            token,
            user_manager.reset_password_token_secret,
            [user_manager.reset_password_token_audience],
        )
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token") from exc

    try:
        user_id = user_manager.parse_id(data["sub"])
        password_fingerprint = data["password_fgpt"]
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token") from exc

    user = await user_manager.get(user_id)
    valid_fingerprint, _ = user_manager.password_helper.verify_and_update(user.hashed_password, password_fingerprint)
    if not valid_fingerprint:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token")

    return user, password_fingerprint


async def create_reset_session(session: AsyncSession, user: User, password_fingerprint: str, original_token: str) -> str:
    now = datetime.now(UTC)
    reset_code = make_reset_code()
    reset_session = PasswordResetSession(
        id=uuid4(),
        user_id=user.id,
        original_token_hash=hash_reset_value(original_token),
        reset_code_hash=hash_reset_value(reset_code),
        password_fingerprint=password_fingerprint,
        created_at=now,
        expires_at=now + timedelta(minutes=15),
        consumed_at=None,
    )
    session.add(reset_session)
    await session.commit()
    return reset_code


async def validate_reset_session(session: AsyncSession, reset_code: str) -> PasswordResetSession:
    reset_code_hash = hash_reset_value(reset_code)
    result = await session.execute(select(PasswordResetSession).where(PasswordResetSession.reset_code_hash == reset_code_hash))
    reset_session = result.scalar_one_or_none()
    if reset_session is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset code")

    if reset_session.consumed_at is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reset code has already been used")

    now = datetime.now(UTC)
    expires_at = reset_session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at <= now:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reset code has expired")

    return reset_session


async def create_pending_signup(
    session: AsyncSession,
    email: str,
    username: str,
    password_hash: str,
) -> str:
    now = datetime.now(UTC)
    code = make_verification_code()
    pending_signup = PendingSignup(
        id=uuid4(),
        email=email,
        username=username,
        password_hash=password_hash,
        code_hash=hash_reset_value(code),
        created_at=now,
        expires_at=now + timedelta(minutes=15),
        consumed_at=None,
    )
    session.add(pending_signup)
    await session.commit()
    await send_verification_email(email, code)
    return code


async def get_user_manager(user_db=Depends(get_user_db)) -> AsyncGenerator[UserManager, None]:
    yield UserManager(user_db)


bearer_transport = BearerTransport(tokenUrl="auth/login")


def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(secret=settings.secret_key, lifetime_seconds=60 * 60 * 24 * 30)


auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)

fastapi_users = FastAPIUsers[User, UUID](get_user_manager, [auth_backend])
current_user = fastapi_users.current_user()
current_active_user = fastapi_users.current_user(active=True)
current_superuser = fastapi_users.current_user(active=True, superuser=True)


async def current_enabled_user(user: User = Depends(current_user)) -> User:
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled")
    return user


async def current_enabled_superuser(user: User = Depends(current_superuser)) -> User:
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled")
    return user
