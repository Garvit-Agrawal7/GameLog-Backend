from uuid import UUID

from collections import defaultdict, deque
from time import monotonic

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import (
    current_active_user,
    current_enabled_superuser,
    current_enabled_user,
    fastapi_users,
    get_jwt_strategy,
    get_user_manager,
)
from app.database import get_async_session
from app.models import User
from app.schemas import (
    ForgotPasswordRequest,
    LoginRequest,
    LoginResponse,
    ResetPasswordRequest,
    UserCreate,
    UserRead,
    UserUpdate,
)

router = APIRouter(prefix="/auth", tags=["auth"])
_auth_requests: dict[str, deque[float]] = defaultdict(deque)
_auth_window_seconds = 1.0
_auth_max_requests = 2


def _allow_auth_request(request: Request) -> bool:
    client = request.client
    client_ip = client.host if client else "unknown"
    now = monotonic()
    window_start = now - _auth_window_seconds
    timestamps = _auth_requests[client_ip]

    while timestamps and timestamps[0] < window_start:
        timestamps.popleft()

    if len(timestamps) >= _auth_max_requests:
        return False

    timestamps.append(now)
    return True

router.include_router(
    fastapi_users.get_verify_router(UserRead),
)
router.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate),
)


@router.post("/signup", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def signup(
    request: Request,
    payload: UserCreate,
    session: AsyncSession = Depends(get_async_session),
    user_manager=Depends(get_user_manager),
):
    if not _allow_auth_request(request):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many auth requests")

    existing = await session.execute(select(User).where((User.email == payload.email) | (User.username == payload.username)))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email or userid already exists")

    user = await user_manager.create(payload)
    return user


@router.post("/login", response_model=LoginResponse)
async def login(
    request: Request,
    payload: LoginRequest,
    session: AsyncSession = Depends(get_async_session),
    user_manager=Depends(get_user_manager),
):
    if not _allow_auth_request(request):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many auth requests")

    result = await session.execute(select(User).where((User.email == payload.identifier) | (User.username == payload.identifier)))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid credentials")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled")

    verified, _ = user_manager.password_helper.verify_and_update(payload.password, user.hashed_password)
    if not verified:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid credentials")

    token = await get_jwt_strategy().write_token(user)
    print(token)
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
    if not _allow_auth_request(request):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many auth requests")

    result = await session.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()
    if user is None:
        return {"message": "If the email exists, a reset link was sent"}

    await user_manager.forgot_password(user, request=request)
    return {"message": "If the email exists, a reset link was sent"}


@router.post("/reset-password")
async def reset_password(
    request: Request,
    payload: ResetPasswordRequest,
    user_manager=Depends(get_user_manager),
):
    if not _allow_auth_request(request):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many auth requests")

    await user_manager.reset_password(payload.token, payload.password, request=request)
    return {"message": "Password updated"}


@router.get("/me", response_model=UserRead)
async def read_current_user(current_user=Depends(current_active_user)):
    return current_user


@router.post("/admin/users/{user_id}/disable", status_code=status.HTTP_200_OK)
async def disable_user(
    request: Request,
    user_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    _admin=Depends(current_enabled_superuser),
):
    if not _allow_auth_request(request):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many auth requests")

    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.is_active = False
    session.add(user)
    await session.commit()
    return {"message": "User disabled", "user_id": str(user_id)}
