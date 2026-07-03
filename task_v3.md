# Aegis AI v3 — Executor Layer: Generic Adapter Architecture

## Purpose

This document tracks the introduction of a generic execution adapter layer that normalizes all execution targets (agents, MCP tools, REST calls, Python functions) into the common callable signature `(context: ProjectContext) -> AgentResult`.

This replaces ad-hoc dispatch with a registration-time normalization pattern. The CapabilityRegistry evolves from a simple agent registry into a generic execution router.

## Design

### Architectural invariant

```
WorkflowEngine → CapabilityRegistry.resolve(name).executor(context: ProjectContext) → AgentResult
```

No change to this call chain. The WorkflowEngine, ExecutionRuntime, and execute_plan() are completely unchanged.

### What changed

**Before:** `CapabilityRegistry` stored only agent functions. MCP tools lived in a parallel `ToolRegistry` with no code path dispatching to them.

**After:** `CapabilityRegistry` stores normalized callables. All execution types are normalized to the same signature via adapter functions at registration time. MCP tools are registered alongside agents. REST and Python stubs exist for future extensibility.

### Adapter factory functions (`backend/app/services/execution_adapters.py`)

| Function | Purpose |
|---|---|
| `adapt_agent(fn)` | Identity — agent `.process()` already matches the signature |
| `adapt_mcp(tool_name, mcp_registry)` | Wraps MCP tool handler; reads `context.step_input` for params |
| `adapt_rest(url, method)` | Stub — no real HTTP calls. Returns descriptive message. |
| `adapt_python(fn)` | Stub — no sandboxed execution. If `fn` provided, calls with `step_input`. |

### Capability metadata enriched

`Capability` now exposes:
- `name: str`
- `description: str`
- `executor: Callable` (the adapter)
- `execution_type: str` — `"agent"`, `"mcp"`, `"rest"`, `"python"`

`CapabilityRegistry.list_capabilities()` now includes `execution_type` in its output dict.

### How step input reaches adapters

`ProjectContext` gained:
- `step_input: Dict = field(default_factory=dict)`

Populated by `WorkflowEngine._build_context_for_step()` from `ExecutionStep.input`. Adapters read `context.step_input` for parameters. Agents ignore this field entirely.

---

## Milestone M1 — Generic Adapter Architecture ✅

**Goal**: Normalize all execution targets into a common callable signature. Extend CapabilityRegistry metadata. Wire MCP tools through adapters. No new architectural layers.

**Completed**: 2026-07-03

### Tasks

- [x] Add `execution_type` to `Capability.__init__()` and `CapabilityRegistry.register()`
  - `execution_type: str = "agent"` — defaults preserved, no existing callers change
- [x] Add `execution_type` to `CapabilityRegistry.list_capabilities()` output
- [x] Add `step_input: Dict = field(default_factory=dict)` to `ProjectContext`
  - Populated by `WorkflowEngine._build_context_for_step()` from `ExecutionStep.input`
  - Agents ignore it; adapters read it for parameters
- [x] Create `backend/app/services/execution_adapters.py`
  - `adapt_agent(fn)` — identity function for symmetry
  - `adapt_mcp(tool_name, mcp_registry)` — wraps MCP tool; reads `context.step_input`; catches exceptions; maps `dict` result to `AgentResult`
  - `adapt_rest(url, method)` — stub; returns `"not implemented"` message
  - `adapt_python(fn)` — stub; optionally calls provided callable; returns `"not configured"` otherwise
- [x] Wrap agent registrations with `adapt_agent()` in `get_workflow_engine()`
  - Old: `registry.register("repository", "...", repo_agent.process)`
  - New: `registry.register("repository", "...", adapt_agent(repo_agent.process))`
  - Functionally identical — `adapt_agent` is identity — but establishes the pattern
- [x] Register all MCP tools via `adapt_mcp()` in `get_workflow_engine()`
  - Iterates `ToolRegistry.list_tools()`, registers each with `execution_type="mcp"`
  - Skips names that already exist (agent names take priority)
  - Logs warning if MCP registry cannot be loaded
- [x] Register stub capabilities `rest_call` (REST executor) and `python_exec` (Python executor)
  - Both set `execution_type="rest"` and `"python"` respectively
  - Return descriptive "not implemented" messages at runtime
- [x] Verify backend app loads without errors
- [x] Verify all MCP tools register with correct `execution_type="mcp"`
- [x] Verify adapter signature contract (`(context) -> AgentResult`) through unit tests
- [x] No changes to existing agents, API endpoints, frontend, Planner, or ExecutionPlan

### Acceptance Criteria

- [x] 15 MCP tools (GitHub: 3, Filesystem: 4, Docker: 4, AWS: 4) registered as capabilities with `execution_type="mcp"`
- [x] 6 existing agents registered with `execution_type="agent"` (functionally identical to before)
- [x] `rest_call` and `python_exec` registered with `execution_type="rest"` and `"python"` (stubs)
- [x] No new architectural layers added
- [x] WorkflowEngine.execute_plan() unchanged — `registry.resolve() + runtime.execute_step()` still works
- [x] ExecutionRuntime unchanged — retry/timeout/cancel still works on any normalized callable
- [x] Backend loads without import errors
- [x] All existing agent endpoints return identical response shapes
- [x] All existing frontend pages unchanged

### Files Created

- `backend/app/services/execution_adapters.py` — adapter factory functions (agent, mcp, rest, python)

### Files Modified

- `backend/app/services/capability_registry.py` — added `execution_type` to `Capability` and `register()`
- `backend/app/services/context_builder.py` — added `step_input` field to `ProjectContext`
- `backend/app/services/workflow_engine.py` — set `context.step_input` in `_build_context_for_step()`; wrap agent registrations with `adapt_agent()`; register MCP tools via `adapt_mcp()`; register REST/Python stubs

### Files NOT Modified (backward compatibility)

- All agent files (repository, knowledge, incident, documentation, code_review, deploy)
- All API endpoint files
- `backend/app/core/execution_plan.py`
- `backend/app/mcp/` (no changes to tool adapters or registry)
- All frontend files
- `backend/app/main.py`

---

## Summary

| Milestone | Focus | Files Changed | Risk | Effort |
|---|---|---|---|---|
| M1 | Generic adapter architecture + CapabilityRegistry metadata + MCP wiring | 4 | Low | ~3h ✅ |

### Key Decisions

1. **No new architectural layer.** The CapabilityRegistry evolves to handle all execution types via registration-time normalization. The WorkflowEngine and ExecutionRuntime remain unchanged.

2. **Adapters are functions, not classes.** No executor interface, no inheritance hierarchy. Each adapter is a closure that wraps a different execution target into the common signature. State is captured in the closure at registration time.

3. **step_input bridges the gap.** The only difference between agent and MCP dispatch is that MCP tools need step-specific parameters. `ProjectContext.step_input` provides this without changing the callable signature.

4. **MCP gets no special treatment.** MCP tools are registered into the same registry as agents. The Planner references them by capability name. The WorkflowEngine dispatches them the same way. The only difference is `execution_type="mcp"` in metadata.

5. **Stubs for future execution types.** `rest_call` and `python_exec` are registered but return "not implemented" at runtime. When real REST/Python execution is needed, only the adapter implementation changes — the registration and dispatch are already wired.
