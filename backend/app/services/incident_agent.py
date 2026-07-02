from typing import Dict, List
from uuid import UUID
from collections import Counter
import json

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import RepositoryFile
from app.services.llm_service import LLMService, get_llm_service
from app.core.di import get_db_session


class IncidentAgent:
    def __init__(self, db: AsyncSession, llm: LLMService):
        self.db = db
        self.llm = llm

    ERROR_KEYWORDS = [
        "error", "exception", "traceback", "fail", "crash",
        "timeout", "unreachable", "permission denied", "access denied",
        "unauthorized", "not found", "missing", "invalid",
    ]

    async def analyze_incidents(self, repository_id: UUID) -> Dict:
        result = await self.db.execute(
            select(RepositoryFile).where(RepositoryFile.repository_id == repository_id)
        )
        files = result.scalars().all()

        if not files:
            return {"error": "No files found"}

        incidents = []
        for f in files:
            if f.content:
                for kw in self.ERROR_KEYWORDS:
                    if kw in f.content.lower():
                        incidents.append({
                            "file": f.path,
                            "keyword": kw,
                            "language": f.language,
                            "severity": "high" if kw in ("traceback", "crash", "exception") else "medium",
                            "context": f.content[:200],
                        })

        if not incidents:
            return {
                "incidents": [],
                "total_incidents": 0,
                "analysis": "No error patterns detected in this repository.",
            }

        context = json.dumps(incidents[:30], indent=2)
        system_prompt = "You are a code analyst. Review these issues and give a brief analysis."
        user_prompt = f"Issues found in codebase:\n{context}\n\nWrite a short summary of the most important problems."
        analysis = await self.llm.generate(system_prompt, user_prompt)

        parsed = {"analysis": analysis, "summary": analysis[:300]}

        return {
            "incidents": incidents[:10],
            "total_incidents": len(incidents),
            **parsed,
        }

    async def root_cause_analysis(self, repository_id: UUID) -> Dict:
        incidents_result = await self.analyze_incidents(repository_id)
        if "error" in incidents_result:
            return incidents_result

        context = json.dumps(incidents_result.get("incidents", [])[:20], indent=2)
        system_prompt = """You are a senior SRE performing root cause analysis. 
For each issue found, determine the root cause, impact, and remediation steps.
Format as JSON with keys: root_causes (list), impact_analysis, remediation_plan, prevention_strategies."""

        user_prompt = f"Incidents:\n{context}"
        analysis = await self.llm.generate(system_prompt, user_prompt)

        try:
            parsed = json.loads(analysis)
        except json.JSONDecodeError:
            parsed = {"analysis": analysis}

        return {
            "total_incidents": incidents_result.get("total_incidents", 0),
            "summary": incidents_result.get("summary", ""),
            **parsed,
        }

    async def analyze_errors(self, repository_id: UUID) -> Dict:
        result = await self.db.execute(
            select(RepositoryFile).where(RepositoryFile.repository_id == repository_id)
        )
        files = result.scalars().all()

        if not files:
            return {"error": "No files found"}

        categories = Counter()
        error_contexts = []
        for f in files:
            if f.content:
                for kw in self.ERROR_KEYWORDS:
                    if kw in f.content.lower():
                        categories[kw] += 1
                        if len(error_contexts) < 20:
                            error_contexts.append({
                                "file": f.path,
                                "keyword": kw,
                                "context": f.content[:200],
                            })

        if not categories:
            return {
                "categories": {},
                "total_issues": 0,
                "recommendations": ["No error patterns detected"],
            }

        context = json.dumps(error_contexts, indent=2)
        system_prompt = """Generate actionable recommendations based on these error patterns.
Format as JSON with keys: recommendations (list of strings), priority_issues (list), quick_wins (list)."""

        user_prompt = f"Error analysis:\nCategories: {dict(categories)}\nContext:\n{context}"
        analysis = await self.llm.generate(system_prompt, user_prompt)

        try:
            parsed = json.loads(analysis)
        except json.JSONDecodeError:
            parsed = {"recommendations": [analysis]}

        return {
            "categories": dict(categories),
            "total_issues": sum(categories.values()),
            "error_details": error_contexts[:10],
            **parsed,
        }


async def get_incident_agent(
    db: AsyncSession = Depends(get_db_session),
    llm: LLMService = Depends(get_llm_service),
) -> IncidentAgent:
    return IncidentAgent(db, llm)
