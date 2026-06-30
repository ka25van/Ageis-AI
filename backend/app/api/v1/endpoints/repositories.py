from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.api.v1.endpoints.auth import get_current_user
from app.core.di import get_db_session
from app.models.user import User
from app.models.project import Repository, Project
from app.services.ingestion import RepositoryIngestionService, get_ingestion_service

router = APIRouter(prefix="/repositories", tags=["repositories"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_repository(
    project_id: UUID,
    name: str,
    url: str,
    branch: str = "main",
    provider: str = "github",
    access_token: str | None = None,
    is_private: bool = True,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == current_user.id)
    )
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    repository = Repository(
        project_id=project_id,
        name=name,
        url=url,
        branch=branch,
        provider=provider,
        access_token_encrypted=access_token,  # TODO: encrypt
        is_private=is_private,
        indexing_status="pending",
    )
    db.add(repository)
    await db.commit()
    await db.refresh(repository)

    return {
        "id": str(repository.id),
        "name": repository.name,
        "url": repository.url,
        "branch": repository.branch,
        "provider": repository.provider,
        "is_private": repository.is_private,
        "indexing_status": repository.indexing_status,
        "created_at": repository.created_at.isoformat(),
    }


@router.post("/{repository_id}/ingest", status_code=status.HTTP_202_ACCEPTED)
async def trigger_ingestion(
    repository_id: UUID,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    ingestion_service: RepositoryIngestionService = Depends(get_ingestion_service),
):
    # Verify ownership through project
    result = await db.execute(
        select(Repository, Project)
        .join(Project, Repository.project_id == Project.id)
        .where(Repository.id == repository_id, Project.owner_id == current_user.id)
    )
    row = result.first()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found",
        )

    repository, _ = row

    # Update status
    repository.indexing_status = "in_progress"
    await db.commit()

    # Run ingestion in background
    background_tasks.add_task(
        ingestion_service.ingest_repository,
        repository_id=repository.id,
        repo_url=repository.url,
        branch=repository.branch,
        access_token=repository.access_token_encrypted,
    )

    return {"message": "Ingestion started", "repository_id": str(repository_id)}


@router.get("")
async def list_repositories(
    project_id: UUID | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    query = (
        select(Repository)
        .join(Project, Repository.project_id == Project.id)
        .where(Project.owner_id == current_user.id)
    )

    if project_id:
        query = query.where(Repository.project_id == project_id)

    result = await db.execute(query)
    repositories = result.scalars().all()

    return [
        {
            "id": str(r.id),
            "project_id": str(r.project_id),
            "name": r.name,
            "url": r.url,
            "branch": r.branch,
            "provider": r.provider,
            "is_private": r.is_private,
            "indexing_status": r.indexing_status,
            "last_indexed_at": r.last_indexed_at.isoformat() if r.last_indexed_at else None,
            "indexing_error": r.indexing_error,
            "created_at": r.created_at.isoformat(),
            "updated_at": r.updated_at.isoformat(),
        }
        for r in repositories
    ]


@router.get("/{repository_id}")
async def get_repository(
    repository_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    result = await db.execute(
        select(Repository, Project)
        .join(Project, Repository.project_id == Project.id)
        .where(Repository.id == repository_id, Project.owner_id == current_user.id)
    )
    row = result.first()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found",
        )

    repository, _ = row

    return {
        "id": str(repository.id),
        "project_id": str(repository.project_id),
        "name": repository.name,
        "url": repository.url,
        "branch": repository.branch,
        "provider": repository.provider,
        "is_private": repository.is_private,
        "indexing_status": repository.indexing_status,
        "last_indexed_at": repository.last_indexed_at.isoformat() if repository.last_indexed_at else None,
        "indexing_error": repository.indexing_error,
        "created_at": repository.created_at.isoformat(),
        "updated_at": repository.updated_at.isoformat(),
    }


@router.get("/{repository_id}/files")
async def list_repository_files(
    repository_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    # Verify ownership
    result = await db.execute(
        select(Repository, Project)
        .join(Project, Repository.project_id == Project.id)
        .where(Repository.id == repository_id, Project.owner_id == current_user.id)
    )
    if not result.first():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found",
        )

    # Get files
    from app.models.project import RepositoryFile
    result = await db.execute(
        select(RepositoryFile).where(RepositoryFile.repository_id == repository_id)
    )
    files = result.scalars().all()

    return [
        {
            "id": str(f.id),
            "path": f.path,
            "language": f.language,
            "size_bytes": f.size_bytes,
            "content_hash": f.content_hash,
            "metadata": f.metadata,
            "created_at": f.created_at.isoformat(),
            "updated_at": f.updated_at.isoformat(),
        }
        for f in files
    ]