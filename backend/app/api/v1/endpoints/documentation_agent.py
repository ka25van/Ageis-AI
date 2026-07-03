from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.api.v1.endpoints.auth import get_current_user
from app.core.di import get_db_session
from app.models.user import User
from app.models.project import Project, Repository
from app.services.documentation_agent import DocumentationAgent, get_documentation_agent
from app.services.context_builder import ContextBuilder, get_context_builder

router = APIRouter(prefix="/docs", tags=["documentation"])


class RepoRequest(BaseModel):
    repository_id: str


async def _resolve_repository(rid: UUID, db: AsyncSession):
    result = await db.execute(
        select(Repository, Project)
        .join(Project, Repository.project_id == Project.id)
        .where(Repository.id == rid)
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Repository not found")
    repo, _ = row
    if repo.indexing_status != "completed":
        raise HTTPException(status_code=400, detail=f"Repository not indexed (status: {repo.indexing_status})")
    return repo


@router.post("/readme")
async def generate_readme(
    body: RepoRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    agent: DocumentationAgent = Depends(get_documentation_agent),
    ctx_builder: ContextBuilder = Depends(get_context_builder),
):
    rid = UUID(body.repository_id)
    await _resolve_repository(rid, db)
    context = await ctx_builder.build(rid, "Generate README documentation")
    result = await agent.process(context)
    await ctx_builder.after_agent("documentation", result, "Generate README")
    if result.get("details"):
        return result["details"]
    return await agent.generate_readme(rid)


@router.post("/api")
async def generate_api_docs(
    body: RepoRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    agent: DocumentationAgent = Depends(get_documentation_agent),
    ctx_builder: ContextBuilder = Depends(get_context_builder),
):
    rid = UUID(body.repository_id)
    await _resolve_repository(rid, db)
    context = await ctx_builder.build(rid, "Generate API documentation")
    result = await agent.process(context)
    await ctx_builder.after_agent("documentation", result, "Generate API docs")
    if result.get("details"):
        return result["details"]
    return await agent.generate_api_documentation(rid)


@router.post("/architecture")
async def generate_architecture_docs(
    body: RepoRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    agent: DocumentationAgent = Depends(get_documentation_agent),
    ctx_builder: ContextBuilder = Depends(get_context_builder),
):
    rid = UUID(body.repository_id)
    await _resolve_repository(rid, db)
    context = await ctx_builder.build(rid, "Generate architecture documentation")
    result = await agent.process(context)
    await ctx_builder.after_agent("documentation", result, "Generate architecture docs")
    if result.get("details"):
        return result["details"]
    return await agent.generate_architecture_documentation(rid)