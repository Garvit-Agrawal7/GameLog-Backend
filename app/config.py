import os

class Settings:
    steam_api_key: str = os.getenv("STEAM_API_KEY")
    igdb_client_id: str = os.getenv("IGDB_CLIENT_ID") or os.getenv("CLIENT_ID")
    igdb_client_secret: str = os.getenv("IGDB_CLIENT_SECRET") or os.getenv("CLIENT_SECRET")
    steam_openid_url: str = "https://steamcommunity.com/openid/login"
    backend_url: str = "http://192.168.1.4:8000"
    return_url: str = "http://192.168.1.4:8000/auth/steam/callback"

settings = Settings()