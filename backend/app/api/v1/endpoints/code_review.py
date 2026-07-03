from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.api.v1.endpoints.auth import get_current_user
from app.core.di import get_db_session
from app.models.user import User
from app.models.project import Project, Repository
from app.services.code_review_agent import CodeReviewAgent, get_code_review_agent
from app.services.context_builder import ContextBuilder, get_context_builder

router = APIRouter(prefix="/code-review", tags=["code-review"])


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


@router.post("/pr")
async def review_pr(
    body: RepoRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    agent: CodeReviewAgent = Depends(get_code_review_agent),
    ctx_builder: ContextBuilder = Depends(get_context_builder),
):
    rid = UUID(body.repository_id)
    await _resolve_repository(rid, db)
    context = await ctx_builder.build(rid, "Review code for pull request")
    result = await agent.process(context)
    await ctx_builder.after_agent("code_review", result, "PR review")
    if result.get("details"):
        return result["details"]
    return await agent.review_pr(rid)


@router.post("/security")
async def security_review(
    body: RepoRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    agent: CodeReviewAgent = Depends(get_code_review_agent),
):
    rid = UUID(body.repository_id)
    await _resolve_repository(rid, db)
    review = await agent.security_audit(rid)
    return review


@router.post("/best-practices")
async def best_practices(
    body: RepoRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    agent: CodeReviewAgent = Depends(get_code_review_agent),
    ctx_builder: ContextBuilder = Depends(get_context_builder),
):
    rid = UUID(body.repository_id)
    await _resolve_repository(rid, db)
    context = await ctx_builder.build(rid, "Analyze code best practices")
    result = await agent.process(context)
    await ctx_builder.after_agent("code_review", result, "Best practices analysis")
    if result.get("details"):
        return result["details"]
    return await agent.best_practices(rid)