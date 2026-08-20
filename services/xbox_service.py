import httpx
from app.config import settings

class XboxService:
    BASE_URL = "https://api.xbl.io"

    def __init__(self):
        self.api_key = settings.xbox_api_key
        self._client = httpx.Client(base_url=self.BASE_URL)
