from typing import Dict, List, Optional
from uuid import UUID
import json

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Repository, RepositoryFile
from app.services.llm_service import LLMService, get_llm_service
from app.core.di import get_db_session


class RepositoryAgent:
    def __init__(self, db: AsyncSession, llm: LLMService):
        self.db = db
        self.llm = llm

    def _build_file_summary(self, files: list) -> str:
        lines = []
        for f in files[:50]:
            lang = f.language or "unknown"
            size = f.size_bytes or 0
            preview = (f.content or "")[:300]
            lines.append(f"### {f.path} [{lang}] ({size} bytes)\n```\n{preview}\n```")
        return "\n\n".join(lines)

    async def understand_code(self, repository_id: UUID) -> Dict:
        result = await self.db.execute(
            select(RepositoryFile).where(RepositoryFile.repository_id == repository_id)
        )
        files = result.scalars().all()

        if not files:
            return {"error": "No files found", "repository_id": str(repository_id)}

        file_summary = self._build_file_summary(files)
        languages = list(set(f.language for f in files if f.language))
        paths = [f.path for f in files]

        repo_result = await self.db.execute(
            select(Repository).where(Repository.id == repository_id)
        )
        repo = repo_result.scalar_one_or_none()
        repo_name = repo.name if repo else "unknown"

        system_prompt = "You are a software architect. Analyze this repository and describe its structure, tech stack, and key components."
        user_prompt = f"""Repository: {repo_name}
Languages: {', '.join(languages)}
Files ({len(files)} total)
File paths: {json.dumps(paths[:60])}

Key file previews:
{file_summary[:4000]}"""

        analysis = await self.llm.generate(system_prompt, user_prompt)
        parsed = {"analysis": analysis}

        return {
            "repository": repo_name,
            "file_count": len(files),
            "languages": languages,
            **parsed,
        }

    async def summarize_architecture(self, repository_id: UUID) -> Dict:
        analysis = await self.understand_code(repository_id)
        system_prompt = """Given this repository analysis, produce a concise 3-paragraph architecture summary:
1. What the project does and its tech stack
2. How it's structured (layers, components)
3. Key architectural decisions

Keep it under 300 words total."""

        user_prompt = json.dumps(analysis, indent=2)[:4000]
        summary = await self.llm.generate(system_prompt, user_prompt)

        return {
            "summary": summary,
            "framework": analysis.get("tech_stack", "Unknown"),
            "languages": analysis.get("languages", []),
            "file_count": analysis.get("file_count", 0),
        }

    async def search_code(self, repository_id: UUID, query: str) -> Dict:
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
                    "match_preview": f.content[:200],
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

        if matches:
            system_prompt = "Summarize what the search results tell us about this codebase regarding the query."
            user_prompt = f"Query: {query}\nMatches: {json.dumps(matches, indent=2)}"
            insight = await self.llm.generate(system_prompt, user_prompt[:4000])
        else:
            insight = "No matches found in the repository."

        return {
            "query": query,
            "matches": matches,
            "count": len(matches),
            "insight": insight,
        }


async def get_repository_agent(
    db: AsyncSession = Depends(get_db_session),
    llm: LLMService = Depends(get_llm_service),
) -> RepositoryAgent:
    return RepositoryAgent(db, llm)
