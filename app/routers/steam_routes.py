import secrets
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, JSONResponse
from app.steam_auth import steam_openid, create_token

router = APIRouter(prefix="/auth", tags=["auth"])
pending_auth_payloads: dict[str, dict] = {}

@router.get("/steam/login")
async def steam_login():
    return RedirectResponse(url=steam_openid.get_login_url())

@router.get("/steam/callback")
async def steam_callback(request: Request):
    # Use raw query to preserve exact percent-encoding
    raw_query = request.url.query
    if not raw_query:
        return JSONResponse(status_code=400, content={"error": "missing query"})

    steamid = await steam_openid.verify_login(raw_query)
    if not steamid:
        return JSONResponse(status_code=401, content={"error": "verification failed"})

    try:
        payload = await create_token(steamid)
    except Exception as e:
        # Return a JSON error instead of letting an unhandled exception produce HTTP 500
        return JSONResponse(status_code=500, content={"error": "payload_creation_failed", "detail": str(e)})

    session_token = secrets.token_urlsafe(16)
    pending_auth_payloads[session_token] = payload

    return RedirectResponse(url=f"gamelog://auth/complete#session={session_token}")

@router.get("/session/{session_token}")
async def get_session_payload(session_token: str):
    payload = pending_auth_payloads.pop(session_token, None)
    if payload is None:
        return JSONResponse(status_code=404, content={"error": "session not found or expired"})
    return payload
