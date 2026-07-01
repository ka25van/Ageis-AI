from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.api.v1.endpoints.auth import get_current_user
from app.core.di import get_db_session
from app.models.user import User
from app.models.project import Project
from app.services.workflow_engine import WorkflowEngine, get_workflow_engine
from app.models.agent import AgentRun

router = APIRouter(prefix="/workflows", tags=["workflows"])


@router.post("/execute")
async def execute_workflow(
    task: str,
    project_id: UUID,
    steps: list[dict],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    engine: WorkflowEngine = Depends(get_workflow_engine),
):
    # Verify project
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == current_user.id)
    )
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Create agent run
    run = AgentRun(
        project_id=project_id,
        agent_type="workflow",
        status="running",
        input_data={"task": task, "steps": steps},
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    result = await engine.execute_workflow(task, steps, run.id)
    return {"run_id": str(run.id), "result": result}


@router.get("/runs/{run_id}/state")
async def get_workflow_state(
    run_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    engine: WorkflowEngine = Depends(get_workflow_engine),
):
    state = await engine.get_workflow_state(run_id)
    return state


@router.post("/runs/{run_id}/resume")
async def resume_workflow(
    run_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    engine: WorkflowEngine = Depends(get_workflow_engine),
):
    result = await engine.resume_workflow(run_id)
    return result


@router.post("/runs/{run_id}/retry")
async def retry_workflow(
    run_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    engine: WorkflowEngine = Depends(get_workflow_engine),
):
    result = await engine.resume_workflow(run_id)
    return result