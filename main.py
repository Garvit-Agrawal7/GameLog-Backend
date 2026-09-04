from dotenv import load_dotenv
load_dotenv()

import asyncio
import contextlib
from contextlib import asynccontextmanager
import logging
import httpx

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import steam_routes, igdb_routes, auth_routes, database_routes, xbox_routes
from app.cleanup import cleanup_expired_auth_rows
from app.database import Base, engine
from app import models
from app.rate_limit import rate_limiter

from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware


logger = logging.getLogger(__name__)
async def _ensure_database_schema() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await _ensure_database_schema()
    await cleanup_expired_auth_rows()
    redis_ready = await rate_limiter.ping()
    if not redis_ready:
        logger.warning("Redis rate limiting is unavailable; falling back to in-memory throttling")
    cleanup_task = asyncio.create_task(_run_periodic_cleanup())
    try:
        yield
    finally:
        cleanup_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await cleanup_task


async def _run_periodic_cleanup() -> None:
    while True:
        await asyncio.sleep(900)
        await cleanup_expired_auth_rows()


app = FastAPI(
    title="Game Library Backend",
    description="Steam OpenID authentication backend for game library app",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(steam_routes.router)
app.include_router(auth_routes.router)
app.include_router(igdb_routes.router)
app.include_router(database_routes.router)
app.include_router(xbox_routes.router)

@app.get("/")
async def root():
    return {"message": "Game Library Backend", "status": "running"}

app = ProxyHeadersMiddleware(app, trusted_hosts="*")

