# Aegis AI v2 — Architecture Refactor

## Purpose

This document contains only the remaining work required to migrate from the current v1 implementation to the target architecture described in `task_v1.md`.

Do NOT modify `TASK.md`.

Do NOT add random features.

Do NOT generate placeholder implementations.

Do NOT remove any existing functionality.

Maintain backward compatibility at every milestone.

---

## Current State Summary

### What already works (keep unchanged)

| Component | Status |
|---|---|
| LLMService (all agents call it correctly) | ✅ Keep |
| MCP tool adapters (GitHub, Filesystem, Docker, AWS) — self-register on import | ✅ Keep |
| ToolRegistry + ToolInterface — single MCP dispatch point | ✅ Keep |
| EmbeddingService.generate_embeddings() | ✅ Keep |
| IngestionService (repository clone, file parsing, chunking) | ✅ Keep |
| DocumentProcessor (PDF, Markdown, text loading) | ✅ Keep |
| Auth system (JWT, refresh tokens, API keys) | ✅ Keep |
| MemorySystem (short-term, long-term, semantic CRUD) | ✅ Keep |
| All existing API endpoint signatures | ✅ Keep for backward compat |
| Frontend page structure (Dashboard, Projects, Repositories, Settings) | ✅ Keep |

### What needs to change

| Problem | Severity |
|---|---|
| `agentRunsApi` imported in 2 frontend pages but never exported — runtime crash | Bug |
| Initial migration creates `document_chunks.embedding` as `VECTOR(1536)` but model and service use 768 | Bug |
| Typo `last_faded` instead of `last_failed` in `workflow_engine.py` | Bug |
| Vector search (pgvector `<=>` operator) implemented independently in 3 services | Duplication |
| RepositoryFile queries duplicated across all 7 agents with near-identical code | Duplication |
| No ContextBuilder — each agent builds LLM prompts from scratch, inconsistent quality | Missing abstraction |
| RepositoryAnalyzer logic exists but no agent consumes it — agents do their own LLM analysis | Missing integration |
| Planner has 2 parallel execution methods (`run_task` LangGraph + `plan_and_execute` manual) | Duplication |
| Planner is optional (1 of 7 agent cards) — not the mandatory entry point | Architectural gap |
| WorkflowEngine returns placeholder strings, never queries DB or calls real agents | Non-functional |
| No IntentRouter — user must manually pick which agent to run | Architectural gap |
| No ResponseMerger — multi-agent outputs are disjointed, never merged | Missing feature |
| No Chat UI — Knowledge page is search-only, no conversational interface | Missing feature |
| 15+ API endpoints defined in frontend `api.ts` but never called by any page | Dead code |
| `memoryApi` and `toolsApi` defined in frontend but never used from UI | Dead code |
| DeployAgent creates `Approval` records directly, bypasses `ApprovalService` | Bypassed abstraction |
| Long-term memory types limited — no ConversationMemory or RepositoryMemory | Incomplete |
| Hardcoded limits (`limit=200`, `limit=50`, `limit=30`) scattered across 10+ files | Code quality |
| `print()` used for error logging in `EmbeddingService` | Code quality |
| Lazy imports inside method bodies in 4 services | Code quality |

---

## Milestone 1 — Safety & Bug Fixes

**Goal**: Fix runtime-breaking bugs with zero behavior change. No new services, no refactoring.

### Tasks

- [ ] Export `agentRunsApi` from `frontend/src/lib/api.ts`
  - Must call `GET /workflows/runs` with optional `?project_id=` query param
  - Must return `AgentRun[]` matching the existing interface
- [ ] Create Alembic migration to alter `document_chunks.embedding` from `VECTOR(1536)` to `VECTOR(768)`
  - Must use `ALTER COLUMN ... TYPE vector(768)` with `USING embedding::vector(768)`
  - Must not drop existing data
- [ ] Fix typo in `backend/app/services/workflow_engine.py`: rename `last_faded` to `last_failed`
  - Single-character fix, no behavior change
- [ ] Move lazy imports to top of file in `services/memory.py`, `services/embeddings.py`, `services/ingestion.py`, `services/document_processor.py`

