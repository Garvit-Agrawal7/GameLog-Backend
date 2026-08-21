import secrets
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.database import get_async_session
from app.rate_limit import allow_default_request
from app.models import PendingAuthPayload
from app.steam_auth import steam_openid, create_steam_payload
from services.igdb_service import IGDBRateLimitException, igdb_service

router = APIRouter(prefix="/auth", tags=["auth"])
_pending_auth_ttl_seconds = 3600


@router.get("/steam/login")
async def steam_login(request: Request, session: AsyncSession = Depends(get_async_session)):
    if not await allow_default_request(request):
        return JSONResponse(status_code=429, content={"error": "Too many steam login requests"})
    return RedirectResponse(url=steam_openid.get_login_url())

@router.get("/steam/callback")
async def steam_callback(request: Request, session: AsyncSession = Depends(get_async_session)):
    if not await allow_default_request(request):
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
            id=steam_payload["steamid"],
            provider="steam",
            games=matched_games,
            created_at=datetime.now(UTC),
            expires_at=datetime.now(UTC) + timedelta(seconds=_pending_auth_ttl_seconds),
        )
    )
    await session.commit()

    return RedirectResponse(url=f"{settings.frontend_url}auth/complete#session={session_token}")

@router.get("/session/{session_token}")
async def get_session_payload(session_token: str, session: AsyncSession = Depends(get_async_session)):
    result = await session.execute(select(PendingAuthPayload).where(PendingAuthPayload.session_token == session_token))
    payload = result.scalar_one_or_none()
    if payload is None:
        return JSONResponse(status_code=404, content={"error": "session not found or expired"})
    if payload.expires_at <= datetime.now(UTC):
        await session.delete(payload)
        await session.commit()
        return JSONResponse(status_code=404, content={"error": "session not found or expired"})
    await session.delete(payload)
    await session.commit()

    return {"id": payload.id, "provider": payload.provider, "games": payload.games}
