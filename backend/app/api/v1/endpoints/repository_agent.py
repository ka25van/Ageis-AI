from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.api.v1.endpoints.auth import get_current_user
from app.core.di import get_db_session
from app.models.user import User
from app.models.project import Project, Repository
from app.services.repository_agent import RepositoryAgent, get_repository_agent
from app.services.context_builder import ContextBuilder, get_context_builder

router = APIRouter(prefix="/repo-agent", tags=["repository-agent"])


async def _resolve_repository(repository_id: UUID, db: AsyncSession):
    result = await db.execute(
        select(Repository, Project)
        .join(Project, Repository.project_id == Project.id)
        .where(Repository.id == repository_id)
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Repository not found")
    repo, _ = row
    if repo.indexing_status != "completed":
        raise HTTPException(status_code=400, detail=f"Repository not indexed (status: {repo.indexing_status})")
    return repo


@router.get("/{repository_id}/understand")
async def understand_code(
    repository_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    agent: RepositoryAgent = Depends(get_repository_agent),
    ctx_builder: ContextBuilder = Depends(get_context_builder),
):
    await _resolve_repository(repository_id, db)
    context = await ctx_builder.build(repository_id, "Understand the repository structure and architecture")
    result = await agent.process(context)
    await ctx_builder.after_agent("repository", result, "Understand repository structure")
    analysis = result["details"] if result.get("details") else {}
    if not analysis:
        analysis = await agent.understand_code(repository_id)
    return analysis


@router.get("/{repository_id}/summary")
async def summarize_architecture(
    repository_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    agent: RepositoryAgent = Depends(get_repository_agent),
    ctx_builder: ContextBuilder = Depends(get_context_builder),
):
    await _resolve_repository(repository_id, db)
    context = await ctx_builder.build(repository_id, "Summarize the project architecture")
    result = await agent.process(context)
    await ctx_builder.after_agent("repository", result, "Summarize architecture")
    analysis = result["details"] if result.get("details") else {}
    if not analysis:
        analysis = await agent.understand_code(repository_id)
    summary = await agent.summarize_architecture(repository_id)
    return summary


@router.get("/{repository_id}/search")
async def search_code(
    repository_id: UUID,
    query: str = Query(..., min_length=1),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    agent: RepositoryAgent = Depends(get_repository_agent),
):
    await _resolve_repository(repository_id, db)
    results = await agent.search_code(repository_id, query)
    return results