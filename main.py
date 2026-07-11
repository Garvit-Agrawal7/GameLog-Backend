from dotenv import load_dotenv
load_dotenv()

import asyncio
import contextlib
import os
from contextlib import asynccontextmanager
import logging

from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import steam_routes, igdb_routes, auth_routes, database_routes, xbox_routes
from app.cleanup import cleanup_expired_auth_rows
from app.rate_limit import rate_limiter


logger = logging.getLogger(__name__)


def _run_database_migrations() -> None:
    alembic_cfg = Config(os.path.join(os.path.dirname(__file__), "alembic.ini"))
    command.upgrade(alembic_cfg, "head")


@asynccontextmanager
async def lifespan(app: FastAPI):
    _run_database_migrations()
    await cleanup_expired_auth_rows()
    redis_ready = await rate_limiter.ping()
    if redis_ready:
        logger.info("Redis rate limiting is available")
    else:
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
