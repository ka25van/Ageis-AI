from fastapi import APIRouter, Depends
from redis.asyncio import Redis

from app.core.redis import get_redis

router = APIRouter()


@router.get("")
async def health_check():
    return {"status": "ok"}


@router.get("/db")
async def db_health_check():
    return {"status": "ok", "database": "connected"}


@router.get("/redis")
async def redis_health_check(redis_client: Redis = Depends(get_redis)):
    await redis_client.ping()
    return {"status": "ok", "redis": "connected"}