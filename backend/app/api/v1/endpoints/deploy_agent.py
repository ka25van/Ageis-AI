from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.api.v1.endpoints.auth import get_current_user
from app.core.di import get_db_session
from app.models.user import User
from app.models.project import Project, Repository
from app.services.deploy_agent import DeployAgent, get_deploy_agent

router = APIRouter(prefix="/deploy", tags=["deploy"])


class RepoRequest(BaseModel):
    repository_id: str


@router.post("/analyze")
async def analyze_deployment(
    body: RepoRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    agent: DeployAgent = Depends(get_deploy_agent),
):
    rid = UUID(body.repository_id)
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

    analysis = await agent.analyze_deployment(rid)
    return analysis