### Acceptance Criteria

- Dashboard page loads without runtime error (agentRunsApi.list() resolves)
- Agents page loads without runtime error (agentRunsApi.list() resolves)
- Semantic search works: 768-dim embeddings write successfully into document_chunks table
- WorkflowEngine.resume_workflow() references correct variable name
- All imports are at module top level, no `from X import Y` inside method bodies

---

## Milestone 2 — Shared Data Services

**Goal**: Eliminate all duplicated DB query and vector search patterns. Create shared services that become the single source of truth for data access.

### Tasks

- [ ] Create `backend/app/services/repository_data_service.py`
  - Method `get_files(repository_id, limit=200) -> List[RepositoryFile]`
  - Method `get_file_summary(repository_id, limit=200) -> str` (returns formatted markdown)
  - Method `get_languages(repository_id) -> List[str]` (distinct languages from files)
  - Method `get_file_paths(repository_id) -> List[str]` (just paths for structure overview)
  - Method `count_files_by_language(repository_id) -> Dict[str, int]`
  - Must provide a FastAPI `Depends`-compatible factory function
- [ ] Consolidate all vector search into `EmbeddingService`
  - Move the raw `<=>` SQL from `KnowledgeAgent.retrieve_knowledge()` into `EmbeddingService.semantic_search()`
  - Move the raw `<=>` SQL from `MemorySystem.search_semantic()` into `EmbeddingService.semantic_search()`
  - Make `EmbeddingService.semantic_search()` accept optional `table_name` parameter (for querying both `document_chunks` and `semantic_memory`)
  - Fix `EmbeddingService.hybrid_search()` — replace no-op stub with real keyword+vector hybrid
- [ ] Replace direct DB queries in all 7 agent services with `RepositoryDataService` calls
  - `services/repository_agent.py`: lines 29-32, 41-43, 86-89
  - `services/documentation_agent.py`: lines 27-30, 32-35, 64-67, 90-93
  - `services/incident_agent.py`: lines 27-30, 92-95
  - `services/code_review_agent.py`: lines 20-23, 48-51, 95-98
  - `services/deploy_agent.py`: lines 28-31
  - Verify no agent performs `select(RepositoryFile)` directly anymore
- [ ] Replace direct DB queries in API endpoints
  - `api/v1/endpoints/repository_analysis.py`: lines 82-85, 126-129
- [ ] Replace direct vector search in `KnowledgeAgent` with `EmbeddingService` call
- [ ] Replace direct vector search in `MemorySystem` with `EmbeddingService` call

### Acceptance Criteria

- All 7 agents receive repository data through `RepositoryDataService` — no agent imports or queries `RepositoryFile` model directly
- `EmbeddingService.semantic_search()` is the only place in the codebase with pgvector `<=>` SQL
- `EmbeddingService.hybrid_search()` returns both semantic and keyword results (not just semantic)
- `MemorySystem.search_semantic()` calls `EmbeddingService` instead of building raw SQL
- `KnowledgeAgent.retrieve_knowledge()` calls `EmbeddingService` instead of building raw SQL
- `KnowledgeAgent.hybrid_search()` calls `EmbeddingService.hybrid_search()` instead of duplicating logic
- All existing agent endpoints return identical response shapes to before refactor

---

## Milestone 3 — Context Builder & Repository Intelligence Layer

**Goal**: Standardize how agents receive input. Create cached, structured repository intelligence so agents stop doing their own LLM analysis.

### Tasks

- [ ] Create `backend/app/services/context_builder.py`
  - Define a `ProjectContext` dataclass or TypedDict with fields:
    - `project_id: UUID`
    - `project_name: str`
    - `repository_summary: str` (pre-built)
    - `file_previews: str` (truncated concatenation)
    - `languages: List[str]`
    - `dependency_graph: Dict` (from RepositoryAnalyzer)
    - `architecture_layers: List[str]` (from RepositoryAnalyzer)
    - `api_routes: List[str]` (from RepositoryAnalyzer)
    - `entry_points: List[str]` (from RepositoryAnalyzer)
    - `semantic_memory: List[Dict]` (from MemorySystem)
    - `workflow_state: Dict` (from WorkflowEngine)
  - Method `build(project_id, task_description) -> ProjectContext`
    - Orchestrates calls to RepositoryDataService, RepositoryIntelligence, MemorySystem
    - Truncates each field to configurable max lengths
    - Returns single object passed to every agent
