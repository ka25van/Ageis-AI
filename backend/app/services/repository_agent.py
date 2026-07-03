from typing import Dict, List, Optional
from uuid import UUID
import json

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.llm_service import LLMService, get_llm_service
from app.services.repository_data_service import RepositoryDataService, get_repository_data_service
from app.services.agent_base import AgentResult
from app.services.context_builder import ProjectContext
from app.core.di import get_db_session
from app.core.config import settings


class RepositoryAgent:
    def __init__(self, repo_data: RepositoryDataService, llm: LLMService):
        self.repo_data = repo_data
        self.llm = llm

    async def process(self, context: ProjectContext, repository_id: UUID = None) -> AgentResult:
        """Entry point for ContextBuilder-driven execution."""
        rid = repository_id or context.project_id
        analysis = await self.understand_code(rid)
        result_text = analysis.get("analysis", json.dumps(analysis))
        return AgentResult(
            result=result_text,
            confidence=0.85,
            recommendations=[],
            follow_up_actions=["View architecture summary", "Search specific code"],
            details=analysis,
        )

    async def understand_code(self, repository_id: UUID) -> Dict:
        files = await self.repo_data.get_files(repository_id)
        if not files:
            return {"error": "No files found", "repository_id": str(repository_id)}

        file_summary = await self.repo_data.get_file_summary(repository_id)
        languages = await self.repo_data.get_languages(repository_id)
        paths = await self.repo_data.get_file_paths(repository_id)
        repo = await self.repo_data.get_repository(repository_id)
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
        files = await self.repo_data.get_files(repository_id, limit=settings.BATCH_FILE_LIMIT)
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
    repo_data: RepositoryDataService = Depends(get_repository_data_service),
    llm: LLMService = Depends(get_llm_service),
) -> RepositoryAgent:
    return RepositoryAgent(repo_data, llm)
