from app.config import settings
import httpx


class XboxAuth:
    def __init__(self) -> None:
        self.app_key = settings.xbox_app_key
        self.api_key: str = settings.xbox_api_key
        self.public_key: str = settings.xbox_public_key
        self.xbox_url: str = "https://api.xbl.io"

    def get_login_url(self) -> str:
        return self.xbox_url + f"/app/auth/{self.public_key}"

    async def verify_login(self, code: str) -> dict:
        """Checks OAuth code and returns the user's data dictionary, with values 'app_key', 'xuid', 'gamertag', 'avatar', 'email'"""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                claim_resp = await client.post(
                    self.xbox_url + "/app/claim",
                    json={"code": code, "app_key": self.app_key},
                    headers={"Content-Type": "application/json"},
                )
        except httpx.TimeoutException:
            raise ValueError("xbox claim request timed out")

        if claim_resp.status_code != 200:
            raise ValueError(
                f"xbox claim failed: status={claim_resp.status_code} body={claim_resp.text[:500]}"
            )

        try:
            return claim_resp.json()
        except ValueError:
            raise ValueError(
                f"xbox claim returned non-JSON body: status={claim_resp.status_code} body={claim_resp.text[:500]}"
            )
