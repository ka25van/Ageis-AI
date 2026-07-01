from typing import Dict, List, Optional, Any
from uuid import UUID

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import RepositoryFile, Repository
from app.core.di import get_db_session


class CodeReviewAgent:
    """Agent for reviewing code: PR review, security review, best practices."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # Security patterns
    SECURITY_PATTERNS = [
        "password",
        "secret",
        "token",
        "api_key",
        "HARDCODED",
        "hardcoded",
    ]

    async def review_pr(self, repository_id: UUID, branch: str = "main") -> Dict:
        """Review a pull request for issues."""
        result = await self.db.execute(
            select(RepositoryFile).where(RepositoryFile.repository_id == repository_id)
        )
        files = result.scalars().all()

        issues = []
        for f in files:
            if f.content:
                # Check for common issues
                for pattern in self.SECURITY_PATTERNS:
                    if pattern in f.content and "import" not in f.content:
                        issues.append({
                            "file": f.path,
                            "issue": pattern,
                            "severity": "high" if pattern == "password" else "medium",
                        })

        return {
            "issues": issues,
            "total_issues": len(issues),
            "file_count": len(files),
            "status": "ready" if not issues else "needs review",
        }

    async def security_review(self, repository_id: UUID) -> Dict:
        """Review for security issues."""
        result = await self.db.execute(
            select(RepositoryFile).where(RepositoryFile.repository_id == repository_id)
        )
        files = result.scalars().all()

        security_issues = []
        for f in files:
            if f.content:
                # Check for security patterns
                if "password" in f.content or "secret" in f.content:
                    security_issues.append({
                        "file": f.path,
                        "pattern": "hardcoded credential",
                        "severity": "high",
                    })
                if "exec" in f.content or "eval" in f.content:
                    security_issues.append({
                        "file": f.path,
                        "pattern": "dangerous function",
                        "severity": "medium",
                    })

        return {
            "security_issues": security_issues,
            "total": len(security_issues),
            "file_count": len(files),
        }

    async def best_practices(self, repository_id: UUID) -> Dict:
        """Check for best practices compliance."""
        result = await self.db.execute(
            select(RepositoryFile).where(RepositoryFile.repository_id == repository_id)
        )
        files = result.scalars().all()

        practices = {
            "has_readme": False,
            "has_docstrings": False,
            "has_tests": False,
            "has_type_hints": False,
            "has_config": False,
            "has_ci": False,
        }

        for f in files:
            path = f.path
            if "readme" in path.lower():
                practices["has_readme"] = True
            if "test" in path.lower():
                practices["has_tests"] = True
            if "doc" in path.lower() or "docstring" in path.lower():
                practices["has_docstrings"] = True
            if "config" in path.lower() or "env" in path.lower():
                practices["has_config"] = True

        return {
            "practices": practices,
            "score": sum(1 for v in practices.values() if v),
            "max": len(practices),
        }


async def get_code_review_agent(
    db: AsyncSession = Depends(get_db_session),
) -> CodeReviewAgent:
    return CodeReviewAgent(db)