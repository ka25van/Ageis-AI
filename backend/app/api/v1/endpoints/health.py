from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.di import get_db_session, get_redis_client

router = APIRouter()


@router.get("")
async def health_check():
    return {"status": "ok"}


@router.get("/db")
async def db_health_check(db: AsyncSession = Depends(get_db_session)):
    await db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "connected"}


@router.get("/redis")
async def redis_health_check(redis_client: Redis = Depends(get_redis_client)):
    await redis_client.ping()
    return {"status": "ok", "redis": "connected"}