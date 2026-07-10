from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, JSONResponse
from app.xbox_auth import xbox_auth


router = APIRouter(prefix="/auth", tags=["auth"])

@router.get("/xbox/login")
async def xbox_login(request: Request):
    return RedirectResponse(url=xbox_auth.get_login_url())


@router.get("/xbox/callback")
async def xbox_callback(request: Request):
    query_params = dict(request.query_params)
    if not query_params:
        return JSONResponse(status_code=400, content={"error": "missing query"})

    return JSONResponse(content={"message": "xbox callback received", "query_params": query_params})
