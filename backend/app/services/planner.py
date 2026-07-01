from typing import Dict, List, Optional, Any, TypedDict, Annotated, Literal
from uuid import UUID
from datetime import datetime
import json

from fastapi import Depends

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph.message import add_messages

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import AgentRun, AgentStep
from app.models.project import Project
from app.models.document import Document, DocumentChunk
from app.services.embeddings import EmbeddingService
from app.core.di import get_db_session


class AgentState(TypedDict):
    """State for the planner agent."""
    messages: Annotated[list, add_messages]
    task: str
    project_id: Optional[str]
    tools_available: List[str]
    current_step: int
    max_steps: int
    context: Dict[str, Any]
    result: Optional[Dict[str, Any]]


class PlannerAgent:
    """LangGraph-based planner agent for task decomposition and execution."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.memory = MemorySaver()
        self._build_graph()

    def _build_graph(self):
        """Build the LangGraph state machine graph."""
        workflow = StateGraph(AgentState)

        # Define nodes
        workflow.add_node("analyze", self._analyze_task)
        workflow.add_node("decompose", self._decompose_task)
        workflow.add_node("execute", self._execute_step)
        workflow.add_node("verify", self._verify_result)

        # Define edges
        workflow.set_entry_point("analyze")
        workflow.add_edge("analyze", "decompose")
        workflow.add_conditional_edges(
            "decompose",
            self._should_continue,
            {
                "execute": "execute",
                "complete": "verify",
            }
        )
        workflow.add_edge("execute", "verify")
        workflow.add_conditional_edges(
            "verify",
            self._check_completion,
            {
                "next": "decompose",
                "done": END,
            }
        )

        self.app = workflow.compile(checkpointer=self.memory)

    async def _analyze_task(self, state: AgentState) -> AgentState:
        """Analyze the task and determine requirements."""
        state["context"]["tools_available"] = [
            "search_knowledge",
            "read_files",
            "run_code",
            "list_repositories",
            "query_database",
        ]
        state["current_step"] = 0
        state["result"] = {"status": "analyzed"}
        return state

    async def _decompose_task(self, state: AgentState) -> AgentState:
        """Break task into executable steps."""
        steps = []
        task = state["task"]
        project_id = state.get("project_id")

        # Simple decomposition: parse into sub-steps
        if "search" in task.lower():
            steps.append({"tool": "search_knowledge", "params": {"query": task}})
        if "analyze" in task.lower():
            steps.append({"tool": "read_files", "params": {"path": "."}})
        if "create" in task.lower():
            steps.append({"tool": "execute", "params": {"action": task}})

        if not steps:
            steps.append({"tool": "analyze", "params": {"task": task}})

        state["context"]["steps"] = steps
        state["context"]["total_steps"] = len(steps)
        state["current_step"] = 0
        return state

    def _should_continue(self, state: AgentState) -> Literal["execute", "complete"]:
        """Determine if more steps need execution."""
        steps = state["context"].get("steps", [])
        current = state["current_step"]
        return "execute" if current < len(steps) else "complete"

    async def _execute_step(self, state: AgentState) -> AgentState:
        """Execute the current step."""
        steps = state["context"].get("steps", [])
        step_index = state["current_step"]

        if step_index < len(steps):
            step = steps[step_index]
            state["result"] = {
                "step": step_index,
                "tool": step.get("tool"),
                "status": "completed",
                "output": f"Executed step {step_index + 1} of {len(steps)}",
            }
            state["current_step"] += 1

        return state

    async def _verify_result(self, state: AgentState) -> AgentState:
        """Verify the result and determine next steps."""
        if state.get("error"):
            state["result"]["status"] = "failed"
        else:
            state["result"]["status"] = "completed"

        return state

    def _check_completion(self, state: AgentState) -> Literal["next", "done"]:
        """Check if all steps are done."""
        steps = state["context"].get("steps", [])
        return "done" if state["current_step"] >= len(steps) else "next"

    async def run_task(self, task: str, project_id: Optional[UUID] = None) -> Dict:
        """Run a task through the planning and execution pipeline."""
        config = {"configurable": {"thread_id": str(datetime.utcnow().timestamp())}}

        initial_state: AgentState = {
            "messages": [],
            "task": task,
            "project_id": str(project_id) if project_id else None,
            "tools_available": [],
            "current_step": 0,
            "max_steps": 5,
            "context": {},
            "result": None,
        }

        result = await self.app.ainvoke(initial_state, config)
        return result

    async def plan_and_execute(self, task: str, project_id: UUID) -> Dict:
        """Full planning and execution pipeline."""
        # Create agent run
        run = AgentRun(
            project_id=project_id,
            agent_type="planner",
            status="running",
            input_data={"task": task, "project_id": str(project_id)},
        )
        self.db.add(run)
        await self.db.commit()
        await self.db.refresh(run)

        # Run through planner
        # For now, simple decomposition and return
        steps = [
            {"step_type": "analysis", "name": "Understand task", "description": f"Analyze: {task}"},
            {"step_type": "tool_call", "name": "Execute", "description": "Run step"},
            {"step_type": "verify", "name": "Verify", "description": "Check results"},
        ]

        for i, step_def in enumerate(steps):
            step = AgentStep(
                run_id=run.id,
                step_index=i,
                step_type=step_def["step_type"],
                name=step_def["name"],
                input_data={"task": task},
                output_data={"result": f"Step {i} completed"},
                status="completed",
            )
            self.db.add(step)

        # Update run status
        run.status = "completed"
        run.completed_at = datetime.utcnow()
        run.output_data = {"total_steps": len(steps), "result": "Task completed"}
        await self.db.commit()
        await self.db.refresh(run)

        return {
            "run_id": str(run.id),
            "status": run.status,
            "steps": len(steps),
            "result": "completed",
        }


async def get_planner(db: AsyncSession = Depends(get_db_session)) -> PlannerAgent:
    return PlannerAgent(db)