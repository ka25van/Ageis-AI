import os
import tempfile
from pathlib import Path
from typing import List, Dict, Optional, BinaryIO
from datetime import datetime
from uuid import UUID

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import pdfplumber
import markdown
from markdown.extensions import codehilite, fenced_code, tables, toc

from app.models.document import Document, DocumentChunk
from app.core.di import get_db_session


class DocumentProcessor:
    """Service for processing documents (PDF, Markdown, Text) into chunks."""

    def __init__(self, db: AsyncSession):
        self.db = db

    def load_pdf(self, file_path: str) -> List[Dict]:
        """Load and extract text from PDF file."""
        chunks = []
        with pdfplumber.open(file_path) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                text = page.extract_text()
                if text and text.strip():
                    chunks.append({
                        "content": text.strip(),
                        "metadata": {
                            "page": page_num,
                            "source_type": "pdf",
                        },
                    })
        return chunks

    def load_markdown(self, file_path: str) -> List[Dict]:
        """Load and parse Markdown file."""
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        # Convert markdown to HTML for structure analysis
        md = markdown.Markdown(extensions=[codehilite.CodeHiliteExtension(), fenced_code.FencedCodeExtension(), tables.TableExtension(), toc.TocExtension()])
        html = md.convert(content)

        # Simple chunking by headers
        chunks = []
        current_chunk = []
        current_header = None

        for line in content.split("\n"):
            if line.startswith("#"):
                if current_chunk:
                    chunks.append({
                        "content": "\n".join(current_chunk).strip(),
                        "metadata": {
                            "header": current_header,
                            "source_type": "markdown",
                        },
                    })
                current_header = line.strip("# ").strip()
                current_chunk = [line]
            else:
                current_chunk.append(line)

        if current_chunk:
            chunks.append({
                "content": "\n".join(current_chunk).strip(),
                "metadata": {
                    "header": current_header,
                    "source_type": "markdown",
                },
            })

        return [c for c in chunks if c["content"]]

    def load_text(self, file_path: str) -> List[Dict]:
        """Load plain text file."""
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        # Split by paragraphs (double newline)
        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]

        chunks = []
        for i, para in enumerate(paragraphs):
            if len(para) > 50:  # Skip very short paragraphs
                chunks.append({
                    "content": para,
                    "metadata": {
                        "paragraph_index": i,
                        "source_type": "text",
                    },
                })

        return chunks

    def load_document(self, file_path: str, source_type: str) -> List[Dict]:
        """Load document based on source type."""
        if source_type == "pdf":
            return self.load_pdf(file_path)
        elif source_type == "markdown":
            return self.load_markdown(file_path)
        elif source_type == "text":
            return self.load_text(file_path)
        else:
            raise ValueError(f"Unsupported source type: {source_type}")

    def chunk_text(self, text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
        """Split text into overlapping chunks."""
        if len(text) <= chunk_size:
            return [text]

        chunks = []
        start = 0
        while start < len(text):
            end = min(start + chunk_size, len(text))
            chunk = text[start:end]

            # Try to break at sentence boundary
            if end < len(text):
                last_period = chunk.rfind(". ")
                last_newline = chunk.rfind("\n")
                break_point = max(last_period, last_newline)
                if break_point > chunk_size // 2:
                    chunk = chunk[:break_point + 1]
                    end = start + break_point + 1

            chunks.append(chunk.strip())
            start = end - overlap

        return [c for c in chunks if c]

    async def create_document(
        self,
        project_id: UUID,
        title: str,
        source_type: str,
        source_path: str = None,
        source_url: str = None,
        metadata: Dict = None,
    ) -> Document:
        """Create document record."""
        doc = Document(
            project_id=project_id,
            title=title,
            source_type=source_type,
            source_path=source_path,
            source_url=source_url,
            metadata=metadata or {},
        )
        self.db.add(doc)
        await self.db.commit()
        await self.db.refresh(doc)
        return doc

    async def save_chunks(
        self,
        document_id: UUID,
        chunks: List[Dict],
    ) -> int:
        """Save document chunks to database."""
        saved = 0
        for i, chunk_data in enumerate(chunks):
            chunk = DocumentChunk(
                document_id=document_id,
                chunk_index=i,
                content=chunk_data["content"],
                token_count=len(chunk_data["content"]) // 4,  # rough estimate
                metadata=chunk_data.get("metadata", {}),
            )
            self.db.add(chunk)
            saved += 1

        await self.db.commit()
        return saved

    async def process_document(
        self,
        project_id: UUID,
        title: str,
        source_type: str,
        file_path: str = None,
        source_url: str = None,
        metadata: Dict = None,
    ) -> Dict:
        """Full document processing pipeline."""
        # Create document record
        doc = await self.create_document(
            project_id=project_id,
            title=title,
            source_type=source_type,
            source_path=file_path,
            source_url=source_url,
            metadata=metadata or {},
        )

        # Load content based on source type
        if source_type in ["pdf", "markdown", "text"] and file_path:
            raw_chunks = self.load_document(file_path, source_type)
        else:
            raise ValueError(f"Unsupported source type or missing file: {source_type}")

        # Further chunk if needed
        all_chunks = []
        for raw_chunk in raw_chunks:
            sub_chunks = self.chunk_text(raw_chunk["content"])
            for sub in sub_chunks:
                all_chunks.append({
                    "content": sub,
                    "metadata": raw_chunk.get("metadata", {}),
                })

        # Save chunks
        saved = await self.save_chunks(doc.id, all_chunks)

        return {
            "document_id": str(doc.id),
            "title": doc.title,
            "source_type": source_type,
            "chunks_created": saved,
            "status": "completed",
        }

    async def process_uploaded_file(
        self,
        project_id: UUID,
        title: str,
        file_content: bytes,
        filename: str,
        metadata: Dict = None,
    ) -> Dict:
        """Process an uploaded file from memory."""
        # Determine source type from extension
        ext = Path(filename).suffix.lower()
        if ext == ".pdf":
            source_type = "pdf"
        elif ext in [".md", ".markdown"]:
            source_type = "markdown"
        elif ext in [".txt", ".rst"]:
            source_type = "text"
        else:
            raise ValueError(f"Unsupported file extension: {ext}")

        # Save to temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            tmp.write(file_content)
            tmp_path = tmp.name

        try:
            result = await self.process_document(
                project_id=project_id,
                title=title,
                source_type=source_type,
                file_path=tmp_path,
                metadata={**(metadata or {}), "original_filename": filename},
            )
            return result
        finally:
            os.unlink(tmp_path)


async def get_document_processor(db: AsyncSession = Depends(get_db_session)) -> DocumentProcessor:
    return DocumentProcessor(db)