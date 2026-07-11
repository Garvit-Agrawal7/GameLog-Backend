import secrets
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.cleanup import cleanup_expired_auth_rows
from app.database import get_async_session
from app.rate_limit import rate_limiter
from app.models import PendingAuthPayload
from app.steam_auth import steam_openid, create_steam_payload
from services.igdb_service import IGDBRateLimitException, igdb_service

router = APIRouter(prefix="/auth", tags=["auth"])
_steam_login_window_seconds = 1.0
_steam_login_max_requests = 2
_pending_auth_ttl_seconds = 3600


async def _allow_steam_login(request: Request) -> bool:
    return await rate_limiter.allow(request, "steam_login", _steam_login_window_seconds, _steam_login_max_requests)

@router.get("/steam/login")
async def steam_login(request: Request, session: AsyncSession = Depends(get_async_session)):
    if not await _allow_steam_login(request):
        return JSONResponse(status_code=429, content={"error": "Too many steam login requests"})
    return RedirectResponse(url=steam_openid.get_login_url())

@router.get("/steam/callback")
async def steam_callback(request: Request, session: AsyncSession = Depends(get_async_session)):
    if not await _allow_steam_login(request):
        return JSONResponse(status_code=429, content={"error": "Too many steam callback requests"})

    raw_query = request.url.query
    if not raw_query:
        return JSONResponse(status_code=400, content={"error": "missing query"})

    steamid = await steam_openid.verify_login(raw_query)
    if not steamid:
        return JSONResponse(status_code=401, content={"error": "verification failed"})

    try:
        steam_payload = await create_steam_payload(steamid)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": "payload_creation_failed", "detail": str(e)})

    seeds = steam_payload["games"]

    try:
        games_data = await igdb_service.multiquery_games(seeds)
    except IGDBRateLimitException as e:
        return JSONResponse(status_code=429, content={"error": str(e)})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": "igdb_enrichment_failed", "detail": str(e)})

    matched_games = [g for g in games_data if g.get("igdb_id") is not None]

    session_token = secrets.token_urlsafe(16)
    session.add(
        PendingAuthPayload(
            session_token=session_token,
            steamid=steam_payload["steamid"],
            games=matched_games,
            created_at=datetime.now(UTC),
            expires_at=datetime.now(UTC) + timedelta(seconds=_pending_auth_ttl_seconds),
        )
    )
    await session.commit()

    return RedirectResponse(url=f"{settings.frontend_url}auth/complete#session={session_token}")

@router.get("/session/{session_token}")
async def get_session_payload(session_token: str, session: AsyncSession = Depends(get_async_session)):
    await cleanup_expired_auth_rows()
    result = await session.execute(select(PendingAuthPayload).where(PendingAuthPayload.session_token == session_token))
    payload = result.scalar_one_or_none()
    if payload is None:
        return JSONResponse(status_code=404, content={"error": "session not found or expired"})
    await session.delete(payload)
    await session.commit()
    return {"steamid": payload.steamid, "games": payload.games}
