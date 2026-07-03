from typing import Dict, List, Optional
from uuid import UUID
from datetime import datetime

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.repository_analysis import RepositoryAnalyzer
from app.services.repository_data_service import RepositoryDataService, get_repository_data_service
from app.services.memory import MemorySystem, get_memory_system
from app.core.di import get_db_session
from app.core.config import settings


CACHE_TTL_SECONDS = 300


class RepositoryIntelligence:
    """Cached structured analysis of a repository.

    Avoids re-running RepositoryAnalyzer on every agent call.
    Uses a module-level singleton so the cache persists across requests.
    """

    _instance: Optional["RepositoryIntelligence"] = None

    def __init__(self, repo_data: RepositoryDataService, analyzer: RepositoryAnalyzer, memory: Optional[MemorySystem] = None):
        self.repo_data = repo_data
        self.analyzer = analyzer
        self.memory = memory
        self._cache: Dict[str, tuple[float, Dict]] = {}

    @classmethod
    def invalidate(cls, repository_id: UUID) -> None:
        if cls._instance is not None:
            cls._instance._cache.pop(str(repository_id), None)
            # Also clear persisted memory so next call refreshes
            if cls._instance.memory:
                import asyncio
                try:
                    asyncio.ensure_future(cls._instance.memory.delete_repository_memory(repository_id))
                except Exception:
                    pass

    async def _get_analysis(self, repository_id: UUID) -> Dict:
        key = str(repository_id)
        now = datetime.utcnow().timestamp()
        entry = self._cache.get(key)
        if entry and (now - entry[0]) < CACHE_TTL_SECONDS:
            return entry[1]

        # Try persisted memory on cache miss
        if self.memory:
            persisted = await self.memory.get_repository_memory(repository_id)
            if persisted:
                self._cache[key] = (now, persisted)
                return persisted

        files = await self.repo_data.get_files(repository_id, limit=settings.BATCH_FILE_LIMIT)
        if not files:
            result: Dict = {"error": "No files found"}
            self._cache[key] = (now, result)
            return result

        file_infos = [
            {"path": f.path, "language": f.language, "content": f.content,
             "content_hash": f.content_hash, "size_bytes": f.size_bytes}
            for f in files
        ]

        all_deps = []
        all_routes = []
        for fi in file_infos:
            if fi["content"]:
                all_deps.extend(self.analyzer.extract_dependencies(fi["content"], fi["language"] or ""))
                all_routes.extend(self.analyzer.extract_api_routes(fi["content"], fi["language"] or ""))

        architecture = self.analyzer.analyze_project_structure(file_infos)
        framework = self.analyzer.detect_framework(file_infos)
        services = self.analyzer.discover_services(file_infos)

        result = {
            "framework": framework,
            "dependencies": list(set(all_deps)),
            "dependency_categories": {
                cat: [d for d in all_deps if self.analyzer.categorize_dependency(d) == cat]
                for cat in ["internal", "third_party", "framework", "unknown"]
            },
            "api_routes": all_routes,
            "architecture": architecture,
            "services": services,
            "file_count": len(files),
        }
        self._cache[key] = (now, result)
        # Store in repository memory for persistence across restarts
        if self.memory:
            try:
                await self.memory.store_repository_memory(repository_id, result)
            except Exception:
                pass
        return result

    async def get_summary(self, repository_id: UUID) -> Dict:
        analysis = await self._get_analysis(repository_id)
        if "error" in analysis:
            return analysis
        return {
            "framework": analysis["framework"],
            "file_count": analysis["file_count"],
            "service_count": len(analysis["services"]),
            "dependency_count": len(analysis["dependencies"]),
            "api_route_count": len(analysis["api_routes"]),
            "architecture": analysis["architecture"],
        }

    async def get_dependency_graph(self, repository_id: UUID) -> Dict:
        analysis = await self._get_analysis(repository_id)
        if "error" in analysis:
            return analysis
        return {
            "dependencies": analysis["dependencies"],
            "dependency_categories": analysis["dependency_categories"],
        }

    async def get_architecture(self, repository_id: UUID) -> Dict:
        analysis = await self._get_analysis(repository_id)
        if "error" in analysis:
            return analysis
        return analysis["architecture"]

    async def get_api_routes(self, repository_id: UUID) -> List[Dict]:
        analysis = await self._get_analysis(repository_id)
        if "error" in analysis:
            return []
        return analysis["api_routes"]

    async def get_entry_points(self, repository_id: UUID) -> List[str]:
        files = await self.repo_data.get_file_paths(repository_id)
        entry_keywords = ["main.py", "app.py", "index.ts", "index.js", "server.ts", "server.js", "manage.py", "cli.py"]
        return [p for p in files if any(p.endswith(kw) or p == kw for kw in entry_keywords)]


async def get_repository_intelligence(
    repo_data: RepositoryDataService = Depends(get_repository_data_service),
    db: AsyncSession = Depends(get_db_session),
    memory: Optional[MemorySystem] = Depends(get_memory_system),
) -> RepositoryIntelligence:
    if RepositoryIntelligence._instance is None:
        analyzer = RepositoryAnalyzer(db)
        RepositoryIntelligence._instance = RepositoryIntelligence(repo_data, analyzer, memory=memory)
    return RepositoryIntelligence._instance
