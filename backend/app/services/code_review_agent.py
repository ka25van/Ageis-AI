from typing import Dict
from uuid import UUID
import json

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import RepositoryFile
from app.services.llm_service import LLMService, get_llm_service
from app.core.di import get_db_session


class CodeReviewAgent:
    def __init__(self, db: AsyncSession, llm: LLMService):
        self.db = db
        self.llm = llm

    async def review_pr(self, repository_id: UUID) -> Dict:
        result = await self.db.execute(
            select(RepositoryFile).where(RepositoryFile.repository_id == repository_id).limit(200)
        )
        files = result.scalars().all()

        if not files:
            return {"error": "No files found"}

        file_context = []
        for f in files[:30]:
            file_context.append({
                "path": f.path,
                "language": f.language,
                "content_preview": (f.content or "")[:500],
            })

        context = json.dumps(file_context, indent=2)
        system_prompt = "You are a code reviewer. Review this code and list any issues or concerns you find."
        user_prompt = f"Review this codebase:\n{context}"
        review = await self.llm.generate(system_prompt, user_prompt)

        parsed = {"review": review}

        return {
            "file_count": len(files),
            **parsed,
        }

    async def security_review(self, repository_id: UUID) -> Dict:
        result = await self.db.execute(
            select(RepositoryFile).where(RepositoryFile.repository_id == repository_id)
        )
        files = result.scalars().all()

        security_patterns = ["password", "secret", "token", "api_key", "hardcoded", "exec(", "eval("]
        suspicious_files = []
        for f in files:
            if f.content:
                for pat in security_patterns:
                    if pat in f.content:
                        suspicious_files.append({
                            "file": f.path,
                            "pattern": pat,
                            "context": f.content[:300],
                        })
                        break

        if not suspicious_files:
            return {
                "security_issues": [],
                "total": 0,
                "message": "No obvious security patterns detected",
            }

        context = json.dumps(suspicious_files[:30], indent=2)
        system_prompt = """You are a security expert. Analyze these potentially suspicious code patterns.
For each, determine if it's a real vulnerability or a false positive.
Format as JSON with keys: vulnerabilities (list of {severity, file, issue, remediation}), 
false_positives (list), security_score (0-10), critical_findings"""

        user_prompt = f"Suspicious patterns found:\n{context}"
        analysis = await self.llm.generate(system_prompt, user_prompt)

        try:
            parsed = json.loads(analysis)
        except json.JSONDecodeError:
            parsed = {"analysis": analysis}

        return {
            "security_issues": suspicious_files[:10],
            "total": len(suspicious_files),
            **parsed,
        }

    async def best_practices(self, repository_id: UUID) -> Dict:
        result = await self.db.execute(
            select(RepositoryFile).where(RepositoryFile.repository_id == repository_id)
        )
        files = result.scalars().all()

        has_readme = any("readme" in f.path.lower() for f in files)
        has_tests = any("test" in f.path.lower() for f in files)
        has_ci = any(f.path.endswith((".yml", ".yaml")) for f in files)
        has_config = any(kw in f.path.lower() for f in files for kw in ["config", "env", ".env"])
        has_docker = any(f.path.lower().startswith("docker") for f in files)
        has_lint = any(f.path.endswith((".eslintrc", ".prettierrc", "ruff.toml", ".flake8", ".pylintrc")) for f in files)

        practices_summary = {
            "has_readme": has_readme,
            "has_tests": has_tests,
            "has_ci_cd": has_ci,
            "has_config": has_config,
            "has_docker": has_docker,
            "has_linter_config": has_lint,
        }

        file_context = []
        for f in files[:20]:
            file_context.append(f"  {f.path} ({f.language or 'unknown'})")

        context = "\n".join(file_context)
        system_prompt = """You are a code quality expert. Review the project structure and best practices.
What's missing and what could be improved? 
Format as JSON with keys: overall_score (0-10), strengths (list), gaps (list), recommendations (list)"""

        user_prompt = f"""Project structure:\n{context}\n\nDetected practices:\n{json.dumps(practices_summary, indent=2)}"""
        assessment = await self.llm.generate(system_prompt, user_prompt)

        try:
            parsed = json.loads(assessment)
        except json.JSONDecodeError:
            parsed = {"assessment": assessment}

        return {
            "practices": practices_summary,
            "score": sum(1 for v in practices_summary.values() if v),
            "max": len(practices_summary),
            **parsed,
        }


async def get_code_review_agent(
    db: AsyncSession = Depends(get_db_session),
    llm: LLMService = Depends(get_llm_service),
) -> CodeReviewAgent:
    return CodeReviewAgent(db, llm)
