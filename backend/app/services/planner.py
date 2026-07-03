import json
from datetime import datetime
from typing import Dict, List, Optional, TypedDict, Any
from uuid import UUID

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import AgentRun, AgentStep
from app.models.project import Project
from app.services.llm_service import LLMService, get_llm_service
from app.services.memory import MemorySystem, get_memory_system
from app.services.agent_base import AgentResult
from app.services.context_builder import ContextBuilder, ProjectContext, EngineeringContext, get_context_builder
from app.core.task import Task
from app.services.repository_agent import RepositoryAgent, get_repository_agent
from app.services.knowledge_agent import KnowledgeAgent, get_knowledge_agent
from app.services.incident_agent import IncidentAgent, get_incident_agent
from app.services.documentation_agent import DocumentationAgent, get_documentation_agent
from app.services.code_review_agent import CodeReviewAgent, get_code_review_agent
from app.services.deploy_agent import DeployAgent, get_deploy_agent
from app.mcp.registry import ToolRegistry, get_registry
from app.core.di import get_db_session
from app.core.config import settings


class ExecutionPlan(TypedDict, total=False):
    intent: str
    required_agents: List[str]
    execution_order: List[str]
    needs_approval: bool
    task_description: str


AGENT_NAMES = {
    "repository": "RepositoryAgent",
    "knowledge": "KnowledgeAgent",
    "incident": "IncidentAgent",
    "documentation": "DocumentationAgent",
    "code_review": "CodeReviewAgent",
    "deploy": "DeployAgent",
}


class PlannerAgent:
    def __init__(
        self,
        db: AsyncSession,
        llm: LLMService,
        memory: Optional[MemorySystem] = None,
        mcp: Optional[ToolRegistry] = None,
    ):
        self.db = db
        self.llm = llm
        self.memory = memory
        self.mcp = mcp

    async def _inject_memory_context(self, task: str) -> str:
        if not self.memory:
            return ""
        results = await self.memory.search_semantic(task, limit=3, threshold=settings.SIMILARITY_THRESHOLD)
        if not results:
            return ""
        parts = []
        for r in results:
            text = r.get("text", "")
            if text:
                parts.append(text[:500])
        return "\nRelated past context:\n" + "\n---\n".join(parts) if parts else ""

    async def plan_and_execute(self, task: Task) -> Dict:
        task_str = task.input
        project_id = task.project_id
        run = AgentRun(
            project_id=project_id, agent_type="planner", status="running",
            input_data={"task": task_str, "project_id": str(project_id)},
        )
        self.db.add(run)
        await self.db.commit()
        await self.db.refresh(run)

        memory_context = await self._inject_memory_context(task_str) if self.memory else ""
        system_prompt = f"Break this software engineering task into 2-4 steps. For each step, describe what needs to be done. Format as JSON: [{{'step': 1, 'name': '...', 'description': '...'}}]{memory_context}"
        result = await self.llm.generate(system_prompt, task_str)

        try:
            parsed = json.loads(result)
            steps_data = parsed if isinstance(parsed, list) else [{"step": 1, "name": "Execute", "description": task}]
        except json.JSONDecodeError:
            steps_data = [{"step": 1, "name": "Execute", "description": task_str}]

        for i, step_def in enumerate(steps_data):
            step_prompt = f"Execute step {i+1}: {step_def.get('description', '')}\nTask context: {task_str}"
            step_result = await self.llm.generate(step_prompt, "Execute this step")

            step = AgentStep(
                run_id=run.id, step_index=i, step_type="llm_call",
                name=step_def.get("name", f"Step {i+1}"),
                input_data={"task": task_str, "step_description": step_def.get("description", "")},
                output_data={"result": step_result}, status="completed",
            )
            self.db.add(step)

        run.status = "completed"
        run.completed_at = datetime.utcnow()
        run.output_data = {"total_steps": len(steps_data), "result": "Task completed via LLM planning and execution"}
        await self.db.commit()
        await self.db.refresh(run)

        if self.memory:
            try:
                emb = (await self.memory.embeddings.generate_embeddings([task_str]))[0]
                if emb:
                    await self.memory.store_semantic(
                        text=f"Task: {task_str}\nPlan: {json.dumps(steps_data)}",
                        embedding=emb,
                        metadata={"type": "planner_plan", "run_id": str(run.id)},
                    )
            except Exception:
                pass

        return {
            "run_id": str(run.id),
            "status": run.status,
            "steps": len(steps_data),
            "result": "completed",
        }


