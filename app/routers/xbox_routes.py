import secrets
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.xbox_auth import xbox_auth
from app.database import get_async_session
from app.rate_limit import allow_default_request
from app.models import PendingAuthPayload
from services.xbox_service import xbox_service
from services.igdb_service import IGDBRateLimitException, igdb_service


router = APIRouter(prefix="/auth", tags=["auth"])
_pending_auth_ttl_seconds = 3600


@router.get("/xbox/login")
async def xbox_login(request: Request, session: AsyncSession = Depends(get_async_session)):
    if not await allow_default_request(request):
        return JSONResponse(status_code=429, content={"error": "Too many xbox login requests"})
    return RedirectResponse(url=xbox_auth.get_login_url())


@router.get("/xbox/callback")
async def xbox_callback(request: Request, session: AsyncSession = Depends(get_async_session)):
    if not await allow_default_request(request):
        return JSONResponse(status_code=429, content={"error": "Too many xbox callback requests"})
    query_params = dict(request.query_params)
    if not query_params or "code" not in query_params:
        return JSONResponse(status_code=400, content={"error": "missing query"})
    code = query_params["code"]

    try:
        user_details = await xbox_auth.verify_login(code)
    except ValueError as e:
        msg = str(e)
        if "timed out" in msg:
            return JSONResponse(
                status_code=504,
                content={"error": "Xbox login timed out, please try again later"},
            )
        return JSONResponse(
            status_code=400,
            content={"error": "Xbox login failed, please try again later"},
        )

    xuid = user_details["xuid"]

    try:
        owned = await xbox_service.get_owned_games(xuid)
    except ValueError as e:
        return JSONResponse(status_code=502, content={"error": "xbox_titles_fetch_failed", "detail": str(e)})

    try:
        games_data = await igdb_service.multiquery_games(owned)
    except IGDBRateLimitException as e:
        return JSONResponse(status_code=429, content={"error": str(e)})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": "igdb_enrichment_failed", "detail": str(e)})

    matched_games = [g for g in games_data if g.get("igdb_id") is not None]

    session_token = secrets.token_urlsafe(16)
    session.add(
        PendingAuthPayload(
            session_token=session_token,
            id=xuid,
            provider="xbox",
            games=matched_games,
            created_at=datetime.now(UTC),
            expires_at=datetime.now(UTC) + timedelta(seconds=_pending_auth_ttl_seconds),
        )
    )
    await session.commit()

    return RedirectResponse(url=f"{settings.frontend_url}auth/complete#session={session_token}")