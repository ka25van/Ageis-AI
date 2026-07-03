from typing import Dict, List, Optional
from uuid import UUID

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import RepositoryFile, Repository
from app.core.di import get_db_session
from app.core.config import settings


class RepositoryDataService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_files(self, repository_id: UUID, limit: int = settings.REPOSITORY_FILE_LIMIT) -> List[RepositoryFile]:
        result = await self.db.execute(
            select(RepositoryFile)
            .where(RepositoryFile.repository_id == repository_id)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_repository(self, repository_id: UUID) -> Optional[Repository]:
        result = await self.db.execute(
            select(Repository).where(Repository.id == repository_id)
        )
        return result.scalar_one_or_none()

    async def get_languages(self, repository_id: UUID) -> List[str]:
        files = await self.get_files(repository_id, limit=settings.BATCH_FILE_LIMIT)
        return list(set(f.language for f in files if f.language))

    async def get_file_paths(self, repository_id: UUID) -> List[str]:
        files = await self.get_files(repository_id, limit=settings.BATCH_FILE_LIMIT)
        return [f.path for f in files]

    async def count_files_by_language(self, repository_id: UUID) -> Dict[str, int]:
        files = await self.get_files(repository_id, limit=settings.BATCH_FILE_LIMIT)
        counts: Dict[str, int] = {}
        for f in files:
            lang = f.language or "unknown"
            counts[lang] = counts.get(lang, 0) + 1
        return counts

    async def get_file_summary(self, repository_id: UUID, limit: int = settings.REPOSITORY_FILE_LIMIT, preview_chars: int = settings.FILE_PREVIEW_CHARS) -> str:
        files = await self.get_files(repository_id, limit=limit)
        lines = []
        for f in files[:settings.FILE_PREVIEW_LIMIT]:
            lang = f.language or "unknown"
            size = f.size_bytes or 0
            preview = (f.content or "")[:preview_chars]
            lines.append(f"### {f.path} [{lang}] ({size} bytes)\n```\n{preview}\n```")
        return "\n\n".join(lines)


async def get_repository_data_service(
    db: AsyncSession = Depends(get_db_session),
) -> RepositoryDataService:
    return RepositoryDataService(db)
