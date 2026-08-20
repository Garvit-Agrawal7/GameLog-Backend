from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse, JSONResponse
from app.xbox_auth import xbox_auth
from app.database import get_async_session
from app.rate_limit import allow_default_request
from sqlalchemy.ext.asyncio import AsyncSession

from services.xbox_service import xbox_service


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

    owned = await xbox_service.get_owned_games(user_details["xuid"])
    print(owned)

    return JSONResponse(content={"message": "xbox callback received", "profile": user_details})
