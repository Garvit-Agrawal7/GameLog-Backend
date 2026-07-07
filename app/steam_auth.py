from app.config import settings
from providers.steam_provider import steam_service
import httpx
import re
from urllib.parse import urlencode, parse_qsl

# Pattern to extract Steam ID from OpenID
STEAM_ID_PATTERN = re.compile(r"https?://steamcommunity\.com/openid/id/(\d+)")

async def create_token(steamid: int) -> dict:
    """Create a trimmed payload with steamid and game summary data."""

    games_response = await steam_service.get_owned_games(str(steamid))
    return steam_service.trim_steam_games(
        steamid,
        games_response if isinstance(games_response, dict) else {},
    )

class SteamOpenID:
    def __init__(self):
        self.steam_url = settings.steam_openid_url
        self.return_url = settings.return_url

    def get_login_url(self) -> str:
        params = {
            "openid.ns": "http://specs.openid.net/auth/2.0",
            "openid.mode": "checkid_setup",
            "openid.return_to": self.return_url,
            "openid.realm": settings.backend_url,
            "openid.identity": "http://specs.openid.net/auth/2.0/identifier_select",
            "openid.claimed_id": "http://specs.openid.net/auth/2.0/identifier_select"
        }
        return f"{self.steam_url}?{urlencode(params)}"

    async def verify_login(self, raw_query: str) -> int | None:
        """Verify an OpenID response using the raw query string."""
        # Parse into a dict without changing encoding
        query = dict(parse_qsl(raw_query, keep_blank_values=True))
        if query.get("openid.mode") != "id_res":
            return None

        # Compare return_to by origin+path
        try:
            from urllib.parse import urlparse

            rt = query.get("openid.return_to")
            if rt:
                pr = urlparse(rt)
                our = urlparse(self.return_url)
                if (pr.scheme, pr.netloc, pr.path) != (our.scheme, our.netloc, our.path):
                    return None
        except Exception:
            return None

        claimed_id = query.get("openid.claimed_id", "")
        match = STEAM_ID_PATTERN.match(claimed_id)
        if not match:
            return None

        # Replace mode in the raw query string so it can be posted as is
        verify_query = raw_query.replace("openid.mode=id_res", "openid.mode=check_authentication")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.steam_url,
                    content=verify_query,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    timeout=10,
                )
                if "is_valid:true" not in response.text:
                    return None
                return int(match.group(1))
        except Exception:
            return None

steam_openid = SteamOpenID()
