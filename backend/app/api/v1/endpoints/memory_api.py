from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.api.v1.endpoints.auth import get_current_user
from app.core.di import get_db_session
from app.models.user import User
from app.services.memory import MemorySystem, get_memory_system

router = APIRouter(prefix="/memory", tags=["memory"])


@router.post("/short-term/{run_id}")
async def store_short_term(
    run_id: UUID,
    key: str,
    value: dict,
    db: AsyncSession = Depends(get_db_session),
    memory: MemorySystem = Depends(get_memory_system),
):
    await memory.store_short_term(run_id, key, value)
    return {"status": "stored"}


@router.get("/short-term/{run_id}/{key}")
async def get_short_term(
    run_id: UUID,
    key: str,
    db: AsyncSession = Depends(get_db_session),
    memory: MemorySystem = Depends(get_memory_system),
):
    value = await memory.get_short_term(run_id, key)
    if value is None:
        raise HTTPException(status_code=404, detail="Not found")
    return {"value": value}


@router.post("/long-term")
async def store_long_term(
    key: str,
    value: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    memory: MemorySystem = Depends(get_memory_system),
):
    await memory.store_long_term(current_user.id, key, value)
    return {"status": "stored"}


@router.get("/long-term/{key}")
async def get_long_term(
    key: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    memory: MemorySystem = Depends(get_memory_system),
):
    value = await memory.get_long_term(current_user.id, key)
    if value is None:
        raise HTTPException(status_code=404, detail="Not found")
    return {"value": value}


@router.post("/semantic")
async def store_semantic(
    text: str,
    embedding: list[float] = None,
    metadata: dict = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    memory: MemorySystem = Depends(get_memory_system),
):
    if embedding is None:
        emb = (await memory.embeddings.generate_embeddings([text]))[0]
    else:
        emb = embedding
    await memory.store_semantic(text, emb, metadata)
    return {"status": "stored"}


@router.post("/search")
async def search_semantic(
    query: str,
    limit: int = 5,
    threshold: float = 0.7,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    memory: MemorySystem = Depends(get_memory_system),
):
    results = await memory.search_semantic(query, limit, threshold)
    return {"results": results, "count": len(results)}


@router.get("/runs/{run_id}/summary")
async def summarize_run(
    run_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    memory: MemorySystem = Depends(get_memory_system),
):
    summary = await memory.summarize_run(run_id)
    return summary