from app.config import settings


class XboxAuth:
    def __init__(self) -> None:
        self.api_key: str = settings.xbox_api_key
        self.public_key: str = settings.xbox_public_key
        self.xbox_url: str = f"https://api.xbl.io/app/auth/{self.public_key}"

    def get_login_url(self) -> str:
        return self.xbox_url


xbox_auth = XboxAuth()
