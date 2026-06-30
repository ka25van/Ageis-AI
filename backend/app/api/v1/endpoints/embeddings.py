from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import Optional

from app.api.v1.endpoints.auth import get_current_user
from app.core.di import get_db_session
from app.models.user import User
from app.models.project import Project
from app.services.embeddings import EmbeddingService, get_embedding_service

router = APIRouter(prefix="/embeddings", tags=["embeddings"])


@router.post("/documents/{document_id}/generate")
async def generate_document_embeddings(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
):
    # Verify document ownership
    from app.models.document import Document
    from sqlalchemy import select

    result = await db.execute(
        select(Document, Project)
        .join(Project, Document.project_id == Project.id)
        .where(Document.id == document_id, Project.owner_id == current_user.id)
    )
    row = result.first()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    result = await embedding_service.embed_and_store_document_chunks(document_id)
    return result


@router.post("/repositories/{repository_id}/generate")
async def generate_repository_embeddings(
    repository_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
):
    # Verify repository ownership
    from app.models.project import Repository
    from sqlalchemy import select

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

    result = await embedding_service.embed_and_store_repository_files(repository_id)
    return result


@router.post("/search")
async def semantic_search(
    query: str,
    project_id: Optional[UUID] = None,
    limit: int = 10,
    threshold: float = 0.7,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
):
    # Verify project ownership if specified
    if project_id:
        from app.models.project import Project
        from sqlalchemy import select

        result = await db.execute(
            select(Project).where(Project.id == project_id, Project.owner_id == current_user.id)
        )
        if not result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found",
            )

    results = await embedding_service.semantic_search(
        query=query,
        project_id=project_id,
        limit=limit,
        similarity_threshold=threshold,
    )

    return {
        "query": query,
        "results": results,
        "count": len(results),
    }


@router.post("/hybrid-search")
async def hybrid_search(
    query: str,
    project_id: Optional[UUID] = None,
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
):
    # Verify project ownership if specified
    if project_id:
        from app.models.project import Project
        from sqlalchemy import select

        result = await db.execute(
            select(Project).where(Project.id == project_id, Project.owner_id == current_user.id)
        )
        if not result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found",
            )

    results = await embedding_service.hybrid_search(
        query=query,
        project_id=project_id,
        limit=limit,
    )

    return {
        "query": query,
        "results": results,
        "count": len(results),
    }