from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import current_enabled_user
from app.database import get_async_session
from app.models import User, UserLibraryGame
from app.rate_limit import allow_default_request, enforce_default_limit
from app.schemas import LibraryGame, UserWithLibrary

router = APIRouter(prefix="/database", tags=["database"], dependencies=[Depends(enforce_default_limit)])


def _to_library_game(row: UserLibraryGame) -> LibraryGame:
    return LibraryGame(
        game_id=row.game_id,
        title=row.title,
        cover_url=row.cover_url,
        genres=list(row.genres or []),
        summary=row.summary,
        rating=row.rating,
        hours_played=row.hours_played,
        time_to_beat_hours=row.time_to_beat_hours,
        status=row.status,
        user_rating=row.user_rating,
        year=row.year,
        in_library=row.in_library,
        last_updated=row.last_updated,
    )


async def _get_user_or_404(session: AsyncSession, user_id: UUID) -> User:
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.get("/users/{user_id}", response_model=UserWithLibrary)
async def get_user_details(
    user_id: UUID,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
):
    if not await allow_default_request(request):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many requests")

    user = await _get_user_or_404(session, user_id)
    library_result = await session.execute(
        select(UserLibraryGame)
        .where(UserLibraryGame.user_id == user_id)
        .order_by(UserLibraryGame.title.asc())
    )
    library = [_to_library_game(item) for item in library_result.scalars().all()]

    return UserWithLibrary(
        id=user.id,
        email=user.email,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        username=user.username,
        library=library,
    )


@router.get("/users/{user_id}/library", response_model=list[LibraryGame])
async def get_user_library(
    user_id: UUID,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
):
    if not await allow_default_request(request):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many requests")

    await _get_user_or_404(session, user_id)
    result = await session.execute(
        select(UserLibraryGame)
        .where(UserLibraryGame.user_id == user_id)
        .order_by(UserLibraryGame.title.asc())
    )
    return [_to_library_game(item) for item in result.scalars().all()]


@router.put("/users/{user_id}/library", response_model=list[LibraryGame])
async def replace_user_library(
    user_id: UUID,
    library: list[LibraryGame],
    request: Request,
    current_user: User = Depends(current_enabled_user),
    session: AsyncSession = Depends(get_async_session),
):
    if not await allow_default_request(request):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many requests")

    if user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only update your own library")

    await _get_user_or_404(session, user_id)

    await session.execute(delete(UserLibraryGame).where(UserLibraryGame.user_id == user_id))

    rows = [
        UserLibraryGame(
            user_id=user_id,
            game_id=item.game_id,
            title=item.title,
            cover_url=item.cover_url,
            genres=item.genres,
            summary=item.summary,
            rating=item.rating,
            hours_played=item.hours_played,
            time_to_beat_hours=item.time_to_beat_hours,
            status=item.status,
            user_rating=item.user_rating,
            year=item.year,
            in_library=item.in_library,
            last_updated=item.last_updated,
        )
        for item in library
    ]

    session.add_all(rows)
    await session.commit()
    return library
