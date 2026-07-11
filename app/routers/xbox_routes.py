from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse, JSONResponse
from app.xbox_auth import xbox_auth
from app.database import get_async_session
from app.rate_limit import rate_limiter
from sqlalchemy.ext.asyncio import AsyncSession


router = APIRouter(prefix="/auth", tags=["auth"])
_xbox_login_window_seconds = 1.0
_xbox_login_max_requests = 2


async def _allow_xbox_login(request: Request) -> bool:
    return await rate_limiter.allow(request, "xbox_login", _xbox_login_window_seconds, _xbox_login_max_requests)

@router.get("/xbox/login")
async def xbox_login(request: Request, session: AsyncSession = Depends(get_async_session)):
    if not await _allow_xbox_login(request):
        return JSONResponse(status_code=429, content={"error": "Too many xbox login requests"})
    return RedirectResponse(url=xbox_auth.get_login_url())


@router.get("/xbox/callback")
async def xbox_callback(request: Request, session: AsyncSession = Depends(get_async_session)):
    if not await _allow_xbox_login(request):
        return JSONResponse(status_code=429, content={"error": "Too many xbox callback requests"})
    query_params = dict(request.query_params)
    if not query_params:
        return JSONResponse(status_code=400, content={"error": "missing query"})

    return JSONResponse(content={"message": "xbox callback received", "query_params": query_params})
