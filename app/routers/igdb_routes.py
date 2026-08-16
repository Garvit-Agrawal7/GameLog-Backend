from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from app.auth import current_enabled_user
from app.rate_limit import allow_igdb_request
from services.igdb_service import IGDBRateLimitException, igdb_service
from app.redis_caching import redis_cache

router = APIRouter(prefix="/igdb", tags=["igdb"], dependencies=[Depends(current_enabled_user)])


@router.get("/search")
async def search_games(request: Request, query: str = Query(..., min_length=1), limit: int = Query(10, ge=1, le=100)):
    # Search results are not cached, frontend already does that.
    if not await allow_igdb_request(request):
        return JSONResponse(status_code=429, content={"error": "Too many IGDB requests"})

    try:
        return await igdb_service.search_games(query, limit=limit)
    except IGDBRateLimitException as e:
        return JSONResponse(status_code=429, content={"error": str(e)})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/similar")
async def fetch_similar_games(request: Request, game_id: int = Query(..., ge=1)):
    cache_key = f"cache:igdb:similar:{game_id}"

    async def fetch():
        if not await allow_igdb_request(request):
            raise IGDBRateLimitException("Too many IGDB requests")
        return await igdb_service.fetch_similar_games(game_id)

    try:
        return await redis_cache.get_or_fetch(cache_key, fetch)
    except IGDBRateLimitException as e:
        return JSONResponse(status_code=429, content={"error": str(e)})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trending")
async def fetch_trending_games(request: Request, limit: int = Query(10, ge=1, le=100)):
    cache_key = f"cache:igdb:trending:{limit}"

    async def fetch():
        if not await allow_igdb_request(request):
            raise IGDBRateLimitException("Too many IGDB requests")
        return await igdb_service.fetch_trending_games(limit=limit)

    try:
        return await redis_cache.get_or_fetch(cache_key, fetch)
    except IGDBRateLimitException as e:
        return JSONResponse(status_code=429, content={"error": str(e)})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/upcoming")
async def fetch_upcoming_games(request: Request, limit: int = Query(10, ge=1, le=100)):
    cache_key = f"cache:igdb:upcoming:{limit}"

    async def fetch():
        if not await allow_igdb_request(request):
            raise IGDBRateLimitException("Too many IGDB requests")
        return await igdb_service.fetch_upcoming_games(limit=limit)

    try:
        return await redis_cache.get_or_fetch(cache_key, fetch)
    except IGDBRateLimitException as e:
        return JSONResponse(status_code=429, content={"error": str(e)})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/by-genre")
async def fetch_by_genre(request: Request, genre: str = Query(..., min_length=1), limit: int = Query(10, ge=1, le=100)):
    cache_key = f"cache:igdb:by-genre:{genre}:{limit}"

    async def fetch():
        if not await allow_igdb_request(request):
            raise IGDBRateLimitException("Too many IGDB requests")
        return await igdb_service.fetch_by_genre(genre, limit=limit)

    try:
        return await redis_cache.get_or_fetch(cache_key, fetch)
    except IGDBRateLimitException as e:
        return JSONResponse(status_code=429, content={"error": str(e)})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/enrich")
async def enrich_games(request: Request, payload: Any = Body(...)):
    # Not cached, per user entry.
    if not await allow_igdb_request(request):
        return JSONResponse(status_code=429, content={"error": "Too many IGDB requests"})

    try:
        seeds = payload.get("seeds") if isinstance(payload, dict) else payload
        if not isinstance(seeds, list):
            raise HTTPException(status_code=400, detail="Expected a list of seeds or an object with a seeds list")
        return await igdb_service.enrich_games(seeds)
    except IGDBRateLimitException as e:
        return JSONResponse(status_code=429, content={"error": str(e)})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/time-to-beat/{game_id}")
async def fetch_time_to_beat(request: Request, game_id: int):
    cache_key = f"cache:igdb:time-to-beat:{game_id}"

    async def fetch():
        if not await allow_igdb_request(request):
            raise IGDBRateLimitException("Too many IGDB requests")
        hours = await igdb_service.fetch_time_to_beat(game_id)
        return {"game_id": game_id, "time_to_beat_hours": hours}

    try:
        return await redis_cache.get_or_fetch(cache_key, fetch)
    except IGDBRateLimitException as e:
        return JSONResponse(status_code=429, content={"error": str(e)})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
