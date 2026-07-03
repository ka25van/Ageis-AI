from typing import Dict, List
from uuid import UUID

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.llm_service import LLMService, get_llm_service
from app.services.repository_data_service import RepositoryDataService, get_repository_data_service
from app.services.agent_base import AgentResult
from app.services.context_builder import ProjectContext
from app.core.di import get_db_session


class DocumentationAgent:
    def __init__(self, repo_data: RepositoryDataService, llm: LLMService):
        self.repo_data = repo_data
        self.llm = llm

    async def process(self, context: ProjectContext) -> AgentResult:
        result = await self.generate_readme(context.project_id)
        result_text = result.get("readme", json.dumps(result))
        return AgentResult(
            result=result_text,
            confidence=0.8,
            recommendations=["Generate API documentation", "Generate architecture documentation"],
            follow_up_actions=["Review README", "Add setup instructions"],
            details=result,
        )

    @staticmethod
    def _build_file_context(files: list, max_files: int = 30) -> str:
        lines = []
        for f in files[:max_files]:
            lang = getattr(f, "language", None) or "unknown"
            content = (getattr(f, "content", None) or "")[:500]
            lines.append(f"## {f.path} [{lang}]\n```\n{content}\n```")
        return "\n\n".join(lines)

    async def generate_readme(self, repository_id: UUID) -> Dict:
        files = await self.repo_data.get_files(repository_id)
        repo = await self.repo_data.get_repository(repository_id)
        repo_name = repo.name if repo else "repository"

        languages = await self.repo_data.get_languages(repository_id)
        paths = await self.repo_data.get_file_paths(repository_id)
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
        files = await self.repo_data.get_files(repository_id)
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
        files = await self.repo_data.get_files(repository_id)
        file_context = self._build_file_context(files)
        paths = await self.repo_data.get_file_paths(repository_id)
        languages = await self.repo_data.get_languages(repository_id)

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
    repo_data: RepositoryDataService = Depends(get_repository_data_service),
    llm: LLMService = Depends(get_llm_service),
) -> DocumentationAgent:
    return DocumentationAgent(repo_data, llm)