- [ ] Create `backend/app/services/repository_intelligence.py`
  - Persists structured analysis (dependency graph, API routes, architecture layers, entry points, service graph, repository health)
  - Caches results so agents don't re-analyze on every call
  - Exposes `get_summary(repo_id)`, `get_dependency_graph(repo_id)`, `get_architecture(repo_id)`, `get_api_routes(repo_id)`, `get_entry_points(repo_id)`
  - Uses `RepositoryAnalyzer` methods internally
  - Invalidates cache when repository is re-ingested
- [ ] Standardize agent I/O contracts
  - Define `AgentResult` TypedDict with fields: `result: str`, `confidence: float`, `recommendations: List[str]`, `follow_up_actions: List[str]`
  - All agents return `AgentResult` instead of raw LLM text
  - All agents accept `ProjectContext` as their single input (replace individual parameters)
- [ ] Refactor each agent to use Context Builder
  - `RepositoryAgent` receives `ProjectContext`, returns `AgentResult`
  - `KnowledgeAgent` receives `ProjectContext`, returns `AgentResult`
  - `IncidentAgent` receives `ProjectContext`, returns `AgentResult`
  - `DocumentationAgent` receives `ProjectContext`, returns `AgentResult`
  - `CodeReviewAgent` receives `ProjectContext`, returns `AgentResult`
  - `DeployAgent` receives `ProjectContext`, returns `AgentResult`
  - Each agent's existing API endpoint still works (backward compatibility — endpoint calls ContextBuilder internally and passes to agent)

### Acceptance Criteria

- `ContextBuilder.build()` returns a complete `ProjectContext` object with all fields populated
- All agents accept `ProjectContext` as input — no agent calls DB, vector search, or memory directly
- All agents return `AgentResult` with `result`, `confidence`, `recommendations`, `follow_up_actions`
- `RepositoryIntelligence.get_summary(repo_id)` returns cached result on second call (no re-analysis)
- Existing per-agent API endpoints return identical response shapes (backward compatibility layer wraps `AgentResult` into old format)

---

## Milestone 4 — Planner as Mandatory Entry Point

**Goal**: The Planner becomes the brain. Users submit a task description; the system determines intent, selects agents, executes them, and merges responses.

### Tasks

- [ ] Consolidate `PlannerAgent` into single execution path
  - Remove `run_task()` (LangGraph path) or merge into `plan_and_execute()`
  - Keep one canonical method with clear input/output contract
  - Existing `POST /planner/plan` endpoint must return same response shape
- [ ] Create `backend/app/services/intent_router.py`
  - Method `route(user_input: str, project_context: ProjectContext) -> ExecutionPlan`
  - `ExecutionPlan` TypedDict: `intent: str`, `required_agents: List[str]`, `execution_order: List[str]`, `needs_approval: bool`
  - Uses LLM to classify intent from user input
  - Maps intents to agent sequences (e.g. "explain auth" → [RepositoryAgent, KnowledgeAgent])
  - Falls back to standalone planner task if intent is unclear
- [ ] Create `backend/app/services/response_merger.py`
  - Method `merge(agent_results: Dict[str, AgentResult], execution_plan: ExecutionPlan) -> str`
  - Combines multiple agent outputs into a single coherent response
  - Preserves confidence scores and recommendations from each agent
  - Handles conflicting recommendations by surfacing both with their confidence levels
- [ ] Create new frontend page `frontend/src/pages/Chat.tsx`
  - Text input for user to type a request (not select agents)
  - Submits to `POST /planner/plan` (or new intent endpoint)
  - Displays merged response in chat-like format
  - Shows which agents were selected and their individual contributions (expandable)
  - Add `/chat` route to `App.tsx` and link in `Layout.tsx` sidebar
  - **Keep existing `/agents` page unchanged** — advanced users can still pick agents manually
