from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import steam_routes, igdb_routes, auth_routes, database_routes, xbox_routes


app = FastAPI(
    title="Game Library Backend",
    description="Steam OpenID authentication backend for game library app",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
