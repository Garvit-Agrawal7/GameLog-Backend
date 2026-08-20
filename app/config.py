import os

class Settings:
    steam_api_key: str = os.getenv("STEAM_API_KEY")
    xbox_api_key: str = os.getenv("XBOX_API_KEY")
    xbox_public_key: str = os.getenv("XBOX_PUBLIC_KEY")
    xbox_app_key: str = os.getenv("AZURE_APP_ID")
    igdb_client_id: str = os.getenv("IGDB_CLIENT_ID")
    igdb_client_secret: str = os.getenv("IGDB_CLIENT_SECRET")
    steam_openid_url: str = "https://steamcommunity.com/openid/login"
    backend_url: str = os.getenv("BACKEND_URL")
    return_url: str = f"{os.getenv('BACKEND_URL')}/auth/steam/callback"
    xbox_return_url: str = f"{os.getenv('BACKEND_URL')}/auth/xbox/callback"
    secret_key: str = os.getenv("SECRET_KEY")
    database_url: str = os.getenv("DATABASE_URL")
    redis_url: str = os.getenv("REDIS_URL")
    gmail_sender_email: str = os.getenv("GMAIL_SENDER_EMAIL")
    gmail_client_id: str = os.getenv("GMAIL_CLIENT_ID")
    gmail_client_secret: str = os.getenv("GMAIL_CLIENT_SECRET")
    gmail_refresh_token: str = os.getenv("GMAIL_REFRESH_TOKEN")
    frontend_url: str = os.getenv("FRONTEND_URL")

settings = Settings()
