import json
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.api.v1.endpoints.auth import get_current_user
from app.core.di import get_db_session
from app.models.user import User
from app.models.project import Project
from app.models.project import Repository
from app.services.planner import (
    PlannerAgent, IntentRouter, ResponseMerger,
    get_planner, get_intent_router, get_response_merger,
)
from app.services.repository_agent import RepositoryAgent, get_repository_agent
from app.services.knowledge_agent import KnowledgeAgent, get_knowledge_agent
from app.services.incident_agent import IncidentAgent, get_incident_agent
from app.services.documentation_agent import DocumentationAgent, get_documentation_agent
from app.services.code_review_agent import CodeReviewAgent, get_code_review_agent
from app.services.deploy_agent import DeployAgent, get_deploy_agent
from app.services.context_builder import ContextBuilder, EngineeringContext, get_context_builder
from app.services.memory import MemorySystem, get_memory_system
from app.services.agent_base import AgentResult
from app.core.task import Task, TaskSource, TaskType

router = APIRouter(prefix="/planner", tags=["planner"])


class PlanRequest(BaseModel):
    task: str
    project_id: str


class RouteRequest(BaseModel):
    message: str
    project_id: str
    repository_id: str | None = None


@router.post("/plan")
async def plan_and_execute(
    body: PlanRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    planner: PlannerAgent = Depends(get_planner),
):
    project_id = UUID(body.project_id)
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == current_user.id)
    )
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    task = Task(input=body.task, project_id=project_id, source=TaskSource.API, type=TaskType.ANALYSIS)
    result = await planner.plan_and_execute(task)
    return result


@router.post("/route")
async def route_and_execute(
    body: RouteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    planner: PlannerAgent = Depends(get_planner),
    router_inject: IntentRouter = Depends(get_intent_router),
    merger: ResponseMerger = Depends(get_response_merger),
    ctx_builder: ContextBuilder = Depends(get_context_builder),
    repo_agent: RepositoryAgent = Depends(get_repository_agent),
    knowledge_agent: KnowledgeAgent = Depends(get_knowledge_agent),
    incident_agent: IncidentAgent = Depends(get_incident_agent),
    doc_agent: DocumentationAgent = Depends(get_documentation_agent),
    code_review_agent: CodeReviewAgent = Depends(get_code_review_agent),
    deploy_agent: DeployAgent = Depends(get_deploy_agent),
    memory: MemorySystem = Depends(get_memory_system),
):
    project_id = UUID(body.project_id)
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == current_user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    # Resolve repository
    repository_id: UUID | None = None
    if body.repository_id:
        repository_id = UUID(body.repository_id)
        repo_result = await db.execute(
            select(Repository).where(Repository.id == repository_id, Repository.project_id == project_id)
        )
        if not repo_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Repository not found")
    else:
        repo_result = await db.execute(
            select(Repository).where(Repository.project_id == project_id).limit(1)
        )
        repo = repo_result.scalar_one_or_none()
        if repo:
            repository_id = repo.id

    # Step 0: Build EngineeringContext (root aggregate)
    task = Task(
        input=body.message,
        project_id=project_id,
        repository_id=repository_id,
        source=TaskSource.CHAT,
        type=TaskType.QUESTION,
    )
    ec = await ctx_builder.build_engineering_context(task)

    # Enrich memory context with conversation history (available only at endpoint layer)
    try:
        past_conversation = await memory.get_conversation(project_id, current_user.id, limit=10)
        if past_conversation:
            ec.memory.conversation_history = [
                {"role": m["role"], "content": m["content"][:200]}
                for m in past_conversation[-5:]
            ]
    except Exception:
        pass

    # Step 1: Intent routing via EngineeringContext
    execution_plan = await router_inject.route(ec)
    intent = execution_plan.get("intent", "unknown")
    required_agents = execution_plan.get("required_agents", ["repository"])
    needs_approval = execution_plan.get("needs_approval", False)
    task_description = execution_plan.get("task_description", body.message)

    # Step 2: Use context from EngineeringContext (backward compatible)
    context = ec.project

    # Step 3: Dispatch to agents
    agent_results: dict[str, AgentResult] = {}

    def _needs_repo(agent_name: str) -> bool:
        return agent_name in ("repository", "incident", "documentation", "code_review", "deploy")

    for agent_name in required_agents:
        if _needs_repo(agent_name) and not repository_id:
            continue

        try:
            if agent_name == "repository" and context:
                agent_results[agent_name] = await repo_agent.process(context)
            elif agent_name == "knowledge":
                ka_context = context if context else await ctx_builder.build(project_id, task_description)
                agent_results[agent_name] = await knowledge_agent.process(ka_context)
            elif agent_name == "incident" and context:
                agent_results[agent_name] = await incident_agent.process(context)
            elif agent_name == "documentation" and context:
                agent_results[agent_name] = await doc_agent.process(context)
            elif agent_name == "code_review" and context:
                agent_results[agent_name] = await code_review_agent.process(context)
            elif agent_name == "deploy" and context:
                agent_results[agent_name] = await deploy_agent.process(context)
        except Exception as e:
            agent_results[agent_name] = AgentResult(
                result=f"Agent '{agent_name}' failed: {e}",
                confidence=0.0,
                recommendations=[],
                follow_up_actions=["Try again or use a different agent"],
            )

    # Step 4: Merge responses
    merged = await merger.merge(agent_results, execution_plan)

    # Step 5: Store user message (assistant message stored after final response is built)
    await memory.store_conversation(project_id, current_user.id, "user", body.message)

    # Step 6: Fallback for unclear intent
    if not agent_results or intent == "unknown":
        planner_result = await planner.plan_and_execute(task)
        merged = f"I couldn't determine which agents to use. Here's a general plan:\n\n{json.dumps(planner_result, indent=2)}"
        await memory.store_conversation(project_id, current_user.id, "assistant", merged[:2000])
        return {
            "response": merged,
            "execution_plan": dict(execution_plan),
            "agents_used": [],
            "agent_details": {},
            "needs_approval": False,
            "planner_fallback": planner_result,
        }

    await memory.store_conversation(project_id, current_user.id, "assistant", merged[:2000])

    return {
        "response": merged,
        "execution_plan": dict(execution_plan),
        "agents_used": required_agents,
        "agent_details": {
            name: {
                "confidence": r.get("confidence", 0),
                "recommendations": r.get("recommendations", []),
                "follow_up_actions": r.get("follow_up_actions", []),
            }
            for name, r in agent_results.items()
        },
        "needs_approval": needs_approval,
        "planner_fallback": None,
    }


@router.get("/runs/{run_id}")
async def get_run_status(
    run_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    from app.models.agent import AgentRun
    result = await db.execute(select(AgentRun).where(AgentRun.id == run_id))
    run = result.scalar_one_or_none()

    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    return {
        "id": str(run.id),
        "status": run.status,
        "agent_type": run.agent_type,
        "input_data": run.input_data,
        "output_data": run.output_data,
        "error_message": run.error_message,
        "started_at": run.started_at,
        "completed_at": run.completed_at,
    }


@router.get("/runs/{run_id}/steps")
async def get_run_steps(
    run_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    from app.models.agent import AgentStep
    result = await db.execute(
        select(AgentStep).where(AgentStep.run_id == run_id).order_by(AgentStep.step_index)
    )
    steps = result.scalars().all()

    return [
        {
            "step_index": s.step_index,
            "step_type": s.step_type,
            "name": s.name,
            "input_data": s.input_data,
            "output_data": s.output_data,
            "status": s.status,
            "error_message": s.error_message,
        }
        for s in steps
    ]
