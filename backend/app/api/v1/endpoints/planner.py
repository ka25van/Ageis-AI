from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.api.v1.endpoints.auth import get_current_user
from app.core.di import get_db_session
from app.models.user import User
from app.models.project import Project
from app.services.planner import PlannerAgent, get_planner

router = APIRouter(prefix="/planner", tags=["planner"])


class PlanRequest(BaseModel):
    task: str
    project_id: str


@router.post("/plan")
async def plan_and_execute(
    body: PlanRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    planner: PlannerAgent = Depends(get_planner),
):
    project_id = UUID(body.project_id)
    task = body.task
    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == current_user.id)
    )
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    result = await planner.plan_and_execute(task, project_id)
    return result


@router.get("/runs/{run_id}")
async def get_run_status(
    run_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    from app.models.agent import AgentRun
    result = await db.execute(
        select(AgentRun).where(AgentRun.id == run_id)
    )
    run = result.scalar_one_or_none()

    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Run not found",
        )

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