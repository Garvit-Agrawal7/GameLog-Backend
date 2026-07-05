import httpx
from app.config import settings


class SteamService:
    BASE_URL = "https://api.steampowered.com"

    def __init__(self):
        self._api_key = settings.steam_api_key
        self._client = httpx.AsyncClient(base_url=self.BASE_URL)

    async def get_player_summaries(self, steam_id: str) -> dict:
        url = "/ISteamUser/GetPlayerSummaries/v0002/"
        params = {"key": self._api_key, "steamids": steam_id}
        try:
            response = await self._client.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise Exception(f"Failed to load player summaries: {e}")

    async def get_owned_games(self, steam_id: str) -> dict:
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