class IntentRouter:
    """Classifies user input into an ExecutionPlan using LLM."""

    def __init__(self, llm: LLMService):
        self.llm = llm

    AGENT_DESCRIPTIONS = {
        "repository": "Analyze repo structure, architecture, code search",
        "knowledge": "Search indexed documents and answer questions",
        "incident": "Find error patterns, root cause analysis, recommendations",
        "documentation": "Generate README, API docs, architecture docs",
        "code_review": "Security audit, code quality, best practices",
        "deploy": "Analyze Docker, CI/CD, deployment configs",
    }

    async def route(self, ec: EngineeringContext) -> ExecutionPlan:
        user_input = ec.task.input
        context = ec.project
        conversation_context = ""
        if ec.memory.conversation_history:
            conv_lines = [
                f"{m['role']}: {m['content']}"
                for m in ec.memory.conversation_history
            ]
            conversation_context = "Recent conversation:\n" + "\n".join(conv_lines) + "\n\n"
        agent_list = "\n".join(f"  - {k}: {v}" for k, v in self.AGENT_DESCRIPTIONS.items())
        prompt = f"""Given the user request below, decide which agents should handle it.

Available agents:
{agent_list}

Return ONLY valid JSON with these keys:
- intent (str): one-sentence summary of what the user wants
- required_agents (list of str): agent names that should run
- execution_order (list of str): same as required_agents (order matters)
- needs_approval (bool): true only if this is a deployment or destructive action
- task_description (str): rephrase the user's request as a clear task

{conversation_context}User request: {user_input}"""

        result = await self.llm.generate(
            "You are an intent router. Return ONLY valid JSON.",
            prompt,
        )
        try:
            plan = json.loads(result)
            plan.setdefault("required_agents", ["repository"])
            plan.setdefault("execution_order", plan["required_agents"])
            plan.setdefault("needs_approval", False)
            plan.setdefault("task_description", user_input)
            return ExecutionPlan(**plan)
        except (json.JSONDecodeError, TypeError):
            return ExecutionPlan(
                intent="unknown",
                required_agents=["repository"],
                execution_order=["repository"],
                needs_approval=False,
                task_description=user_input,
            )


class ResponseMerger:
    """Combines multiple AgentResult dicts into one coherent response."""

    def __init__(self, llm: LLMService):
        self.llm = llm

    async def merge(
        self,
        agent_results: Dict[str, AgentResult],
        execution_plan: ExecutionPlan,
    ) -> str:
        if not agent_results:
            return "No agent results to merge."

        if len(agent_results) == 1:
            name, result = next(iter(agent_results.items()))
            text = result.get("result", "")
            recs = result.get("recommendations", [])
            footer = "\n\n**Recommendations:**\n" + "\n".join(f"- {r}" for r in recs) if recs else ""
            return text + footer

        parts = []
        for agent_name, result in agent_results.items():
            display_name = AGENT_NAMES.get(agent_name, agent_name)
            text = result.get("result", "")
            confidence = result.get("confidence", 0.5)
            recs = result.get("recommendations", [])
            parts.append(f"## {display_name} (confidence: {confidence:.0%})\n\n{text}")
            if recs:
                parts.append("**Recommendations:**\n" + "\n".join(f"- {r}" for r in recs))

        combined = "\n\n---\n\n".join(parts)

        system_prompt = "Merge these agent outputs into a single coherent response. Remove redundancy, preserve unique insights from each agent."
        merged = await self.llm.generate(system_prompt, f"Task: {execution_plan.get('task_description', '')}\n\n{combined[:6000]}")
        return merged


async def get_planner(
    db: AsyncSession = Depends(get_db_session),
    llm: LLMService = Depends(get_llm_service),
    memory: Optional[MemorySystem] = Depends(get_memory_system),
) -> PlannerAgent:
    return PlannerAgent(db, llm, memory=memory, mcp=get_registry())


async def get_intent_router(
    llm: LLMService = Depends(get_llm_service),
) -> IntentRouter:
    return IntentRouter(llm)


async def get_response_merger(
    llm: LLMService = Depends(get_llm_service),
) -> ResponseMerger:
    return ResponseMerger(llm)
