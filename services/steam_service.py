import httpx
from app.config import settings


class SteamService:
    BASE_URL = "https://api.steampowered.com"

    def __init__(self):
        self._api_key = settings.steam_api_key
        self._client = httpx.AsyncClient(base_url=self.BASE_URL)

    @staticmethod
    def _normalize_name(name: str) -> str:
        """Keep letters, digits, and spaces only, then collapse whitespace."""

        if not isinstance(name, str):
            return ""

        cleaned = "".join(
            ch if (ch.isalpha() or ch.isdigit() or ch.isspace()) else " "
            for ch in name
        )
        return " ".join(cleaned.split())

    @staticmethod
    def _extract_games(container: dict | None) -> list[dict]:
        if not isinstance(container, dict):
            return []
        return container.get("response", {}).get("games", []) or []

    def trim_steam_games(self, steamid: int | str, games_response: dict,) -> dict:
        """
        Trim the nested Steam games response into a compact format.

        Keeps owned games, keeps free games only when playtime is at least 60,
        and returns a normalized list with just the fields the frontend needs.
        """

        owned_games = self._extract_games(games_response.get("ownedGames"))
        free_games = self._extract_games(games_response.get("freeGames"))

        trimmed_games: list[dict] = []

        for game in owned_games:
            if not isinstance(game, dict):
                continue

            playtime = game.get("playtime_forever", 0) or 0
            trimmed_games.append(
                {
                    "name": self._normalize_name(game.get("name", "")),
                    "playtime_forever": round(playtime / 60, 2),
                    "rtime_last_played": game.get("rtime_last_played", 0),
                }
            )

        for game in free_games:
            if not isinstance(game, dict):
                continue

            playtime = game.get("playtime_forever", 0) or 0
            if playtime < 60:
                continue

            trimmed_games.append(
                {
                    "name": self._normalize_name(game.get("name", "")),
                    "playtime_forever": round(playtime / 60, 2),
                    "rtime_last_played": game.get("rtime_last_played", 0),
                }
            )

        return {
            "steamid": str(steamid),
            "game_count": len(trimmed_games),
            "games": trimmed_games,
        }

    # async def get_player_summaries(self, steam_id: str) -> dict:
    #     """Return player summaries for a steam id."""
    #     url = "/ISteamUser/GetPlayerSummaries/v0002/"
    #     params = {"key": self._api_key, "steamids": steam_id}
    #     try:
    #         response = await self._client.get(url, params=params)
    #         response.raise_for_status()
    #         return response.json()
    #     except Exception as e:
    #         raise Exception(f"Failed to load player summaries: {e}")

    async def get_owned_games(self, steam_id: str) -> dict:
        """Returns all user's owned games, and free games, and formats them together."""
        owned_games_params = {
            "key": self._api_key,
            "steamid": steam_id,
            "include_appinfo": "true",
        }
        free_games_params = {**owned_games_params, "include_played_free_games": "true"}

        try:
            owned_games_response = await self._client.get(
                "/IPlayerService/GetOwnedGames/v0001/", params=owned_games_params
            )
            free_games_response = await self._client.get(
                "/IPlayerService/GetOwnedGames/v0001/", params=free_games_params
            )

            owned_games = owned_games_response.json()
            free_games = free_games_response.json()

            owned_games_list = owned_games.get("response", {}).get("games", []) or []
            owned_app_ids = {
                game["appid"] for game in owned_games_list if isinstance(game.get("appid"), int)
            }

            free_games_list = [
                game
                for game in (free_games.get("response", {}).get("games", []) or [])
                if game.get("appid") not in owned_app_ids
            ]

            return {
                "ownedGames": owned_games,
                "freeGames": {
                    **free_games,
                    "response": {
                        **free_games.get("response", {}),
                        "games": free_games_list,
                    },
                },
            }
        except Exception as e:
            raise Exception(f"Failed to load owned and free games: {e}")

    async def close(self):
        await self._client.aclose()


steam_service = SteamService()
