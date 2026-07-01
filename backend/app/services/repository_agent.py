from typing import Dict, List, Optional, Any
from uuid import UUID

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Repository, RepositoryFile
from app.services.repository_analysis import RepositoryAnalyzer, get_repository_analyzer
from app.core.di import get_db_session


class RepositoryAgent:
    """AI agent that understands, summarizes, and searches repository code."""

    def __init__(self, db: AsyncSession, analyzer: RepositoryAnalyzer):
        self.db = db
        self.analyzer = analyzer

    async def understand_code(self, repository_id: UUID, query: str = None) -> Dict:
        """Understand repository code by analyzing its structure."""
        result = await self.db.execute(
            select(RepositoryFile).where(RepositoryFile.repository_id == repository_id)
        )
        files = result.scalars().all()

        if not files:
            return {"error": "No files found", "repository_id": str(repository_id)}

        # Collect all files with content
        file_infos = [
            {"path": f.path, "language": f.language, "content": f.content}
            for f in files if f.content
        ]

        # Analyze structure
        architecture = self.analyzer.analyze_project_structure(file_infos)
        framework = self.analyzer.detect_framework(file_infos)

        # Extract key components
        languages = set(f["language"] for f in file_infos if f["language"])
        api_components = []
        for fi in file_infos:
            if fi["content"]:
                routes = self.analyzer.extract_api_routes(fi["content"], fi["language"] or "")
                api_components.extend(routes)

        return {
            "framework": framework,
            "languages": list(languages),
            "architecture": architecture,
            "api_routes": api_components,
            "file_count": len(files),
        }

    async def summarize_architecture(self, repository_id: UUID) -> Dict:
        """Generate a concise architecture summary."""
        analysis = await self.understand_code(repository_id)

        # Get repo info
        from app.models.project import Repository
        result = await self.db.execute(
            select(Repository).where(Repository.id == repository_id)
        )
        repo = result.scalar_one_or_none()

        return {
            "repository_id": str(repository_id),
            "repository_name": repo.name if repo else "unknown",
            "framework": analysis["framework"],
            "type": f"A {analysis['framework']} project with {len(analysis['languages'])} languages",
            "languages": analysis["languages"],
            "layers": analysis["architecture"]["layers"],
            "api_routes": analysis["api_routes"],
        }

    async def search_code(self, repository_id: UUID, query: str) -> Dict:
        """Search for specific code patterns in the repository."""
        from app.models.project import RepositoryFile

        result = await self.db.execute(
            select(RepositoryFile).where(RepositoryFile.repository_id == repository_id)
        )
        files = result.scalars().all()

        matches = []
        query_lower = query.lower()

        for f in files:
            if f.content and query_lower in f.content.lower():
                matches.append({
                    "file": f.path,
                    "language": f.language,
                    "match_preview": f.content[:200] if f.content else "",
                    "size_bytes": f.size_bytes,
                })
            elif query_lower in f.path.lower():
                matches.append({
                    "file": f.path,
                    "language": f.language,
                    "match_preview": f"Name match: {f.path}",
                    "size_bytes": f.size_bytes,
                })

            if len(matches) >= 20:
                break

        return {
            "query": query,
            "matches": matches,
            "count": len(matches),
        }


async def get_repository_agent(
    db: AsyncSession = Depends(get_db_session),
    analyzer: RepositoryAnalyzer = Depends(get_repository_analyzer),
) -> RepositoryAgent:
    return RepositoryAgent(db, analyzer)