- [ ] Wire new flow to backend
  - New endpoint `POST /planner/route` or modify `POST /planner/plan` to accept raw text + project_id
  - Endpoint calls IntentRouter, then Planner, then ResponseMerger
  - Returns merged response + execution plan metadata

### Acceptance Criteria

- User types "explain authentication" in Chat UI → system routes to Repository Agent + Knowledge Agent → merged response returned
- User types "review deployment" → system routes to Repository Agent + Deploy Agent → merged response returned
- User types "investigate build failure" → system routes to Incident Agent + Knowledge Agent + Repository Agent → merged response returned
- User types an ambiguous request → system falls back to Planner-only execution
- Existing `/agents` page still works — user can still pick individual agents
- Existing `POST /planner/plan` endpoint still returns same format

---

## Milestone 5 — WorkflowEngine Rewrite

**Goal**: The WorkflowEngine becomes functional — it delegates to real agents, handles retries with real error recovery, and supports workflow resumption.

### Tasks

- [ ] Rewrite `WorkflowEngine._execute_step()` to delegate to real services
  - `tool == "search_knowledge"` → call `KnowledgeAgent.query()` via shared instance
  - `tool == "analyze_code"` → call `RepositoryAgent.understand()` via shared instance
  - `tool == "generate_docs"` → call `DocumentationAgent` methods
  - `tool == "review_code"` → call `CodeReviewAgent` methods
  - `tool == "analyze_incidents"` → call `IncidentAgent` methods
  - `tool == "analyze_deploy"` → call `DeployAgent` methods
  - Remove all placeholder string return values
- [ ] Add real error handling in retry loop
  - Distinguish between retryable errors (LLM timeout, DB transient) and fatal errors (invalid input)
  - Only retry on retryable errors, up to `max_retries`
  - Log retry attempts with structured logging
- [ ] Wire `WorkflowEngine.resume_workflow()` to real state recovery
  - On resume, restore `AgentState` from last completed `AgentStep`
  - Re-execute only from the first failed step
  - Return both resumed results and previously completed results

### Acceptance Criteria

- `POST /workflows/execute` with a valid plan executes real agents (not placeholder strings)
- If LLM times out on step 2 of 4, retry happens, step eventually completes or gives fatal error
- Resume endpoint restarts from the failed step, preserves completed steps
- `GET /workflows/runs/{run_id}/state` returns real step results (not placeholder text)

---

## Milestone 6 — Memory Expansion & HITL Consolidation

**Goal**: Widen memory coverage to all agent types. Route all HITL through ApprovalService.

### Tasks

- [ ] Add `ConversationMemory` type to `MemorySystem`
  - Stores chat history as ordered list of messages
  - Retrieved by `project_id + user_id` for context window
  - Automatically summarized/truncated when exceeding token budget
- [ ] Add `RepositoryMemory` type to `MemorySystem`
  - Caches analysis results per repository (architecture, deps, API routes)
  - Invalidated when repository is re-ingested
  - Used by `RepositoryIntelligence` to avoid re-analysis
- [ ] Wire remaining 5 agents (Repository, Incident, Documentation, Code Review, Deploy) to MemorySystem
  - Each stores its analysis results in `SemanticMemory` after completion
  - Each searches `SemanticMemory` for related past analyses before calling LLM
  - Follows same pattern already used by PlannerAgent and KnowledgeAgent
- [ ] Make Planner the memory gateway
  - All agent memory reads/writes go through Planner or ContextBuilder
  - Agents do not import or call `MemorySystem` directly
- [ ] Route `DeployAgent` approvals through `ApprovalService`
  - Replace direct `Approval` model creation with `ApprovalService.request_approval()`
  - DeployAgent endpoint still works identically from frontend perspective
- [ ] Wire `memoryApi` frontend calls to actual UI
  - Add semantic memory viewer to Knowledge page (show stored memory entries)
  - Add run memory viewer to Agent Runs timeline
  - Existing `memoryApi` exports remain, add UI consumers

### Acceptance Criteria

