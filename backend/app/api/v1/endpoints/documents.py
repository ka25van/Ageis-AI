from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.api.v1.endpoints.auth import get_current_user
from app.core.di import get_db_session
from app.models.user import User
from app.models.project import Project
from app.models.document import Document, DocumentChunk
from app.services.document_processor import DocumentProcessor, get_document_processor

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_document(
    project_id: UUID = Form(...),
    title: str = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    processor: DocumentProcessor = Depends(get_document_processor),
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

    # Validate file type
    ext = file.filename.split(".")[-1].lower()
    if ext not in ["pdf", "md", "markdown", "txt", "rst"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file type. Supported: pdf, md, markdown, txt, rst",
        )

    # Read file content
    content = await file.read()

    # Process document
    result = await processor.process_uploaded_file(
        project_id=project_id,
        title=title,
        file_content=content,
        filename=file.filename,
        metadata={"original_filename": file.filename, "content_type": file.content_type},
    )

    return result


@router.post("/text", status_code=status.HTTP_201_CREATED)
async def create_text_document(
    project_id: UUID,
    title: str,
    content: str,
    source_type: str = "text",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    processor: DocumentProcessor = Depends(get_document_processor),
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

    # Create temp file
    import tempfile
    ext = ".txt" if source_type == "text" else ".md"
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=ext) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        result = await processor.process_document(
            project_id=project_id,
            title=title,
            source_type=source_type,
            file_path=tmp_path,
            metadata={"inline": True},
        )
        return result
    finally:
        os.unlink(tmp_path)


@router.get("")
async def list_documents(
    project_id: UUID | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    query = (
        select(Document)
        .join(Project, Document.project_id == Project.id)
        .where(Project.owner_id == current_user.id)
    )

    if project_id:
        query = query.where(Document.project_id == project_id)

    result = await db.execute(query)
    documents = result.scalars().all()

    return [
        {
            "id": str(d.id),
            "project_id": str(d.project_id),
            "title": d.title,
            "source_type": d.source_type,
            "source_url": d.source_url,
            "source_path": d.source_path,
            "metadata": d.doc_metadata,
            "created_at": d.created_at.isoformat(),
            "updated_at": d.updated_at.isoformat(),
        }
        for d in documents
    ]


@router.get("/{document_id}")
async def get_document(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
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

    document, _ = row

    return {
        "id": str(document.id),
        "project_id": str(document.project_id),
        "title": document.title,
        "source_type": document.source_type,
        "source_url": document.source_url,
        "source_path": document.source_path,
        "content": document.content,
        "metadata": document.metadata,
        "created_at": document.created_at.isoformat(),
        "updated_at": document.updated_at.isoformat(),
    }


@router.get("/{document_id}/chunks")
async def get_document_chunks(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    # Verify ownership
    result = await db.execute(
        select(Document, Project)
        .join(Project, Document.project_id == Project.id)
        .where(Document.id == document_id, Project.owner_id == current_user.id)
    )
    if not result.first():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    # Get chunks
    result = await db.execute(
        select(DocumentChunk).where(DocumentChunk.document_id == document_id).order_by(DocumentChunk.chunk_index)
    )
    chunks = result.scalars().all()

    return [
        {
            "id": str(c.id),
            "document_id": str(c.document_id),
            "chunk_index": c.chunk_index,
            "content": c.content,
            "token_count": c.token_count,
            "metadata": c.chunk_metadata,
            "created_at": c.created_at.isoformat(),
        }
        for c in chunks
    ]


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
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

    document, _ = row
    await db.delete(document)
    await db.commit()

import os  # for unlink in text endpoint