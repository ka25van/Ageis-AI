from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.api.v1.endpoints.auth import get_current_user
from app.core.di import get_db_session
from app.models.user import User
from app.models.project import Project, Repository
from app.services.incident_agent import IncidentAgent, get_incident_agent

router = APIRouter(prefix="/incidents", tags=["incidents"])


@router.post("/analyze")
async def analyze_logs(
    repository_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    agent: IncidentAgent = Depends(get_incident_agent),
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

    analysis = await agent.analyze_incidents(repository_id)
    return analysis


@router.post("/root-cause")
async def root_cause_analysis(
    repository_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    agent: IncidentAgent = Depends(get_incident_agent),
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

    analysis = await agent.root_cause_analysis(repository_id)
    return analysis


@router.post("/recommendations")
async def get_recommendations(
    repository_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    agent: IncidentAgent = Depends(get_incident_agent),
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

    analysis = await agent.analyze_errors(repository_id)
    return {"recommendations": analysis.get("recommendations", [])}