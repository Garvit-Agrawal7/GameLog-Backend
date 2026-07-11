from dotenv import load_dotenv
load_dotenv()

import asyncio
import contextlib
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import steam_routes, igdb_routes, auth_routes, database_routes, xbox_routes
from app.cleanup import cleanup_expired_auth_rows


@asynccontextmanager
async def lifespan(app: FastAPI):
    await cleanup_expired_auth_rows()
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
