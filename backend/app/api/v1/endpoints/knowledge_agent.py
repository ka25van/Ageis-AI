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


@router.post("/search")
async def retrieve_knowledge(
    query: str,
    project_id: UUID = None,
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    agent: KnowledgeAgent = Depends(get_knowledge_agent),
):
    if project_id:
        from app.models.project import Project
        result = await db.execute(
            select(Project).where(Project.id == project_id, Project.owner_id == current_user.id)
        )
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Project not found")

    results = await agent.retrieve_knowledge(query, project_id, limit)
    return results


@router.post("/hybrid")
async def hybrid_search(
    query: str,
    project_id: UUID = None,
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    agent: KnowledgeAgent = Depends(get_knowledge_agent),
):
    if project_id:
        from app.models.project import Project
        result = await db.execute(
            select(Project).where(Project.id == project_id, Project.owner_id == current_user.id)
        )
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Project not found")

    results = await agent.hybrid_search(query, project_id, limit)
    return results


@router.post("/rank")
async def rank_results(
    query: str,
    results: list[dict],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    agent: KnowledgeAgent = Depends(get_knowledge_agent),
):
    ranked = await agent.rank_results(results, query)
    return {"results": ranked, "count": len(ranked)}