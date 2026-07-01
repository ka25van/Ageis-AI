import asyncio
from typing import Dict, List, Optional, Any, Callable, Awaitable
from uuid import UUID
from datetime import datetime

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import AgentRun, AgentStep
from app.models.project import Project
from app.core.di import get_db_session


class WorkflowEngine:
    """Engine for executing and managing workflows with retry logic."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def execute_workflow(
        self,
        task: str,
        steps: List[Dict],
        run_id: UUID,
        max_retries: int = 3,
        retry_delay: int = 2,
    ) -> Dict:
        """Execute a workflow with retry logic."""
        for step in steps:
            success = False
            attempts = 0
            last_error = None

            while not success and attempts < max_retries:
                attempts += 1
                try:
                    # Execute step
                    result = await self._execute_step(step, run_id, attempts)
                    success = True
                    last_error = None

                    # Save step
                    step_record = AgentStep(
                        run_id=run_id,
                        step_index=step.get("step_index", 0),
                        step_type=step.get("type", "execute"),
                        name=step.get("name", f"Step {step.get('step_index', 0)}"),
                        input_data=step,
                        output_data={"result": result},
                        status="completed",
                        duration_ms=step.get("duration_ms", 0),
                    )
                    self.db.add(step_record)
                    await self.db.commit()

                except Exception as e:
                    last_error = str(e)
                    if attempts < max_retries:
                        await asyncio.sleep(retry_delay)
                    else:
                        # Save failed step
                        step_record = AgentStep(
                            run_id=run_id,
                            step_index=step.get("step_index", 0),
                            step_type=step.get("type", "execute"),
                            name=step.get("name", f"Step {step.get('step_index', 0)}"),
                            input_data=step,
                            output_data={"error": last_error},
                            status="failed",
                            error_message=last_error,
                        )
                        self.db.add(step_record)
                        await self.db.commit()

        return {"status": "completed" if not last_error else "failed"}

    async def _execute_step(self, step: Dict, run_id: UUID, attempt: int) -> Any:
        """Execute a single workflow step."""
        tool = step.get("tool", "analyze")

        if tool == "search_knowledge":
            return await self._search_knowledge(step)
        elif tool == "read_files":
            return await self._read_files(step)
        elif tool == "run_code":
            return await self._run_code(step)
        elif tool == "analyze":
            return await self._analyze(step)
        else:
            return {"result": f"Unknown tool: {tool}"}

    async def _search_knowledge(self, step: Dict) -> Dict:
        """Search knowledge base."""
        query = step.get("params", {}).get("query", "")
        return {"results": f"Search results for: {query}"}

    async def _read_files(self, step: Dict) -> Dict:
        """Read files from repository."""
        path = step.get("params", {}).get("path", "")
        return {"files": [f"file: {path}"]}

    async def _run_code(self, step: Dict) -> Dict:
        """Execute code."""
        action = step.get("params", {}).get("action", "")
        return {"output": f"Executed: {action}"}

    async def _analyze(self, step: Dict) -> Dict:
        """Analyze task."""
        task = step.get("params", {}).get("task", "")
        return {"analysis": f"Analysis of: {task}"}

    async def get_workflow_state(self, run_id: UUID) -> Dict:
        """Get current workflow state."""
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
        """Resume a failed workflow from the last failed step."""
        result = await self.db.execute(
            select(AgentStep).where(AgentStep.run_id == run_id).order_by(AgentStep.step_index)
        )
        steps = result.scalars().all()

        # Find last failed step
        failed_steps = [s for s in steps if s.status == "failed"]
        if not failed_steps:
            return {"status": "already_completed", "message": "No failed steps found"}

        # Resume from failed step
        last_failed = failed_steps[-1]
        return {
            "status": "resumed",
            "resume_from": last_failed.step_index,
            "error": last_faded.error_message,
        }


async def get_workflow_engine(db: AsyncSession = Depends(get_db_session)) -> WorkflowEngine:
    return WorkflowEngine(db)