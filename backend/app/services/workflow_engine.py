import asyncio
import logging
from typing import Dict, List, Optional, Any, Callable, Awaitable
from uuid import UUID
from datetime import datetime

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import AgentRun, AgentStep
from app.models.project import Project, Repository
from app.core.di import get_db_session
from app.services.agent_base import AgentResult
from app.services.context_builder import ContextBuilder, ProjectContext, get_context_builder
from app.services.repository_agent import RepositoryAgent, get_repository_agent
from app.services.knowledge_agent import KnowledgeAgent, get_knowledge_agent
from app.services.incident_agent import IncidentAgent, get_incident_agent
from app.services.documentation_agent import DocumentationAgent, get_documentation_agent
from app.services.code_review_agent import CodeReviewAgent, get_code_review_agent
from app.services.deploy_agent import DeployAgent, get_deploy_agent

logger = logging.getLogger(__name__)


class RetryableError(Exception):
    """Error that can be retried (LLM timeout, DB transient)."""
    pass


class FatalError(Exception):
    """Error that should not be retried (invalid input, auth failure)."""
    pass


TOOL_AGENT_MAP: Dict[str, str] = {
    "analyze_code": "repository",
    "search_knowledge": "knowledge",
    "generate_docs": "documentation",
    "review_code": "code_review",
    "analyze_incidents": "incident",
    "analyze_deploy": "deploy",
}


