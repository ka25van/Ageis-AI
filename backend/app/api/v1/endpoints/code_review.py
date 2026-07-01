from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.api.v1.endpoints.auth import get_current_user
from app.core.di import get_db_session
from app.models.user import User
from app.models.project import Project, Repository
from app.services.code_review_agent import CodeReviewAgent, get_code_review_agent

router = APIRouter(prefix="/code-review", tags=["code-review"])


@router.post("/pr")
async def review_pr(
    repository_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    agent: CodeReviewAgent = Depends(get_code_review_agent),
):
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

    review = await agent.review_pr(repository_id)
    return review


@router.post("/security")
async def security_review(
    repository_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    agent: CodeReviewAgent = Depends(get_code_review_agent),
):
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

    review = await agent.security_review(repository_id)
    return review


@router.post("/best-practices")
async def best_practices(
    repository_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    agent: CodeReviewAgent = Depends(get_code_review_agent),
):
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

    review = await agent.best_practices(repository_id)
    return review