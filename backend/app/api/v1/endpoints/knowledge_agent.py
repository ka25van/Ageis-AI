from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.api.v1.endpoints.auth import get_current_user
from app.core.di import get_db_session
from app.models.user import User
from app.models.project import Project
from app.services.knowledge_agent import KnowledgeAgent, get_knowledge_agent

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


class SearchRequest(BaseModel):
    query: str
    project_id: str | None = None
    limit: int = 10


@router.post("/search")
async def retrieve_knowledge(
    body: SearchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    agent: KnowledgeAgent = Depends(get_knowledge_agent),
):
    pid = UUID(body.project_id) if body.project_id else None
    if pid:
        from app.models.project import Project
        result = await db.execute(
            select(Project).where(Project.id == pid, Project.owner_id == current_user.id)
        )
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Project not found")

    results = await agent.retrieve_knowledge(body.query, pid, body.limit)
    return results


@router.post("/hybrid")
async def hybrid_search(
    body: SearchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    agent: KnowledgeAgent = Depends(get_knowledge_agent),
):
    pid = UUID(body.project_id) if body.project_id else None
    if pid:
        from app.models.project import Project
        result = await db.execute(
            select(Project).where(Project.id == pid, Project.owner_id == current_user.id)
        )
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Project not found")

    results = await agent.hybrid_search(body.query, pid, body.limit)
    return results


class RankRequest(BaseModel):
    query: str
    results: list[dict]


@router.post("/rank")
async def rank_results(
    body: RankRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    agent: KnowledgeAgent = Depends(get_knowledge_agent),
):
    ranked = await agent.rank_results(body.results, body.query)
    return {"results": ranked, "count": len(ranked)}