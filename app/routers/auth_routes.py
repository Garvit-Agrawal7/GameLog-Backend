from uuid import UUID, uuid4

from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import (
    build_frontend_reset_url,
    current_active_user,
    current_enabled_superuser,
    create_reset_session,
    create_pending_signup,
    fastapi_users,
    get_jwt_strategy,
    get_user_manager,
    hash_reset_value,
    validate_reset_token,
    validate_reset_session,
)
from app.database import get_async_session
from app.models import PasswordResetSession, PendingSignup, User
from app.rate_limit import allow_default_request, enforce_default_limit
from app.schemas import (
    ForgotPasswordRequest,
    LoginRequest,
    LoginResponse,
    ResetPasswordRequest,
    SignupResponse,
    UserCreate,
    UserRead,
    UserUpdate,
    VerifyEmailRequest,
)

router = APIRouter(prefix="/auth", tags=["auth"])


router.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate),
    dependencies=[Depends(enforce_default_limit)],
)


@router.post("/signup", response_model=SignupResponse, status_code=status.HTTP_201_CREATED)
async def signup(
    request: Request,
    payload: UserCreate,
    session: AsyncSession = Depends(get_async_session),
    user_manager=Depends(get_user_manager),
):
    if not await allow_default_request(request):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many auth requests")

    existing = await session.execute(select(User).where((User.email == payload.email) | (User.username == payload.username)))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email or userid already exists")

    pending_existing = await session.execute(
        select(PendingSignup).where((PendingSignup.email == payload.email) | (PendingSignup.username == payload.username))
    )
    if pending_existing.scalar_one_or_none() is not None:
        return {"message": "Verification code sent"}

    password_hash = user_manager.password_helper.hash(payload.password)
    await create_pending_signup(session, payload.email, payload.username, password_hash)
    return {"message": "Verification code sent"}


@router.post("/verify")
async def verify(
    request: Request,
    payload: VerifyEmailRequest,
    session: AsyncSession = Depends(get_async_session),
):
    if not await allow_default_request(request):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many auth requests")

    result = await session.execute(select(PendingSignup).where(PendingSignup.email == payload.email))
    pending_signup = result.scalar_one_or_none()
    if pending_signup is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid verification code")

    code_hash = hash_reset_value(payload.code)
    if pending_signup.code_hash != code_hash:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid verification code")

    if pending_signup.consumed_at is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Verification code has already been used")

    now = datetime.now(UTC)
    expires_at = pending_signup.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at <= now:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Verification code has expired")

    user = User(
        id=uuid4(),
        email=pending_signup.email,
        username=pending_signup.username,
        hashed_password=pending_signup.password_hash,
        is_active=True,
        is_superuser=False,
    )
    pending_signup.consumed_at = now
    session.add(user)
    await session.delete(pending_signup)
    await session.commit()
    return {"message": "Email verified and account created"}


@router.post("/login", response_model=LoginResponse)
async def login(
    request: Request,
    payload: LoginRequest,
    session: AsyncSession = Depends(get_async_session),
    user_manager=Depends(get_user_manager),
):
    if not await allow_default_request(request):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many auth requests")

    result = await session.execute(select(User).where((User.email == payload.identifier) | (User.username == payload.identifier)))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled")

    verified, _ = user_manager.password_helper.verify_and_update(payload.password, user.hashed_password)
    if not verified:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = await get_jwt_strategy().write_token(user)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user,
    }


@router.post("/forgot-password")
async def forgot_password(
    request: Request,
    payload: ForgotPasswordRequest,
    session: AsyncSession = Depends(get_async_session),
    user_manager=Depends(get_user_manager),
):
    if not await allow_default_request(request):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many auth requests")

    result = await session.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    await user_manager.forgot_password(user, request=request)
    return {"message": "A password reset link was sent to your email"}


@router.get("/reset-password/confirm")
async def confirm_reset_password(
    token: str,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user_manager=Depends(get_user_manager),
):
    if not await allow_default_request(request):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many auth requests")

    token_hash = hash_reset_value(token)
    existing = await session.execute(select(PasswordResetSession).where(PasswordResetSession.original_token_hash == token_hash))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reset link has already been used")

    user, password_fingerprint = await validate_reset_token(user_manager, token)
    reset_code = await create_reset_session(session, user, password_fingerprint, token)
    app_reset_url = build_frontend_reset_url(reset_code)

    fallback_template = Path("app/templates/reset_password_fallback.html").read_text(encoding="utf-8")
    fallback_html = (
        fallback_template.replace("{{RESET_CODE}}", reset_code)
        .replace("{{APP_RESET_URL}}", app_reset_url)
    )

    return HTMLResponse(content=fallback_html, status_code=status.HTTP_200_OK)


@router.post("/reset-password")
async def reset_password(
    request: Request,
    payload: ResetPasswordRequest,
    session: AsyncSession = Depends(get_async_session),
    user_manager=Depends(get_user_manager),
):
    if not await allow_default_request(request):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many auth requests")

    if len(payload.password) < 6:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password must be at least 6 characters long")

    reset_session = await validate_reset_session(session, payload.token)
    now = datetime.now(UTC)
    user = await user_manager.get(reset_session.user_id)
    valid_fingerprint, _ = user_manager.password_helper.verify_and_update(user.hashed_password, reset_session.password_fingerprint)
    if not valid_fingerprint:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset code")

    await user_manager._update(user, {"password": payload.password})
    reset_session.consumed_at = now
    session.add(reset_session)
    await session.commit()
    return {"message": "Password updated"}


@router.get("/me", response_model=UserRead)
async def read_current_user(request: Request, current_user=Depends(current_active_user)):
    if not await allow_default_request(request):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many auth requests")

    return current_user


@router.post("/admin/users/{user_id}/disable", status_code=status.HTTP_200_OK)
async def disable_user(
    request: Request,
    user_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    _admin=Depends(current_enabled_superuser),
):
    if not await allow_default_request(request):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many auth requests")

    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.is_active = False
    session.add(user)
    await session.commit()
    return {"message": "User disabled", "user_id": str(user_id)}
