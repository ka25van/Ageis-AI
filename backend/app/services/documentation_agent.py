from typing import Dict, List
from uuid import UUID

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import RepositoryFile, Repository
from app.services.llm_service import LLMService, get_llm_service
from app.core.di import get_db_session


class DocumentationAgent:
    def __init__(self, db: AsyncSession, llm: LLMService):
        self.db = db
        self.llm = llm

    def _build_file_context(self, files: list, max_files: int = 30) -> str:
        lines = []
        for f in files[:max_files]:
            lang = f.language or "unknown"
            content = (f.content or "")[:500]
            lines.append(f"## {f.path} [{lang}]\n```\n{content}\n```")
        return "\n\n".join(lines)

    async def generate_readme(self, repository_id: UUID) -> Dict:
        result = await self.db.execute(
            select(RepositoryFile).where(RepositoryFile.repository_id == repository_id).limit(200)
        )
        files = result.scalars().all()

        repo_result = await self.db.execute(
            select(Repository).where(Repository.id == repository_id)
        )
        repo = repo_result.scalar_one_or_none()
        repo_name = repo.name if repo else "repository"

        languages = list(set(f.language for f in files if f.language))
        paths = [f.path for f in files]
        file_context = self._build_file_context(files)

        system_prompt = """You are a technical documentation expert. Generate a comprehensive README.md for this repository.
Include: title, description, features, tech stack, project structure, setup instructions, API overview (if applicable), and usage examples.
Use proper markdown formatting."""

        user_prompt = f"""Repository: {repo_name}
Languages: {', '.join(languages)}
Total Files: {len(files)}
Structure:
{chr(10).join(paths[:60])}

Key file contents:
{file_context[:6000]}"""

        readme = await self.llm.generate(system_prompt, user_prompt)

        return {
            "readme": readme,
            "files_analyzed": len(files),
            "languages": languages,
        }

    async def generate_api_documentation(self, repository_id: UUID) -> Dict:
        result = await self.db.execute(
            select(RepositoryFile).where(RepositoryFile.repository_id == repository_id).limit(200)
        )
        files = result.scalars().all()

        api_files = [f for f in files if f.content and any(
            kw in f.content.lower() for kw in ["router", "route", "endpoint", "api", "flask", "django", "fastapi", "controller"]
        )]
        file_context = self._build_file_context(api_files[:20])

        system_prompt = """You are an API documentation expert. Generate comprehensive API documentation for this codebase.
Document all endpoints, request/response formats, authentication, and usage examples.
Use proper markdown formatting."""

        user_prompt = f"""API-related files found:
{file_context[:6000]}"""

        api_docs = await self.llm.generate(system_prompt, user_prompt)

        return {
            "api_documentation": api_docs,
            "api_files_found": len(api_files),
            "total_files": len(files),
        }

    async def generate_architecture_documentation(self, repository_id: UUID) -> Dict:
        result = await self.db.execute(
            select(RepositoryFile).where(RepositoryFile.repository_id == repository_id).limit(200)
        )
        files = result.scalars().all()

        file_context = self._build_file_context(files)
        paths = [f.path for f in files]
        languages = list(set(f.language for f in files if f.language))

        system_prompt = """You are a software architect. Generate detailed architecture documentation.
Analyze the directory structure, file organization, dependency flow, and component relationships.
Include: high-level architecture, component diagram (text-based), data flow, layer descriptions, and technology decisions.
Use proper markdown."""

        user_prompt = f"""Total files: {len(files)}
Languages: {', '.join(languages)}
Directory structure:
{chr(10).join(paths[:80])}

Key file contents:
{file_context[:5000]}"""

        arch_docs = await self.llm.generate(system_prompt, user_prompt)

        return {
            "architecture_documentation": arch_docs,
            "total_files": len(files),
            "languages": languages,
        }


async def get_documentation_agent(
    db: AsyncSession = Depends(get_db_session),
    llm: LLMService = Depends(get_llm_service),
) -> DocumentationAgent:
    return DocumentationAgent(db, llm)
