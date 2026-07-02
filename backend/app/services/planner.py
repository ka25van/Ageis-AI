import json
from datetime import datetime
from typing import Dict, List, Optional, Any, TypedDict, Annotated, Literal
from uuid import UUID

from fastapi import Depends
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import AgentRun, AgentStep
from app.models.project import Project
from app.services.llm_service import LLMService, get_llm_service
from app.core.di import get_db_session


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    task: str
    project_id: Optional[str]
    context: Dict[str, Any]
    steps: List[Dict]
    current_step: int
    max_steps: int
    result: Optional[Dict[str, Any]]


class PlannerAgent:
    def __init__(self, db: AsyncSession, llm: LLMService):
        self.db = db
        self.llm = llm
        self.memory = MemorySaver()
        self._build_graph()

    def _build_graph(self):
        workflow = StateGraph(AgentState)

        workflow.add_node("analyze", self._analyze_task)
        workflow.add_node("decompose", self._decompose_task)
        workflow.add_node("execute_step", self._execute_step)
        workflow.add_node("verify", self._verify_result)

        workflow.set_entry_point("analyze")
        workflow.add_edge("analyze", "decompose")
        workflow.add_conditional_edges(
            "decompose",
            self._should_continue,
            {"execute_step": "execute_step", "verify": "verify"},
        )
        workflow.add_edge("execute_step", "verify")
        workflow.add_conditional_edges(
            "verify",
            self._check_completion,
            {"next": "decompose", "done": END},
        )

        self.app = workflow.compile(checkpointer=self.memory)

    async def _analyze_task(self, state: AgentState) -> AgentState:
        system_prompt = """Analyze this software engineering task. Identify:
1. What needs to be done
2. What information is needed
3. Which agents/tools would be useful
Keep it concise."""

        task_context = f"Task: {state['task']}"
        if state.get("project_id"):
            task_context += f"\nProject ID: {state['project_id']}"
        result = await self.llm.generate(system_prompt, task_context)
        state["context"]["analysis"] = result
        return state

    async def _decompose_task(self, state: AgentState) -> AgentState:
        current_step = state.get("current_step", 0)
        steps = state.get("steps", [])

        if current_step < len(steps):
            return state

        system_prompt = """You are a task planner. Break this software engineering task into 2-4 specific, executable steps.
Each step should use one of these tools: analyze_code, generate_docs, review_code, search_knowledge, analyze_incidents.
Format your response as a JSON array of objects with keys: tool (str), description (str), goal (str).
Return ONLY the JSON array, no other text."""

        result = await self.llm.generate(system_prompt, state["task"])
        try:
            parsed = json.loads(result)
            if isinstance(parsed, list):
                state["steps"] = parsed
            else:
                state["steps"] = [{"tool": "analyze_code", "description": state["task"], "goal": "Complete task"}]
        except json.JSONDecodeError:
            state["steps"] = [{"tool": "analyze_code", "description": state["task"], "goal": "Complete task"}]

        state["context"]["total_steps"] = len(state["steps"])
        return state

    def _should_continue(self, state: AgentState) -> Literal["execute_step", "verify"]:
        steps = state.get("steps", [])
        current = state.get("current_step", 0)
        return "execute_step" if current < len(steps) else "verify"

    async def _execute_step(self, state: AgentState) -> AgentState:
        steps = state.get("steps", [])
        step_index = state.get("current_step", 0)

        if step_index >= len(steps):
            state["result"] = {"status": "completed", "message": "All steps executed"}
            return state

        step = steps[step_index]
        tool = step.get("tool", "analyze_code")
        description = step.get("description", state["task"])
        goal = step.get("goal", "")

        system_prompt = f"""You are executing step {step_index + 1} of a plan.
Tool: {tool}
Goal: {goal}

Execute this step and provide the results."""

        result = await self.llm.generate(system_prompt, description)

        if "results" not in state["context"]:
            state["context"]["results"] = []
        state["context"]["results"].append({
            "step": step_index + 1,
            "tool": tool,
            "output": result,
        })

        state["current_step"] = step_index + 1
        state["result"] = {
            "step": step_index + 1,
            "tool": tool,
            "status": "completed",
            "output": result[:1000],
        }
        return state

    async def _verify_result(self, state: AgentState) -> AgentState:
        results = state["context"].get("results", [])
        if not results:
            state["result"] = {"status": "completed", "message": "Task completed"}
            return state

        context = json.dumps(results, indent=2)
        system_prompt = "Verify the results of this task execution. Is the task complete? Summarize the outcomes."
        verification = await self.llm.generate(system_prompt, context)

        state["result"] = {
            "status": "completed",
            "verification": verification,
            "steps_completed": len(results),
        }
        return state

    def _check_completion(self, state: AgentState) -> Literal["next", "done"]:
        steps = state.get("steps", [])
        current = state.get("current_step", 0)
        return "next" if current < len(steps) else "done"

    async def run_task(self, task: str, project_id: Optional[UUID] = None) -> Dict:
        config = {"configurable": {"thread_id": str(datetime.utcnow().timestamp())}}

        initial_state: AgentState = {
            "messages": [],
            "task": task,
            "project_id": str(project_id) if project_id else None,
            "context": {},
            "steps": [],
            "current_step": 0,
            "max_steps": 5,
            "result": None,
        }

        result = await self.app.ainvoke(initial_state, config)
        return {
            "task": task,
            "project_id": str(project_id) if project_id else None,
            "steps_planned": len(result.get("steps", [])),
            "steps_executed": result.get("current_step", 0),
            "result": result.get("result", {}),
            "details": result.get("context", {}).get("results", []),
        }

    async def plan_and_execute(self, task: str, project_id: UUID) -> Dict:
        run = AgentRun(
            project_id=project_id,
            agent_type="planner",
            status="running",
            input_data={"task": task, "project_id": str(project_id)},
        )
        self.db.add(run)
        await self.db.commit()
        await self.db.refresh(run)

        system_prompt = """Break this software engineering task into 2-4 steps. 
For each step, describe what needs to be done.
Format as JSON: [{"step": 1, "name": "...", "description": "..."}]"""

        result = await self.llm.generate(system_prompt, task)

        try:
            parsed = json.loads(result)
            steps_data = parsed if isinstance(parsed, list) else [{"step": 1, "name": "Execute", "description": task}]
        except json.JSONDecodeError:
            steps_data = [{"step": 1, "name": "Execute", "description": task}]

        for i, step_def in enumerate(steps_data):
            system_prompt = f"Execute step {i+1}: {step_def.get('description', '')}\nTask context: {task}"
            step_result = await self.llm.generate(system_prompt, f"Execute this step")

            step = AgentStep(
                run_id=run.id,
                step_index=i,
                step_type="llm_call",
                name=step_def.get("name", f"Step {i+1}"),
                input_data={"task": task, "step_description": step_def.get("description", "")},
                output_data={"result": step_result},
                status="completed",
            )
            self.db.add(step)

        run.status = "completed"
        run.completed_at = datetime.utcnow()
        run.output_data = {
            "total_steps": len(steps_data),
            "result": "Task completed via LLM planning and execution",
        }
        await self.db.commit()
        await self.db.refresh(run)

        return {
            "run_id": str(run.id),
            "status": run.status,
            "steps": len(steps_data),
            "result": "completed",
        }


async def get_planner(
    db: AsyncSession = Depends(get_db_session),
    llm: LLMService = Depends(get_llm_service),
) -> PlannerAgent:
    return PlannerAgent(db, llm)
