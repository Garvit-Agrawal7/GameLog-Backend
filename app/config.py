import os

class Settings:
    steam_api_key: str = os.getenv("STEAM_API_KEY")
    xbox_api_key: str = os.getenv("XBOX_API_KEY")
    xbox_public_key: str = os.getenv("XBOX_PUBLIC_KEY")
    igdb_client_id: str = os.getenv("IGDB_CLIENT_ID")
    igdb_client_secret: str = os.getenv("IGDB_CLIENT_SECRET")
    steam_openid_url: str = "https://steamcommunity.com/openid/login"
    backend_url: str = os.getenv("BACKEND_URL")
    return_url: str = f"{os.getenv('BACKEND_URL')}/auth/steam/callback"
    xbox_return_url: str = f"{os.getenv('BACKEND_URL')}/auth/xbox/callback"
    secret_key: str = os.getenv("SECRET_KEY")
    database_url: str = os.getenv("DATABASE_URL")
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_username: str = os.getenv("SMTP_USERNAME")
    smtp_password: str = os.getenv("SMTP_PASSWORD")
    frontend_url: str = os.getenv("FRONTEND_URL")

settings = Settings()
