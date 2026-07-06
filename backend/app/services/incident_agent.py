from typing import Dict, List, Optional
from uuid import UUID
from collections import Counter
import json

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.llm_service import LLMService, get_llm_service
from app.services.repository_data_service import RepositoryDataService, get_repository_data_service
from app.services.agent_base import AgentResult
from app.services.context_builder import ProjectContext
from app.core.di import get_db_session
from app.core.config import settings


class IncidentAgent:
    def __init__(self, repo_data: RepositoryDataService, llm: LLMService):
        self.repo_data = repo_data
        self.llm = llm

    async def process(self, context: ProjectContext) -> AgentResult:
        rid = context.repository_id or context.project_id
        result = await self.analyze_incidents(rid)
        result_text = result.get("analysis", json.dumps(result))
        return AgentResult(
            result=result_text,
            confidence=0.8,
            recommendations=[result.get("analysis", "")],
            follow_up_actions=["Run root cause analysis", "View error recommendations"],
            details=result,
        )

    ERROR_KEYWORDS = [
        "error", "exception", "traceback", "fail", "crash",
        "timeout", "unreachable", "permission denied", "access denied",
        "unauthorized", "not found", "missing", "invalid",
    ]

    async def analyze_incidents(self, repository_id: UUID) -> Dict:
        files = await self.repo_data.get_files(repository_id)
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
        files = await self.repo_data.get_files(repository_id, limit=settings.BATCH_FILE_LIMIT)
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


    async def analyze_alert(self, alert_body: str) -> Dict:
        """Analyze a Prometheus alert text directly and produce structured output.
        
        Unlike analyze_incidents/root_cause_analysis, this does NOT require a
        repository — it works purely on the alert text via LLM.
        Returns root causes, impact, and remediation steps.
        """
        system_prompt = """You are a senior SRE analyzing a Prometheus alert.
Return ONLY valid JSON with these exact keys:
- root_cause (str): what is likely causing this alert
- impact (str): what systems/functionality are affected
- severity (str): critical|high|medium|low
- remediation_steps (list of str): actionable step-by-step remediation
- prevention (list of str): steps to prevent recurrence
- confidence (float): 0.0 to 1.0"""
        try:
            result = await self.llm.generate(system_prompt, alert_body)
            parsed = json.loads(result)
        except json.JSONDecodeError:
            parsed = {}
        except Exception as e:
            parsed = {}

        return {
            "incidents": [],
            "total_incidents": 1,
            "analysis": parsed.get("root_cause", alert_body[:200]),
            "summary": parsed.get("impact", "")[:300],
            "root_causes": [parsed.get("root_cause", "Unknown")] if parsed.get("root_cause") else [],
            "impact_analysis": parsed.get("impact", ""),
            "remediation_plan": parsed.get("remediation_steps", []),
            "prevention_strategies": parsed.get("prevention", []),
            "severity": parsed.get("severity", "medium"),
            "confidence": parsed.get("confidence", 0.5),
        }


async def get_incident_agent(
    repo_data: RepositoryDataService = Depends(get_repository_data_service),
    llm: LLMService = Depends(get_llm_service),
) -> IncidentAgent:
    return IncidentAgent(repo_data, llm)
