from typing import Dict, List
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


class CodeReviewAgent:
    def __init__(self, repo_data: RepositoryDataService, llm: LLMService):
        self.repo_data = repo_data
        self.llm = llm

    async def process(self, context: ProjectContext) -> AgentResult:
        result = await self.best_practices(context.project_id)
        result_text = result.get("analysis", json.dumps(result))
        return AgentResult(
            result=result_text,
            confidence=0.8,
            recommendations=result.get("recommendations", []),
            follow_up_actions=["Run security audit", "Review specific file"],
            details=result,
        )

    async def review_pr(self, repository_id: UUID, pr_url: str) -> Dict:
        files = await self.repo_data.get_files(repository_id)
        if not files:
            return {"error": "No files found"}

        file_previews = []
        for f in files[:40]:
            lang = f.language or "unknown"
            content = (f.content or "")[:400]
            file_previews.append(f"File: {f.path} [{lang}]\n```\n{content}\n```")

        context = "\n\n".join(file_previews)
        system_prompt = """You are a senior code reviewer. Review this code for:
1. Potential bugs and logic errors
2. Security vulnerabilities
3. Performance issues
4. Code quality and maintainability
5. Suggested improvements

Provide specific line-level feedback where possible."""

        user_prompt = f"PR URL: {pr_url}\n\nRepository contents:\n{context[:6000]}"
        review = await self.llm.generate(system_prompt, user_prompt)

        return {
            "pr_url": pr_url,
            "review": review,
            "files_reviewed": len(files[:40]),
            "total_files": len(files),
        }

    async def security_audit(self, repository_id: UUID) -> Dict:
        files = await self.repo_data.get_files(repository_id, limit=settings.BATCH_FILE_LIMIT)

        security_keywords = [
            "password", "secret", "token", "api_key", "apikey",
            "private_key", "ssh", "credentials", "auth_token",
            "database_url", "connection_string", "jwt_secret",
            "session_secret", "csrf", "xss", "injection",
            "exec(", "eval(", "pickle.load", "yaml.load",
            "sudo", "chmod 777", "chmod 755",
        ]

        findings = []
        for f in files:
            if f.content:
                for kw in security_keywords:
                    if kw in f.content.lower():
                        findings.append({
                            "file": f.path,
                            "keyword": kw,
                            "context": f.content[:200],
                            "language": f.language,
                        })

        if not findings:
            return {
                "findings": [],
                "total_findings": 0,
                "risk_level": "low",
                "recommendations": ["No security concerns detected"],
            }

        context = json.dumps(findings[:settings.CONTEXT_TRUNCATION_LIMIT], indent=2)
        system_prompt = """You are a security auditor. Analyze these findings and provide:
1. Severity assessment for each finding
2. Whether it's a false positive or real threat
3. Remediation steps
4. Overall risk assessment (low/medium/high/critical)"""

        user_prompt = f"Security findings:\n{context}"
        analysis = await self.llm.generate(system_prompt, user_prompt)

        return {
            "findings": findings[:10],
            "total_findings": len(findings),
            "risk_level": "high" if len(findings) > 10 else "medium" if findings else "low",
            "analysis": analysis,
            "recommendations": [analysis],
        }

    async def best_practices(self, repository_id: UUID) -> Dict:
        files = await self.repo_data.get_files(repository_id, limit=settings.BATCH_FILE_LIMIT)
        paths = await self.repo_data.get_file_paths(repository_id)
        languages = await self.repo_data.get_languages(repository_id)

        file_previews = []
        for f in files[:settings.CONTEXT_TRUNCATION_LIMIT]:
            content = (f.content or "")[:settings.FILE_PREVIEW_CHARS]
            file_previews.append(f"File: {f.path}\n```\n{content}\n```")

        context = "\n\n".join(file_previews)
        system_prompt = """You are a code quality expert. Analyze this codebase for best practices:
1. Coding standards and conventions
2. Design pattern usage
3. Test coverage
4. Documentation quality
5. Error handling
6. Performance patterns
7. Suggested improvements

Provide specific, actionable recommendations."""

        user_prompt = f"""Languages: {', '.join(languages)}
Structure: {json.dumps(paths[:40])}

Code samples:
{context[:5000]}"""

        analysis = await self.llm.generate(system_prompt, user_prompt)

        return {
            "analysis": analysis,
            "languages": languages,
            "files_analyzed": len(files[:30]),
            "recommendations": [analysis],
        }


async def get_code_review_agent(
    repo_data: RepositoryDataService = Depends(get_repository_data_service),
    llm: LLMService = Depends(get_llm_service),
) -> CodeReviewAgent:
    return CodeReviewAgent(repo_data, llm)
