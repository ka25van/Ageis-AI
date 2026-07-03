import json
from datetime import datetime
from typing import Dict, List, Optional, Any, TypedDict, Annotated, Literal
from uuid import UUID

from fastapi import Depends
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import AgentRun, AgentStep
from app.models.project import Project
from app.services.llm_service import LLMService, get_llm_service
from app.services.memory import MemorySystem, get_memory_system
from app.mcp.registry import ToolRegistry, get_registry
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
    def __init__(self, db: AsyncSession, llm: LLMService, memory: Optional[MemorySystem] = None, mcp: Optional[ToolRegistry] = None):
        self.db = db
        self.llm = llm
        self.memory = memory
        self.mcp = mcp
        self.checkpointer = MemorySaver()
        self._build_graph()

    def _build_graph(self):
        workflow = StateGraph(AgentState)
        workflow.add_node("analyze", self._analyze_task)
        workflow.add_node("decompose", self._decompose_task)
        workflow.add_node("execute_step", self._execute_step)
        workflow.add_node("verify", self._verify_result)

        workflow.set_entry_point("analyze")
        workflow.add_edge("analyze", "decompose")
        workflow.add_conditional_edges("decompose", self._should_continue, {"execute_step": "execute_step", "verify": "verify"})
        workflow.add_edge("execute_step", "verify")
        workflow.add_conditional_edges("verify", self._check_completion, {"next": "decompose", "done": END})

        self.app = workflow.compile(checkpointer=self.checkpointer)

    async def _inject_memory_context(self, task: str) -> str:
        if not self.memory:
            return ""
        results = await self.memory.search_semantic(task, limit=3, threshold=0.3)
        if not results:
            return ""
        parts = []
        for r in results:
            text = r.get("text", "")
            if text:
                parts.append(text[:500])
        return "\nRelated past context:\n" + "\n---\n".join(parts) if parts else ""

    async def _analyze_task(self, state: AgentState) -> AgentState:
        memory_context = await self._inject_memory_context(state["task"])
        system_prompt = "Analyze this software engineering task. Identify: 1. What needs to be done 2. What information is needed 3. Which agents/tools would be useful. Keep it concise."
        task_context = f"Task: {state['task']}"
        if state.get("project_id"):
            task_context += f"\nProject ID: {state['project_id']}"
        task_context += memory_context
        result = await self.llm.generate(system_prompt, task_context)
        state["context"]["analysis"] = result
        return state

    async def _decompose_task(self, state: AgentState) -> AgentState:
        current_step = state.get("current_step", 0)
        steps = state.get("steps", [])
        if current_step < len(steps):
            return state

        available_tools = ["analyze_code", "generate_docs", "review_code", "search_knowledge", "analyze_incidents"]
        if self.mcp:
            for t in self.mcp.list_tools():
                available_tools.append(t["name"])

        tools_list = ", ".join(available_tools)
        system_prompt = f"You are a task planner. Break this software engineering task into 2-4 specific executable steps. Each step should use one of these tools: {tools_list}. Return ONLY a JSON array of objects with keys: tool (str), description (str), goal (str)."
        result = await self.llm.generate(system_prompt, state["task"])
        try:
            parsed = json.loads(result)
            state["steps"] = parsed if isinstance(parsed, list) else [{"tool": "analyze_code", "description": state["task"], "goal": "Complete task"}]
        except json.JSONDecodeError:
            state["steps"] = [{"tool": "analyze_code", "description": state["task"], "goal": "Complete task"}]
        state["context"]["total_steps"] = len(state["steps"])
        return state

    def _should_continue(self, state: AgentState) -> Literal["execute_step", "verify"]:
        return "execute_step" if state.get("current_step", 0) < len(state.get("steps", [])) else "verify"

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

        # Try MCP dispatch first
        result = None
        if self.mcp and tool in self.mcp:
            try:
                mcp_result = await self.mcp.execute(tool, {"description": description, "goal": goal}, {"task": state["task"]})
                result = json.dumps(mcp_result, indent=2)
            except Exception as e:
                result = f"MCP tool '{tool}' failed: {e}"

        if result is None:
            system_prompt = f"You are executing step {step_index + 1} of a plan. Tool: {tool}. Goal: {goal}. Execute this step and provide results."
            result = await self.llm.generate(system_prompt, description)

        if "results" not in state["context"]:
            state["context"]["results"] = []
        state["context"]["results"].append({"step": step_index + 1, "tool": tool, "output": result})
        state["current_step"] = step_index + 1
        state["result"] = {"step": step_index + 1, "tool": tool, "status": "completed", "output": result[:1000]}
        return state

    async def _verify_result(self, state: AgentState) -> AgentState:
        results = state["context"].get("results", [])
        if not results:
            state["result"] = {"status": "completed", "message": "Task completed"}
            return state

        context = json.dumps(results, indent=2)
        verification = await self.llm.generate("Verify the results of this task execution. Is the task complete? Summarize the outcomes.", context)
        state["result"] = {"status": "completed", "verification": verification, "steps_completed": len(results)}

        # Store results in semantic memory
        if self.memory:
            try:
                emb = (await self.memory.embeddings.generate_embeddings([state["task"]]))[0]
                if emb:
                    await self.memory.store_semantic(
                        text=f"Task: {state['task']}\nResult: {verification[:500]}",
                        embedding=emb,
                        metadata={"type": "planner_result", "steps": len(results)},
                    )
            except Exception:
                pass

        return state

    def _check_completion(self, state: AgentState) -> Literal["next", "done"]:
        return "next" if state.get("current_step", 0) < len(state.get("steps", [])) else "done"

    async def run_task(self, task: str, project_id: Optional[UUID] = None) -> Dict:
        config = {"configurable": {"thread_id": str(datetime.utcnow().timestamp())}}
        initial_state: AgentState = {
            "messages": [], "task": task,
            "project_id": str(project_id) if project_id else None,
            "context": {}, "steps": [], "current_step": 0,
            "max_steps": 5, "result": None,
        }
        result = await self.app.ainvoke(initial_state, config)
        return {
            "task": task, "project_id": str(project_id) if project_id else None,
            "steps_planned": len(result.get("steps", [])),
            "steps_executed": result.get("current_step", 0),
            "result": result.get("result", {}),
            "details": result.get("context", {}).get("results", []),
        }

    async def plan_and_execute(self, task: str, project_id: UUID) -> Dict:
        run = AgentRun(
            project_id=project_id, agent_type="planner", status="running",
            input_data={"task": task, "project_id": str(project_id)},
        )
        self.db.add(run)
        await self.db.commit()
        await self.db.refresh(run)

        # Inject memory context
        memory_context = await self._inject_memory_context(task) if self.memory else ""
        system_prompt = f"Break this software engineering task into 2-4 steps. For each step, describe what needs to be done. Format as JSON: [{{'step': 1, 'name': '...', 'description': '...'}}]{memory_context}"
        result = await self.llm.generate(system_prompt, task)

        try:
            parsed = json.loads(result)
            steps_data = parsed if isinstance(parsed, list) else [{"step": 1, "name": "Execute", "description": task}]
        except json.JSONDecodeError:
            steps_data = [{"step": 1, "name": "Execute", "description": task}]

        for i, step_def in enumerate(steps_data):
            step_prompt = f"Execute step {i+1}: {step_def.get('description', '')}\nTask context: {task}"
            step_result = await self.llm.generate(step_prompt, "Execute this step")

            step = AgentStep(
                run_id=run.id, step_index=i, step_type="llm_call",
                name=step_def.get("name", f"Step {i+1}"),
                input_data={"task": task, "step_description": step_def.get("description", "")},
                output_data={"result": step_result}, status="completed",
            )
            self.db.add(step)

        run.status = "completed"
        run.completed_at = datetime.utcnow()
        run.output_data = {"total_steps": len(steps_data), "result": "Task completed via LLM planning and execution"}
        await self.db.commit()
        await self.db.refresh(run)

        # Store in semantic memory
        if self.memory:
            try:
                emb = (await self.memory.embeddings.generate_embeddings([task]))[0]
                if emb:
                    await self.memory.store_semantic(
                        text=f"Task: {task}\nPlan: {json.dumps(steps_data)}",
                        embedding=emb,
                        metadata={"type": "planner_plan", "run_id": str(run.id)},
                    )
            except Exception:
                pass

        return {"run_id": str(run.id), "status": run.status, "steps": len(steps_data), "result": "completed"}


async def get_planner(
    db: AsyncSession = Depends(get_db_session),
    llm: LLMService = Depends(get_llm_service),
    memory: Optional[MemorySystem] = Depends(get_memory_system),
) -> PlannerAgent:
    return PlannerAgent(db, llm, memory=memory, mcp=get_registry())