class WorkflowEngine:
    """Engine for executing and managing workflows with retry logic.

    Delegates to real agents via their process(context) methods.
    """

    def __init__(
        self,
        db: AsyncSession,
        ctx_builder: ContextBuilder,
        repo_agent: RepositoryAgent,
        knowledge_agent: KnowledgeAgent,
        incident_agent: IncidentAgent,
        doc_agent: DocumentationAgent,
        code_review_agent: CodeReviewAgent,
        deploy_agent: DeployAgent,
    ):
        self.db = db
        self.ctx_builder = ctx_builder
        self._agents: Dict[str, Callable[[ProjectContext], Awaitable[AgentResult]]] = {
            "repository": repo_agent.process,
            "knowledge": knowledge_agent.process,
            "incident": incident_agent.process,
            "documentation": doc_agent.process,
            "code_review": code_review_agent.process,
            "deploy": deploy_agent.process,
        }

    async def execute_workflow(
        self,
        task: str,
        steps: List[Dict],
        run_id: UUID,
        max_retries: int = 3,
        retry_delay: int = 2,
    ) -> Dict:
        """Execute a workflow with retry logic and real agent delegation."""
        last_error: Optional[str] = None

        run = await self.db.get(AgentRun, run_id)
        project_id = run.project_id if run else None

        for step in steps:
            step_index = step.get("step_index", 0)
            tool = step.get("tool", "analyze")
            success = False
            attempts = 0
            step_error: Optional[str] = None

            while not success and attempts < max_retries:
                attempts += 1
                try:
                    result = await self._execute_step(tool, step, project_id, run_id, attempts)
                    success = True

                    step_record = AgentStep(
                        run_id=run_id,
                        step_index=step_index,
                        step_type=tool,
                        name=step.get("name", f"Step {step_index}"),
                        input_data=step,
                        output_data={"result": result},
                        status="completed",
                    )
                    self.db.add(step_record)
                    await self.db.commit()
                    logger.info("Workflow step %d (%s) completed (attempt %d/%d)", step_index, tool, attempts, max_retries)

                except FatalError as e:
                    step_error = str(e)
                    logger.error("Fatal error on step %d (%s): %s — not retrying", step_index, tool, step_error)
                    self.db.add(AgentStep(
                        run_id=run_id, step_index=step_index, step_type=tool,
                        name=step.get("name", f"Step {step_index}"),
                        input_data=step, output_data={"error": step_error},
                        status="failed", error_message=step_error,
                    ))
                    await self.db.commit()
                    last_error = step_error
                    break

                except RetryableError as e:
                    step_error = str(e)
                    if attempts < max_retries:
                        logger.warning("Retryable error on step %d (%s) attempt %d/%d: %s", step_index, tool, attempts, max_retries, step_error)
                        await asyncio.sleep(retry_delay)
                    else:
                        logger.error("Step %d (%s) exhausted %d retries: %s", step_index, tool, max_retries, step_error)
                        self.db.add(AgentStep(
                            run_id=run_id, step_index=step_index, step_type=tool,
                            name=step.get("name", f"Step {step_index}"),
                            input_data=step, output_data={"error": step_error},
                            status="failed", error_message=step_error,
                        ))
                        await self.db.commit()
                        last_error = step_error

                except Exception as e:
                    step_error = str(e)
                    if attempts < max_retries:
                        logger.warning("Unexpected error on step %d (%s) attempt %d/%d: %s — will retry", step_index, tool, attempts, max_retries, step_error)
                        await asyncio.sleep(retry_delay)
                    else:
                        logger.error("Step %d (%s) exhausted %d retries with unexpected error: %s", step_index, tool, max_retries, step_error)
                        self.db.add(AgentStep(
                            run_id=run_id, step_index=step_index, step_type=tool,
                            name=step.get("name", f"Step {step_index}"),
                            input_data=step, output_data={"error": step_error},
                            status="failed", error_message=step_error,
                        ))
                        await self.db.commit()
                        last_error = step_error

        return {"status": "completed" if not last_error else "failed"}

    async def _execute_step(
        self,
        tool: str,
        step: Dict,
        project_id: Optional[UUID],
        run_id: UUID,
        attempt: int,
    ) -> Any:
        """Execute a single workflow step by delegating to a real agent."""
        agent_name = TOOL_AGENT_MAP.get(tool)
        if not agent_name:
            return {"result": f"Unknown tool: {tool}"}

        agent_fn = self._agents.get(agent_name)
        if not agent_fn:
            return {"result": f"No agent registered for tool: {tool}"}

        # Build context
        repository_id: Optional[UUID] = None
        rid_raw = step.get("repository_id") or (str(project_id) if project_id else None)
        if rid_raw:
            try:
                repository_id = UUID(rid_raw) if isinstance(rid_raw, str) else rid_raw
            except (ValueError, TypeError):
                pass

        if not repository_id and project_id:
            repo_result = await self.db.execute(
                select(Repository).where(Repository.project_id == project_id).limit(1)
            )
            repo = repo_result.scalar_one_or_none()
            if repo:
                repository_id = repo.id

        task_description = step.get("description") or step.get("goal") or step.get("name", "Execute step")

        if repository_id:
            context = await self.ctx_builder.build(repository_id, task_description)
        else:
            context = ProjectContext(
                project_id=project_id or UUID("00000000-0000-0000-0000-000000000000"),
                task_description=task_description,
            )

        return await agent_fn(context)

    async def get_workflow_state(self, run_id: UUID) -> Dict:
        """Get current workflow state with real step results."""
        result = await self.db.execute(
            select(AgentStep).where(AgentStep.run_id == run_id).order_by(AgentStep.step_index)
        )
        steps = result.scalars().all()

        return {
            "run_id": str(run_id),
            "total_steps": len(steps),
            "completed_steps": sum(1 for s in steps if s.status == "completed"),
            "failed_steps": sum(1 for s in steps if s.status == "failed"),
            "steps": [
                {
                    "id": str(s.id),
                    "step_index": s.step_index,
                    "step_type": s.step_type,
                    "name": s.name,
                    "status": s.status,
                    "error_message": s.error_message,
                    "input_data": s.input_data,
                    "output_data": s.output_data,
                    "duration_ms": s.duration_ms,
                    "created_at": s.created_at.isoformat(),
                }
                for s in steps
            ],
        }

    async def resume_workflow(self, run_id: UUID) -> Dict:
        """Resume a failed workflow from the last failed step.

        Reconstructs original task and steps from AgentRun.input_data,
        skips completed steps, re-executes from the first failed step.
        """
        run = await self.db.get(AgentRun, run_id)
        if not run:
            return {"status": "not_found", "message": "Run not found"}

        result = await self.db.execute(
            select(AgentStep).where(AgentStep.run_id == run_id).order_by(AgentStep.step_index)
        )
        steps = result.scalars().all()

        completed = [s for s in steps if s.status == "completed"]
        failed = [s for s in steps if s.status == "failed"]

        if not failed:
            return {"status": "already_completed", "message": "No failed steps found"}

        original_task = ""
        original_steps: List[Dict] = []
        if run.input_data:
            original_task = run.input_data.get("task", "")
            original_steps = run.input_data.get("steps", [])

        # Re-execute from the first failed step index
        first_failed = failed[0]
        resume_from = first_failed.step_index

        remaining_steps = [s for s in original_steps if s.get("step_index", 0) >= resume_from]

        completed_details = [
            {
                "step_index": s.step_index,
                "name": s.name,
                "tool": s.step_type,
                "output": s.output_data,
            }
            for s in completed
        ]

        logger.info("Resuming workflow %s from step %d (%d remaining)", run_id, resume_from, len(remaining_steps))

        resume_result = await self.execute_workflow(
            task=original_task,
            steps=remaining_steps,
            run_id=run_id,
        )

        return {
            "status": "resumed",
            "resume_from": resume_from,
            "error": first_failed.error_message,
            "completed_before_resume": completed_details,
            "resume_result": resume_result,
        }


async def get_workflow_engine(
    db: AsyncSession = Depends(get_db_session),
    ctx_builder: ContextBuilder = Depends(get_context_builder),
    repo_agent: RepositoryAgent = Depends(get_repository_agent),
    knowledge_agent: KnowledgeAgent = Depends(get_knowledge_agent),
    incident_agent: IncidentAgent = Depends(get_incident_agent),
    doc_agent: DocumentationAgent = Depends(get_documentation_agent),
    code_review_agent: CodeReviewAgent = Depends(get_code_review_agent),
    deploy_agent: DeployAgent = Depends(get_deploy_agent),
) -> WorkflowEngine:
    return WorkflowEngine(
        db=db,
        ctx_builder=ctx_builder,
        repo_agent=repo_agent,
        knowledge_agent=knowledge_agent,
        incident_agent=incident_agent,
        doc_agent=doc_agent,
        code_review_agent=code_review_agent,
        deploy_agent=deploy_agent,
    )
