import httpx
from app.config import settings

class XboxService:
    BASE_URL = "https://api.xbl.io"

    def __init__(self):
        self.api_key = settings.xbox_api_key
        self._client = httpx.Client(base_url=self.BASE_URL)

    async def get_owned_games(self, xuid: str) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"https://api.xbl.io/v2/titles/{xuid}",
                headers={"X-Authorization": self.api_key},
            )
            if resp.status_code != 200:
                raise ValueError(
                    f"xbox titles fetch failed: {resp.status_code} {resp.text}"
                )
            data = resp.json()
        titles = data.get("content", {}).get("titles", [])
        return [
            {
                "name": t.get("name"),
                "type": t.get("type"),
                "progressPercentage": t.get("achievement", {}).get("progressPercentage"),
                "currentAchievements": t.get("achievement", {}).get("currentAchievements"),
                "lastTimePlayed": t.get("titleHistory", {}).get("lastTimePlayed"),
            }
            for t in titles
        ]

xbox_service = XboxService()