- Chat conversation history persists and is included in context for follow-up queries
- Repository analysis is cached — second call to same repo returns quickly without LLM
- Running Repository Agent on a repo stores result in SemanticMemory; running it again shows past result as context
- All 7 agents store results in SemanticMemory
- DeployAgent creates Approval record through `ApprovalService.request_approval()`, not directly
- Knowledge page shows a "Memory" tab with stored semantic entries

---

## Milestone 7 — Cleanup & Code Quality

**Goal**: Remove dead code, eliminate hardcoded values, fix logging, tighten consistency.

### Tasks

- [ ] Audit and wire or remove uncalled frontend API endpoints
  - `documentsApi.get()` — wire to doc detail view or remove
  - `repositoriesApi.getFiles()` — wire to Repository Explorer or remove
  - `knowledgeAgentApi.hybridSearch()` — merge into search UI as toggle or remove
  - `knowledgeAgentApi.rankResults()` — merge into search UI or remove
  - `incidentAgentApi.rootCauseAnalysis()` — wire to incident detail or remove
  - `incidentAgentApi.getRecommendations()` — wire to incident detail or remove
  - `docAgentApi.generateApiDocs()` — add UI button for each agent card or remove
  - `docAgentApi.generateArchitectureDocs()` — add UI button for each agent card or remove
  - `codeReviewApi.securityReview()` — add UI button for each agent card or remove
  - `codeReviewApi.bestPractices()` — add UI button for each agent card or remove
  - `memoryApi` — wire to Knowledge page or remove
  - `toolsApi` — wire to Settings or admin page or remove
  - `workflowApi` — wire to Agent Runs or remove
- [ ] Extract hardcoded limits into config
  - `limit=200` (file queries) → settings.REPOSITORY_FILE_LIMIT
  - `limit=50` (file previews) → settings.FILE_PREVIEW_LIMIT
  - `limit=30` (truncation) → settings.CONTEXT_TRUNCATION_LIMIT
  - `similarity_threshold=0.3` → settings.SIMILARITY_THRESHOLD
- [ ] Replace `print()` in `EmbeddingService` with structured logger call
- [ ] Remove dead code paths
  - `PlannerAgent.run_task()` if consolidated in M4
  - Placeholder strings in `WorkflowEngine` (replaced in M5)
- [ ] Verify backward compatibility
  - Every existing API endpoint returns identical response shape (field names, types)
  - Frontend pages load without new errors
  - All existing agent cards on `/agents` page work identically

### Acceptance Criteria

- No `print()` statements remain in production service code
- No `limit=200` or `limit=50` literal integers remain in agent files (all reference settings)
- All `api.ts` endpoints have at least one UI consumer or are removed
- Backend starts without import errors
- Frontend builds without TypeScript errors
- All existing v1 agent endpoints return same JSON shape as before refactor

---

## Summary

| Milestone | Focus | Files Changed | Risk | Effort |
|---|---|---|---|---|
| M1 | Bug fixes (migration, export, typo) | 4 | Very Low | ~2h |
| M2 | Shared data services, deduplicate vector search | ~12 | Low | ~5h |
| M3 | ContextBuilder + RepositoryIntelligence + agent I/O contracts | ~14 | Medium | ~8h |
| M4 | Planner as mandatory entry, IntentRouter, Chat UI | ~8 | High | ~10h |
| M5 | WorkflowEngine rewrite (real delegation) | ~3 | Medium | ~5h |
| M6 | Memory expansion + HITL consolidation | ~8 | Low | ~4h |
| M7 | Cleanup (dead code, constants, logging) | ~10 | Very Low | ~3h |

**Total: 7 milestones, ~37 hours, ~59 files**

### Ordering Rules

1. M1 must be first (fixes runtime crashes)
2. M2 must precede M3 (shared services are prerequisite for ContextBuilder)
3. M3 must precede M4 (ContextBuilder is prerequisite for IntentRouter)
4. M5 can start after M2 (needs shared services, doesn't need ContextBuilder)
5. M6 can start after M3 (needs ContextBuilder for memory gateway pattern)
6. M7 must be last (verifies everything still works after all changes)

Safe parallel tracks:
- M2 + M5 (no dependency between them)
- M5 + M6 (no dependency after M3 complete)
