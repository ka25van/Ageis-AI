from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.api.v1.endpoints.auth import get_current_user
from app.core.di import get_db_session
from app.models.user import User
from app.models.project import Project, Repository
from app.services.repository_analysis import RepositoryAnalyzer, get_repository_analyzer

router = APIRouter(prefix="/analyze", tags=["analysis"])


@router.post("/{repository_id}")
async def analyze_repository(
    repository_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    analyzer: RepositoryAnalyzer = Depends(get_repository_analyzer),
):
    # Verify ownership
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

    if repository.indexing_status != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Repository not yet indexed. Run ingestion first.",
        )

    analysis = await analyzer.analyze_repository(repository_id)

    return {
        "repository_id": str(repository_id),
        "repository_name": repository.name,
        "framework": analysis["framework"],
        "file_count": analysis["file_count"],
        "dependencies": analysis["dependencies"],
        "dependency_categories": analysis["dependency_categories"],
        "api_routes": analysis["api_routes"],
        "architecture": analysis["architecture"],
        "services": analysis["services"],
    }


@router.get("/{repository_id}/dependencies")
async def get_dependency_graph(
    repository_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    analyzer: RepositoryAnalyzer = Depends(get_repository_analyzer),
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

    import sqlalchemy as sa
    from app.models.project import RepositoryFile

    files_result = await db.execute(
        sa.select(RepositoryFile).where(RepositoryFile.repository_id == repository_id)
    )
    files = files_result.scalars().all()

    dependencies = []
    for file in files:
        if file.content:
            deps = analyzer.extract_dependencies(file.content, file.language or "")
            dependencies.append({
                "file": file.path,
                "dependencies": deps,
                "language": file.language,
            })

    return {
        "repository_id": str(repository_id),
        "dependencies": dependencies,
    }


@router.get("/{repository_id}/services")
async def get_services(
    repository_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    analyzer: RepositoryAnalyzer = Depends(get_repository_analyzer),
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

    import sqlalchemy as sa
    from app.models.project import RepositoryFile

    files_result = await db.execute(
        sa.select(RepositoryFile).where(RepositoryFile.repository_id == repository_id)
    )
    files = files_result.scalars().all()

    file_infos = [
        {"path": f.path, "language": f.language, "content": f.content}
        for f in files
    ]

    services = analyzer.discover_services(file_infos)
    framework = analyzer.detect_framework(file_infos)
    architecture = analyzer.analyze_project_structure(file_infos)

    return {
        "framework": framework,
        "architecture": architecture,
        "services": services,
    }