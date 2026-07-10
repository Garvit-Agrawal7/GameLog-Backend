from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import JSONResponse

from app.auth import current_enabled_user
from services.igdb_service import IGDBRateLimitException, igdb_service

router = APIRouter(prefix="/igdb", tags=["igdb"], dependencies=[Depends(current_enabled_user)])


@router.get("/search")
async def search_games(query: str = Query(..., min_length=1), limit: int = Query(10, ge=1, le=100)):
    try:
        return await igdb_service.search_games(query, limit=limit)
    except IGDBRateLimitException as e:
        return JSONResponse(status_code=429, content={"error": str(e)})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/similar")
async def fetch_similar_games(game_id: int = Query(..., ge=1)):
    try:
        return await igdb_service.fetch_similar_games(game_id)
    except IGDBRateLimitException as e:
        return JSONResponse(status_code=429, content={"error": str(e)})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trending")
async def fetch_trending_games(limit: int = Query(10, ge=1, le=100)):
    try:
        return await igdb_service.fetch_trending_games(limit=limit)
    except IGDBRateLimitException as e:
        return JSONResponse(status_code=429, content={"error": str(e)})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/upcoming")
async def fetch_upcoming_games(limit: int = Query(10, ge=1, le=100)):
    try:
        return await igdb_service.fetch_upcoming_games(limit=limit)
    except IGDBRateLimitException as e:
        return JSONResponse(status_code=429, content={"error": str(e)})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/by-genre")
async def fetch_by_genre(genre: str = Query(..., min_length=1), limit: int = Query(10, ge=1, le=100)):
    try:
        return await igdb_service.fetch_by_genre(genre, limit=limit)
    except IGDBRateLimitException as e:
        return JSONResponse(status_code=429, content={"error": str(e)})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/enrich")
async def enrich_games(payload: Any = Body(...)):
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
async def fetch_time_to_beat(game_id: int):
    try:
        return {"game_id": game_id, "time_to_beat_hours": await igdb_service.fetch_time_to_beat(game_id)}
    except IGDBRateLimitException as e:
        return JSONResponse(status_code=429, content={"error": str(e)})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

