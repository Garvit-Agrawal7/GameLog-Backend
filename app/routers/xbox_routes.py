from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse, JSONResponse
from app.xbox_auth import xbox_auth
from app.database import get_async_session
from app.rate_limit import allow_default_request
from sqlalchemy.ext.asyncio import AsyncSession


router = APIRouter(prefix="/auth", tags=["auth"])


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
    if not query_params:
        return JSONResponse(status_code=400, content={"error": "missing query"})

    return JSONResponse(content={"message": "xbox callback received", "query_params": query_params})
