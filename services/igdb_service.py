import asyncio
import datetime as dt
import time
from typing import Any

import httpx

from app.config import settings


class IGDBRateLimitException(Exception):
    pass


class IGDBService:
    BASE_URL = "https://api.igdb.com/v4"
    TOKEN_URL = "https://id.twitch.tv/oauth2/token"

    def __init__(self):
        self._client = httpx.AsyncClient(base_url=self.BASE_URL)
        self._access_token: str | None = None
        self._token_expires_at: float = 0.0
        self._token_lock = asyncio.Lock()

    @staticmethod
    def _require_credentials() -> tuple[str, str]:
        client_id = settings.igdb_client_id
        client_secret = settings.igdb_client_secret
        if not client_id or not client_secret:
            raise ValueError("IGDB client credentials are not configured")
        return client_id, client_secret

    async def _get_access_token(self) -> str:
        if self._access_token and time.monotonic() < self._token_expires_at:
            return self._access_token

        async with self._token_lock:
            if self._access_token and time.monotonic() < self._token_expires_at:
                return self._access_token

            client_id, client_secret = self._require_credentials()
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.TOKEN_URL,
                    params={
                        "client_id": client_id,
                        "client_secret": client_secret,
                        "grant_type": "client_credentials",
                    },
                    headers={"Accept": "application/json"},
                    timeout=20,
                )
                response.raise_for_status()
                data = response.json()

            access_token = data.get("access_token")
            expires_in = data.get("expires_in", 0)
            if not isinstance(access_token, str) or not access_token:
                raise RuntimeError("IGDB access token missing")

            self._access_token = access_token
            self._token_expires_at = time.monotonic() + max(int(expires_in) - 60, 60)
            return access_token

    async def _post(self, path: str, query: str) -> list[dict[str, Any]]:
        token = await self._get_access_token()
        client_id, _ = self._require_credentials()

        response = await self._client.post(
            path,
            content=query,
            headers={
                "Accept": "application/json",
                "Client-ID": client_id,
                "Authorization": f"Bearer {token}",
            },
            timeout=30,
        )

        if response.status_code == 429:
            raise IGDBRateLimitException("Slow Down bruh")

        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            return []
        return [item for item in payload if isinstance(item, dict)]

    async def search_games(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        trimmed_query = query.strip()
        if not trimmed_query:
            return []
        if not settings.igdb_client_id or not settings.igdb_client_secret:
            return []

        escaped_query = trimmed_query.replace('"', '\\"')
        igdb_query = (
            f'search "{escaped_query}"; '
            'fields name,summary,cover.image_id,genres.name,first_release_date,rating,rating_count; '
            'where game_type = (0,3,8,9,10); '
            f'limit {limit};'
        )
        return await self._post("/games", igdb_query)

    async def fetch_similar_games(self, game_id: int) -> list[dict[str, Any]]:
        if not settings.igdb_client_id or not settings.igdb_client_secret:
            return []
        igdb_query = (
            "fields similar_games.name,similar_games.summary,similar_games.cover.image_id,"
            "similar_games.genres.name,similar_games.first_release_date,similar_games.rating,"
            "similar_games.rating_count; "
            f"where id = {game_id}; "
            "limit 1;"
        )
        games = await self._post("/games", igdb_query)
        if not games:
            return []

        game = games[0]
        similar_games = [
            item
            for item in (game.get("similar_games") or [])
            if isinstance(item, dict)
            and item.get("rating") is not None
            and item.get("rating_count") is not None
        ]
        return self._calculate_rating_order(similar_games, minimum_votes=50)

    async def fetch_trending_games(self, limit: int = 10) -> list[dict[str, Any]]:
        if not settings.igdb_client_id or not settings.igdb_client_secret:
            return []
        year_start = int(dt.datetime.now().replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0).timestamp())
        igdb_query = (
            'fields name,summary,cover.image_id,genres.name,first_release_date,rating,rating_count; '
            f'where first_release_date > {year_start} & rating != null & rating_count != null & game_type = (0,8,9); '
            'sort rating_count desc; '
            f'limit {limit};'
        )
        games = await self._post("/games", igdb_query)
        ranked = self._calculate_rating_order(games)
        return ranked[:limit]

    async def fetch_upcoming_games(self, limit: int = 10) -> list[dict[str, Any]]:
        if not settings.igdb_client_id or not settings.igdb_client_secret:
            return []
        now = int(dt.datetime.now().timestamp())
        year_end = int((dt.datetime.now() + dt.timedelta(days=365)).timestamp())
        igdb_query = (
            'fields name,summary,cover.image_id,genres.name,first_release_date,rating; '
            f'where first_release_date > {now} & first_release_date < {year_end} & hypes != null & game_type = 0; '
            'sort hypes desc; '
            f'limit {limit};'
        )
        return await self._post("/games", igdb_query)

    async def fetch_by_genre(self, genre: str, limit: int = 10) -> list[dict[str, Any]]:
        trimmed_genre = genre.strip()
        if not trimmed_genre:
            return []
        if not settings.igdb_client_id or not settings.igdb_client_secret:
            return []

        escaped_genre = trimmed_genre.replace('"', '\\"')
        igdb_query = (
            'fields name,summary,cover.image_id,genres.name,first_release_date,rating,rating_count; '
            f'where genres.name = "{escaped_genre}" & rating != null & rating_count != null & game_type = (0,8,9); '
            'sort rating_count desc; '
            f'limit {limit};'
        )
        games = await self._post("/games", igdb_query)
        return self._calculate_rating_order(games, minimum_votes=50)[:limit]


    async def multiquery_games(self, seeds: list[dict]) -> list[dict]:
        """
        Batch-fetch IGDB data for Steam game seeds via IGDB's multiquery
        endpoint, chunked to stay under IGDB's per-request sub-query limit.
        """
        chunk_size = 10
        if not seeds:
            return []
        if not settings.igdb_client_id or not settings.igdb_client_secret:
            return [{"steam_name": seed.get("name"), "playtime_forever": seed.get("playtime_forever"), "rtime_last_played": seed.get("rtime_last_played"), "igdb_id": None} for seed in seeds if isinstance(seed, dict)]

        all_results: list[dict] = []
        for chunk_start in range(0, len(seeds), chunk_size):
            chunk = seeds[chunk_start:chunk_start + chunk_size]

            query_blocks = []
            for i, seed in enumerate(chunk):
                name_escaped = seed["name"].replace('"', '\\"')
                if name_escaped == "Grand Theft Auto V Legacy":
                    name_escaped = "Grand Theft Auto V"
                query_blocks.append(
                    f'query games "{i}" {{'
                    f'fields name,summary,cover.image_id,genres.name,first_release_date,rating,rating_count; '
                    f'where name = "{name_escaped}" & game_type = (0,8,9,10);'
                    f'sort rating_count desc;'
                    f'limit 10;'
                    f'}};'
                )

            multiquery_body = "\n".join(query_blocks)

            chunk_results = await self._post("/multiquery", multiquery_body)

            for i, seed in enumerate(chunk):
                result_block = next((r for r in chunk_results if r.get("name") == str(i)), None)
                candidates = result_block.get("result", []) if result_block else []

                game = self._pick_best_match(seed["name"], candidates)

                if game:
                    cover_id = self._read_cover_id(game)
                    all_results.append({
                        "steam_name": seed["name"],
                        "playtime_forever": seed.get("playtime_forever"),
                        "rtime_last_played": seed.get("rtime_last_played"),
                        "igdb_id": game.get("id"),
                        "igdb_name": game.get("name"),
                        "cover_url": self._cover_url(cover_id) if cover_id else None,
                        "summary": game.get("summary"),
                        "genres": self._read_genres(game),
                        "release_date": game.get("first_release_date"),
                        "rating": game.get("rating"),
                    })
                else:
                    all_results.append({
                        "steam_name": seed["name"],
                        "playtime_forever": seed.get("playtime_forever"),
                        "rtime_last_played": seed.get("rtime_last_played"),
                        "igdb_id": None,
                    })

        return all_results

    async def enrich_games(self, seeds: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not seeds:
            return []
        if not settings.igdb_client_id or not settings.igdb_client_secret:
            return [seed for seed in seeds if isinstance(seed, dict)]

        normalized_seeds = [seed for seed in seeds if isinstance(seed, dict)]
        if not normalized_seeds:
            return []

        if len(normalized_seeds) == 1:
            return [await self._fetch_game_by_title(normalized_seeds[0])]

        try:
            payload = await self._multiquery(normalized_seeds)
            if not payload:
                return await asyncio.gather(*(self._fetch_game_by_title(seed) for seed in normalized_seeds))

            result_by_index: dict[int, list[dict[str, Any]]] = {}
            for item in payload:
                if not isinstance(item, dict):
                    continue
                name = item.get("name")
                result = item.get("result")
                if not isinstance(name, str) or not isinstance(result, list):
                    continue
                index = int(name) if name.isdigit() else None
                if index is not None:
                    result_by_index[index] = [entry for entry in result if isinstance(entry, dict)]

            enriched: list[dict[str, Any]] = []
            for index, seed in enumerate(normalized_seeds):
                payload = result_by_index.get(index)
                if not payload:
                    enriched.append(await self._fetch_game_by_title(seed))
                    continue

                best_match = self._pick_best_match(seed.get("title", ""), payload) or payload[0]
                enriched.append(self._merge_seed_with_game(seed, best_match))

            return enriched
        except Exception:
            return await asyncio.gather(*(self._fetch_game_by_title(seed) for seed in normalized_seeds))

    async def fetch_time_to_beat(self, game_id: int) -> int | None:
        if not settings.igdb_client_id or not settings.igdb_client_secret:
            return None
        igdb_query = f"fields hastily; where game_id = {game_id}; limit 1;"
        items = await self._post("/game_time_to_beats", igdb_query)
        if not items:
            return None

        hastily = items[0].get("hastily")
        if isinstance(hastily, (int, float)):
            return round(float(hastily) / 3600)
        return None

    async def close(self):
        await self._client.aclose()

    async def _fetch_game_by_title(self, seed: dict[str, Any]) -> dict[str, Any]:
        title = str(seed.get("title", "")).strip()
        if not title:
            return seed

        try:
            payload = await self.search_games(title, limit=5)
            if not payload:
                return seed

            best_match = self._pick_best_match(title, payload) or payload[0]
            return self._merge_seed_with_game(seed, best_match)
        except Exception:
            return seed

    async def _multiquery(self, seeds: list[dict[str, Any]]) -> list[dict[str, Any]]:
        buffer: list[str] = []
        for index, seed in enumerate(seeds):
            title = str(seed.get("title", "")).replace('"', '\\"')
            buffer.append(
                "\n".join(
                    [
                        f'query games "{index}" {{',
                        f'  search "{title}";',
                        '  fields name,summary,cover.image_id,genres.name,first_release_date,rating;',
                        '  limit 5;',
                        '};',
                    ]
                )
            )
        query = "\n\n".join(buffer)
        token = await self._get_access_token()
        client_id, _ = self._require_credentials()

        response = await self._client.post(
            "/multiquery",
            content=query,
            headers={
                "Accept": "application/json",
                "Client-ID": client_id,
                "Authorization": f"Bearer {token}",
            },
            timeout=30,
        )

        if response.status_code == 429:
            raise IGDBRateLimitException("Slow Down bruh")

        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            return []
        return [item for item in payload if isinstance(item, dict)]

    def _merge_seed_with_game(self, seed: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
        cover_id = self._read_cover_id(data)
        genres = self._read_genres(data)
        rating = self._read_rating(data)
        summary = data.get("summary") or data.get("description")
        year = self._read_year(data)

        return {
            "id": seed.get("id", data.get("id", hash(seed.get("title", "")))),
            "title": data.get("name") or seed.get("title", ""),
            "coverUrl": self._cover_url(cover_id) if cover_id else seed.get("coverUrl", ""),
            "genres": genres or seed.get("genres", []),
            "summary": summary if isinstance(summary, str) and summary.strip() else seed.get("summary", ""),
            "rating": rating if rating is not None else seed.get("rating", 0),
            "hoursPlayed": seed.get("hoursPlayed", 0),
            "status": seed.get("status"),
            "year": year if year is not None else seed.get("year"),
            "inLibrary": seed.get("inLibrary", False),
            "lastUpdated": seed.get("lastUpdated", ""),
            "timeToBeatHours": seed.get("timeToBeatHours"),
        }

    def _pick_best_match(self, seed_title: str, payload: list[dict[str, Any]]) -> dict[str, Any] | None:
        target = self._normalize_title(seed_title)
        best_match: dict[str, Any] | None = None
        best_score = -1

        for item in payload:
            name = item.get("name")
            if not isinstance(name, str) or not name.strip():
                continue

            score = self._score_title_match(target, self._normalize_title(name), item.get("first_release_date"))
            if score > best_score:
                best_score = score
                best_match = item

        return best_match if best_score >= 60 else None

    def _calculate_rating_order(
        self,
        games: list[dict[str, Any]],
        minimum_votes: int = 100,
    ) -> list[dict[str, Any]]:
        if not games:
            return games

        ratings = [float(game.get("rating", 0) or 0) for game in games]
        global_average = sum(ratings) / len(ratings) if ratings else 0

        scored: list[tuple[dict[str, Any], float]] = []
        for game in games:
            rating = float(game.get("rating", 0) or 0)
            votes = int(game.get("rating_count", 0) or 0)
            denominator = votes + minimum_votes
            weighted_score = ((votes / denominator) * rating) + ((minimum_votes / denominator) * global_average) if denominator else rating
            scored.append((game, weighted_score))

        scored.sort(key=lambda item: item[1], reverse=True)
        return [item[0] for item in scored]

    def _score_title_match(self, target: str, candidate: str, release_date: Any) -> int:
        if candidate == target:
            return 1000

        score = 0
        if candidate.startswith(target) or target.startswith(candidate):
            score += 500

        target_tokens = {token for token in target.split(" ") if token}
        candidate_tokens = {token for token in candidate.split(" ") if token}
        overlap = len(target_tokens.intersection(candidate_tokens))
        score += overlap * 40

        score -= abs(len(target_tokens) - len(candidate_tokens)) * 3

        if isinstance(release_date, int):
            score += 10

        return score

    def _normalize_title(self, input_value: str) -> str:
        replacements = {
            "à": "a",
            "á": "a",
            "â": "a",
            "ã": "a",
            "ä": "a",
            "å": "a",
            "æ": "ae",
            "ç": "c",
            "è": "e",
            "é": "e",
            "ê": "e",
            "ë": "e",
            "ì": "i",
            "í": "i",
            "î": "i",
            "ï": "i",
            "ñ": "n",
            "ò": "o",
            "ó": "o",
            "ô": "o",
            "õ": "o",
            "ö": "o",
            "œ": "oe",
            "ù": "u",
            "ú": "u",
            "û": "u",
            "ü": "u",
            "ý": "y",
            "ÿ": "y",
        }

        lowered = input_value.lower()
        buffer: list[str] = []
        for char in lowered:
            buffer.append(replacements.get(char, char))

        return " ".join("".join(buffer).split())

    def _read_cover_id(self, data: dict[str, Any]) -> str | None:
        cover = data.get("cover")
        if isinstance(cover, dict):
            value = cover.get("image_id")
            return value if isinstance(value, str) else None
        return None

    def _read_genres(self, data: dict[str, Any]) -> list[str]:
        raw = data.get("genres")
        if not isinstance(raw, list):
            return []

        genres: list[str] = []
        for genre in raw:
            if not isinstance(genre, dict):
                continue
            name = genre.get("name")
            if isinstance(name, str) and name.strip():
                genres.append(name)
        return genres

    def _read_rating(self, data: dict[str, Any]) -> float | None:
        rating = data.get("rating")
        return float(rating) if isinstance(rating, (int, float)) else None

    def _read_year(self, data: dict[str, Any]) -> int | None:
        release = data.get("first_release_date")
        if isinstance(release, int):
            return dt.datetime.fromtimestamp(release).year
        return None

    def _cover_url(self, image_id: str) -> str:
        return f"https://images.igdb.com/igdb/image/upload/t_720p/{image_id}.jpg"


igdb_service = IGDBService()
