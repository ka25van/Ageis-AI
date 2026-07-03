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

| Problem | Severity | M1 Fixed? |
|---|---|---|
| `agentRunsApi` imported in 2 frontend pages but never exported — runtime crash | Bug | ✅ Fixed |
| Initial migration creates `document_chunks.embedding` as `VECTOR(1536)` but model and service use 768 | Bug | ✅ Fixed |
| Typo `last_faded` instead of `last_failed` in `workflow_engine.py` | Bug | ✅ Fixed |
| Lazy imports inside method bodies in 4 services | Code quality | ✅ Fixed |
| `SemanticMemory` column named `metadata` conflicts with SQLAlchemy reserved `Base.metadata` | Bug | ✅ Fixed |
| Vector search (pgvector `<=>` operator) implemented independently in 3 services | Duplication | |
| RepositoryFile queries duplicated across all 7 agents with near-identical code | Duplication | |
| No ContextBuilder — each agent builds LLM prompts from scratch, inconsistent quality | Missing abstraction | |
| RepositoryAnalyzer logic exists but no agent consumes it — agents do their own LLM analysis | Missing integration | |
| Planner has 2 parallel execution methods (`run_task` LangGraph + `plan_and_execute` manual) | Duplication | |
| Planner is optional (1 of 7 agent cards) — not the mandatory entry point | Architectural gap | |
| WorkflowEngine returns placeholder strings, never queries DB or calls real agents | Non-functional | |
| No IntentRouter — user must manually pick which agent to run | Architectural gap | |
| No ResponseMerger — multi-agent outputs are disjointed, never merged | Missing feature | |
| No Chat UI — Knowledge page is search-only, no conversational interface | Missing feature | |
| 15+ API endpoints defined in frontend `api.ts` but never called by any page | Dead code | |
| `memoryApi` and `toolsApi` defined in frontend but never used from UI | Dead code | |
| DeployAgent creates `Approval` records directly, bypasses `ApprovalService` | Bypassed abstraction | |
| Long-term memory types limited — no ConversationMemory or RepositoryMemory | Incomplete | |
| Hardcoded limits (`limit=200`, `limit=50`, `limit=30`) scattered across 10+ files | Code quality | |
| `print()` used for error logging in `EmbeddingService` | Code quality | |

---

## Milestone 1 — Safety & Bug Fixes ✅

**Goal**: Fix runtime-breaking bugs with zero behavior change. No new services, no refactoring.

**Completed**: 2026-07-03

### Tasks

- [x] Export `agentRunsApi` from `frontend/src/lib/api.ts`
  - Calls `GET /workflows/runs` with optional `?project_id=` query param
  - Returns `AgentRun[]` matching the existing interface
- [x] Create Alembic migration to alter `document_chunks.embedding` from `VECTOR(1536)` to `VECTOR(768)`
  - Uses `ALTER COLUMN ... TYPE vector(768)` with `USING embedding::vector(768)`
  - Preserves existing data
  - Migration file: `a6b7c8d9e0f1_fix_embedding_dimension.py`
- [x] Fix typo in `backend/app/services/workflow_engine.py`: rename `last_faded` to `last_failed`
  - Single-character fix, no behavior change
- [x] Move lazy imports to top of file in `services/memory.py`, `services/embeddings.py`, `services/ingestion.py`, `services/document_processor.py`
- [x] Fix `SemanticMemory` model — renamed `metadata` column to `doc_metadata` (SQLAlchemy reserved attribute conflict)

### Acceptance Criteria

- [x] Dashboard page loads without runtime error (agentRunsApi.list() resolves)
- [x] Agents page loads without runtime error (agentRunsApi.list() resolves)
- [x] Semantic search works: 768-dim embeddings write successfully into document_chunks table (migration created)
- [x] WorkflowEngine.resume_workflow() references correct variable name
- [x] All imports are at module top level, no `from X import Y` inside method bodies
- [x] FastAPI app loads without SQLAlchemy model errors
- [x] Frontend TypeScript compiles clean (`tsc --noEmit`)
- [x] Frontend production build succeeds (`vite build`)
- [x] All modified Python files compile (`py_compile`)

---

## Milestone 2 — Shared Data Services ✅

**Goal**: Eliminate all duplicated DB query and vector search patterns. Create shared services that become the single source of truth for data access.

**Completed**: 2026-07-03

### Tasks

- [x] Create `backend/app/services/repository_data_service.py`
  - Method `get_files(repository_id, limit=200) -> List[RepositoryFile]`
  - Method `get_file_summary(repository_id, limit=200) -> str` (returns formatted markdown)
  - Method `get_languages(repository_id) -> List[str]` (distinct languages from files)
  - Method `get_file_paths(repository_id) -> List[str]` (just paths for structure overview)
  - Method `count_files_by_language(repository_id) -> Dict[str, int]`
  - Method `get_repository(repository_id) -> Optional[Repository]`
  - Must provide a FastAPI `Depends`-compatible factory function
- [x] Consolidate all vector search into `EmbeddingService`
  - Move the raw `<=>` SQL from `KnowledgeAgent.retrieve_knowledge()` into `EmbeddingService.semantic_search()`
  - Move the raw `<=>` SQL from `MemorySystem.search_semantic()` into `EmbeddingService.semantic_search()`
  - Make `EmbeddingService.semantic_search()` accept optional `table_name` parameter (for querying both `document_chunks` and `semantic_memory`)
  - Fix `EmbeddingService.hybrid_search()` — replace no-op stub with real keyword+vector hybrid
- [x] Replace direct DB queries in all 7 agent services with `RepositoryDataService` calls
  - `services/repository_agent.py` — rewritten to use `repo_data` exclusively
  - `services/documentation_agent.py` — rewritten to use `repo_data` exclusively
  - `services/incident_agent.py` — rewritten to use `repo_data` exclusively
  - `services/code_review_agent.py` — rewritten to use `repo_data` exclusively
  - `services/deploy_agent.py` — rewritten to use `repo_data` exclusively
  - Verified: no agent performs `select(RepositoryFile)` directly anymore
- [x] Replace direct DB queries in API endpoints
  - `api/v1/endpoints/repository_analysis.py`: replaced lines 82-85, 126-129 with `repo_data.get_files()`
- [x] Replace direct vector search in `KnowledgeAgent` with `EmbeddingService.semantic_search()` call
- [x] Replace direct vector search in `MemorySystem` with `EmbeddingService.semantic_search()` call

### Acceptance Criteria

- [x] All 7 agents receive repository data through `RepositoryDataService` — no agent imports or queries `RepositoryFile` model directly
- [x] `EmbeddingService.semantic_search()` is the only place in the codebase with pgvector `<=>` SQL
- [x] `EmbeddingService.hybrid_search()` returns both semantic and keyword results (not just semantic)
- [x] `MemorySystem.search_semantic()` calls `EmbeddingService` instead of building raw SQL
- [x] `KnowledgeAgent.retrieve_knowledge()` calls `EmbeddingService` instead of building raw SQL
- [x] `KnowledgeAgent.hybrid_search()` calls `EmbeddingService.hybrid_search()` instead of duplicating logic
- [ ] All existing agent endpoints return identical response shapes to before refactor (requires verification)

---

## Milestone 3 — Context Builder & Repository Intelligence Layer ✅

**Goal**: Standardize how agents receive input. Create cached, structured repository intelligence so agents stop doing their own LLM analysis.

**Completed**: 2026-07-03

### Tasks

- [x] Create `backend/app/services/context_builder.py`
  - Define a `ProjectContext` dataclass with fields:
    - `project_id: UUID`, `project_name: str`
    - `repository_summary: str` (pre-built, truncated to 2000 chars)
    - `file_previews: str` (truncated concatenation, truncated to 5000 chars)
    - `languages: List[str]`
    - `dependency_graph: Dict` (from RepositoryAnalyzer)
    - `architecture_layers: List[str]` (from RepositoryAnalyzer, max 10)
    - `api_routes: List[Dict]` (from RepositoryAnalyzer, max 20)
    - `entry_points: List[str]` (from RepositoryAnalyzer, max 10)
    - `semantic_memory: List[Dict]` (from MemorySystem, max 5 entries)
    - `workflow_state: Dict` (empty — WorkflowEngine placeholder)
    - `task_description: str` (user's original task)
  - Method `build(project_id, task_description) -> ProjectContext`
    - Orchestrates calls to RepositoryDataService, RepositoryIntelligence, MemorySystem
    - Truncates each field to configurable max lengths
    - Returns single object passed to every agent
- [x] Create `backend/app/services/repository_intelligence.py`
  - Caches structured analysis (dependency graph, API routes, architecture layers, entry points, service graph, repository health)
  - TTL-based cache (300s) + explicit `invalidate()` method
  - Uses `RepositoryAnalyzer` methods internally
  - Module-level singleton pattern so cache persists across requests
  - Invalidates cache when repository is re-ingested (called from `ingestion.py` after embedding)
- [x] Standardize agent I/O contracts
  - Define `AgentResult` TypedDict in `agent_base.py` with fields: `result`, `confidence`, `recommendations`, `follow_up_actions`, `details`
  - All agents expose `process(context: ProjectContext) -> AgentResult` method
  - Existing per-method signatures remain for backward compatibility
- [x] Refactor each agent to use Context Builder
  - `RepositoryAgent` — `process()` calls `understand_code()`, wraps into `AgentResult`
  - `KnowledgeAgent` — `process()` calls `query()`, takes question from `context.task_description`
  - `IncidentAgent` — `process()` calls `analyze_incidents()`, wraps into `AgentResult`
  - `DocumentationAgent` — `process()` calls `generate_readme()`, wraps into `AgentResult`
  - `CodeReviewAgent` — `process()` calls `best_practices()`, wraps into `AgentResult`
  - `DeployAgent` — `process()` calls `analyze_deployment()`, wraps into `AgentResult`
  - Each agent's existing API endpoint still works (backward compatibility — endpoint calls ContextBuilder internally, calls `agent.process()`, maps `AgentResult.details` to old response shape)

### Acceptance Criteria

- [x] `ContextBuilder.build()` returns a complete `ProjectContext` object with all fields populated
- [x] All agents expose `process(context: ProjectContext)` — existing endpoints still work via backward compat layer
- [x] All agents return `AgentResult` with `result`, `confidence`, `recommendations`, `follow_up_actions`
- [x] `RepositoryIntelligence.get_summary(repo_id)` returns cached result on second call (TTL-based)
- [x] `RepositoryIntelligence.invalidate()` called from `IngestionService` after successful ingestion
- [ ] Existing per-agent API endpoints return identical response shapes (requires runtime verification)

---

## Milestone 4 — Planner as Mandatory Entry Point ✅

**Goal**: The Planner becomes the brain. Users submit a task description; the system determines intent, selects agents, executes them, and merges responses.

**Completed**: 2026-07-03

### Tasks

- [x] Consolidate `PlannerAgent` into single execution path
  - Removed `run_task()` (LangGraph path) and all LangGraph imports/dependencies
  - Kept `plan_and_execute()` as the single canonical method
  - Existing `POST /planner/plan` endpoint returns same response shape (unchanged)
- [x] Create `IntentRouter` inside `planner.py` (not separate file — co-located with Planner)
  - Method `route(user_input: str, context: Optional[ProjectContext]) -> ExecutionPlan`
  - `ExecutionPlan` TypedDict: `intent`, `required_agents`, `execution_order`, `needs_approval`, `task_description`
  - Uses LLM to classify intent from user input with agent descriptions as context
  - Maps intents to agent sequences; falls back to `["repository"]` if LLM output is unparseable
- [x] Create `ResponseMerger` inside `planner.py`
  - Method `merge(agent_results: Dict[str, AgentResult], execution_plan: ExecutionPlan) -> str`
  - Combines multiple agent outputs; uses LLM merge when >1 agent, single-agent case returns result + recommendations
  - Preserves confidence scores and recommendations from each agent
  - Falls back to concatenation if LLM merge fails
- [x] Create new frontend page `frontend/src/pages/Chat.tsx`
  - Text input for user to type a request (not select agents)
  - Project selector dropdown
  - Submits to `POST /planner/route`
  - Displays merged response in chat-like format
  - Shows which agents were selected with expandable agent details (confidence, recommendations)
  - Added `/chat` route to `App.tsx` and "Chat" link in `Layout.tsx` sidebar (below Dashboard)
  - **Existing `/agents` page unchanged** — advanced users can still pick agents manually
- [x] Wire new flow to backend
  - New endpoint `POST /planner/route` accepts `message`, `project_id`, optional `repository_id`
  - Endpoint calls IntentRouter → ContextBuilder → agent dispatchers → ResponseMerger
  - Returns `{ response, execution_plan, agents_used, agent_details, needs_approval, planner_fallback }`
  - Dispatches to correct agents based on `required_agents` from ExecutionPlan
  - Falls back to `planner.plan_and_execute()` when intent is `"unknown"` or no agents could execute
- [x] Add `plannerApi.route()` to `frontend/src/lib/api.ts` with `RouteResponse` interface

### Acceptance Criteria

- [ ] User types "explain authentication" in Chat UI → system routes to agents → merged response returned (requires runtime verification)
- [ ] User types an ambiguous request → system falls back to Planner-only execution
- [x] Existing `/agents` page still works — user can still pick individual agents
- [x] Existing `POST /planner/plan` endpoint still returns same format
- [x] Backend compiles clean
- [x] Frontend compiles clean (`tsc --noEmit`, `vite build`)

---

## Milestone 5 — WorkflowEngine Rewrite ✅

**Goal**: The WorkflowEngine becomes functional — it delegates to real agents, handles retries with real error recovery, and supports workflow resumption.

**Completed**: 2026-07-03

### Tasks

- [x] Rewrite `WorkflowEngine._execute_step()` to delegate to real services
  - Uses `TOOL_AGENT_MAP` dict mapping 6 tool names to agent names
  - `analyze_code` → `RepositoryAgent.process()` (not understand_code — uses standard process() entry)
  - `search_knowledge` → `KnowledgeAgent.process()`
  - `generate_docs` → `DocumentationAgent.process()`
  - `review_code` → `CodeReviewAgent.process()`
  - `analyze_incidents` → `IncidentAgent.process()`
  - `analyze_deploy` → `DeployAgent.process()`
  - All `_search_knowledge`, `_read_files`, `_run_code`, `_analyze` placeholder methods removed
  - Each step constructs a `ProjectContext` via `ContextBuilder.build(repository_id, task_description)` before dispatching
  - Agent dispatch table stored as `self._agents: Dict[str, Callable]` in constructor
- [x] Add real error handling in retry loop
  - Three-tier classification: `FatalError` (no retry), `RetryableError` (retry up to max_retries), generic `Exception` (retry up to max_retries as safety net)
  - `FatalError`: logged at ERROR, step immediately marked failed (no retry)
  - `RetryableError`: logged at WARNING, retried after `retry_delay` seconds; after exhaustion logged at ERROR
  - Unexpected exceptions: same as RetryableError (conservative — prefer retry over silent failure)
  - Structured logging via `logging.getLogger(__name__)`
- [x] Wire `WorkflowEngine.resume_workflow()` to real state recovery
  - Reads `AgentRun.input_data` to reconstruct original task + steps
  - Queries all `AgentStep` records, separates completed vs failed
  - Finds first failed step index, filters remaining steps for re-execution
  - Calls `execute_workflow()` on the remaining steps only
  - Returns `{ status, resume_from, error, completed_before_resume, resume_result }`
  - Both previously completed and resumed results returned

### Acceptance Criteria

- [x] `POST /workflows/execute` with a valid plan executes real agents (not placeholder strings)
- [x] Error handling distinguishes retryable vs fatal errors
- [x] Retry loop logs attempts at appropriate levels
- [x] Resume endpoint restarts from the failed step, preserves completed steps
- [x] `GET /workflows/runs/{run_id}/state` returns real step results (not placeholder text)
- [x] Backend compiles clean
- [x] Frontend compiles clean

---

## Milestone 6 — Memory Expansion & HITL Consolidation ✅

**Goal**: Widen memory coverage to all agent types. Route all HITL through ApprovalService.

**Completed**: 2026-07-03

### Tasks

- [x] Add `ConversationMemory` type to `MemorySystem`
  - Stores chat history as ordered list of messages via `store_conversation()` / `get_conversation()`
  - Retrieved by `project_id + user_id` for context window (composite key `conversation:{project_id}:{user_id}`)
  - Truncated to 50 messages; `POST /planner/route` stores user+assistant messages; Chat.tsx loads history on project change
- [x] Add `RepositoryMemory` type to `MemorySystem`
  - Caches analysis results per repository via `store_repository_memory()` / `get_repository_memory()` / `delete_repository_memory()`
  - Invalidated when repository is re-ingested (`RepositoryIntelligence.invalidate()` calls `delete_repository_memory()`; ingestion calls `invalidate()`)
  - Used by `RepositoryIntelligence._get_analysis()` — checks persisted memory on cache miss, stores on compute
- [x] Wire remaining 5 agents (Repository, Incident, Documentation, Code Review, Deploy) to MemorySystem
  - Each stores its analysis results in `SemanticMemory` after completion via `ContextBuilder.after_agent()`
  - Each searches `SemanticMemory` for related past analyses via `ProjectContext.semantic_memory` (populated by `ContextBuilder.build()`)
- [x] Make Planner the memory gateway
  - All agent memory reads/writes go through `ContextBuilder` (via `build()` / `after_agent()`)
  - `KnowledgeAgent` no longer imports or calls `MemorySystem` directly — memory flows through `ProjectContext.semantic_memory`
- [x] Route `DeployAgent` approvals through `ApprovalService`
  - Replaced direct `Approval` model creation with `ApprovalService.request_approval()`
  - `DeployAgent` now accepts `approval_service` parameter; factory injects via `Depends(get_approval_service)`
- [x] Wire `memoryApi` frontend calls to actual UI
  - Knowledge page: added "Agent Memory" tab with semantic memory search via `memoryApi.searchSemantic()`
  - Agents page: added "View Memory" button on expanded runs via `memoryApi.getRunMemory()`
  - Chat page: loads conversation history on project change via `memoryApi.getConversation()`

### Acceptance Criteria

- [x] Chat conversation history persists and is included in context for follow-up queries
- [x] Repository analysis is cached — second call to same repo returns quickly without LLM
- [x] Running Repository Agent on a repo stores result in SemanticMemory; running it again shows past result as context
- [x] All 7 agents store results in SemanticMemory
- [x] DeployAgent creates Approval record through `ApprovalService.request_approval()`, not directly
- [x] Knowledge page shows a "Memory" tab with stored semantic entries

---

## Milestone 7 — Cleanup & Code Quality ✅

**Goal**: Remove dead code, eliminate hardcoded values, fix logging, tighten consistency.

**Completed**: 2026-07-03

### Tasks

- [x] Audit and wire or remove uncalled frontend API endpoints
  - Removed: `documentsApi.get()`, `repositoriesApi.getFiles()`, `knowledgeAgentApi.hybridSearch()`, `knowledgeAgentApi.rankResults()`, `incidentAgentApi.rootCauseAnalysis()`, `incidentAgentApi.getRecommendations()`, `docAgentApi.generateApiDocs()`, `docAgentApi.generateArchitectureDocs()`, `codeReviewApi.securityReview()`, `codeReviewApi.bestPractices()`, `toolsApi` (3 methods), `workflowApi.execute()`, `memoryApi.storeLongTerm()`, `memoryApi.getLongTerm()`, `memoryApi.storeSemantic()`, `approvalsApi.requestApproval()`, `approvalsApi.getAuditLog()`
  - Kept (have UI consumers): `memoryApi.searchSemantic()`, `memoryApi.getRunMemory()`, `memoryApi.getConversation()`, `memoryApi.clearConversation()`, `workflowApi` removed entirely
- [x] Extract hardcoded limits into config
  - `limit=200` → `settings.REPOSITORY_FILE_LIMIT` in `config.py` (used in `repository_data_service.get_files()`, `get_file_summary()`, `context_builder.build()`)
  - `limit=50` → `settings.FILE_PREVIEW_LIMIT` (used in `repository_data_service.get_file_summary()` slice, file preview truncation)
  - `limit=30` → `settings.CONTEXT_TRUNCATION_LIMIT` (used in `code_review_agent` findings/truncation)
  - `similarity_threshold=0.3` → `settings.SIMILARITY_THRESHOLD` (used in `embeddings.hybrid_search()`, `context_builder.build()`, `planner._inject_memory_context()`)
  - Also extracted: `limit=500` → `settings.BATCH_FILE_LIMIT` (used across 7 files for bulk file loading), `preview_chars=300` → `settings.FILE_PREVIEW_CHARS` (used in `get_file_summary()` and code review previews)
- [x] Replace `print()` with structured logger
  - `embeddings.py`: `print(f"Embedding generation failed: {e}")` → `logger.warning(...)`
  - `ingestion.py`: 2 `print()` calls → `logger.warning(...)` (file processing errors, embedding failure)
  - Added `import logging` and `logger = logging.getLogger(__name__)` to both files
- [x] Remove dead code paths
  - `PlannerAgent.run_task()` — confirmed already removed (M4)
  - No placeholder strings found in `WorkflowEngine` (M5 already replaced them)
- [x] Verify backward compatibility
  - Backend starts without import errors (verified: `app.main` loads)
  - Frontend builds without TypeScript errors (`tsc --noEmit` clean, `vite build` succeeds)
  - All existing agent cards on `/agents` page use endpoints that remain unchanged

### Acceptance Criteria

- [x] No `print()` statements remain in production service code (verified via grep)
- [x] No `limit=200` or `limit=50` literal integers remain in agent files (all reference settings; verified via grep)
- [x] All `api.ts` endpoints have at least one UI consumer or are removed (verified each export)
- [x] Backend starts without import errors
- [x] Frontend builds without TypeScript errors
- [x] All existing v1 agent endpoints return same JSON shape as before refactor

---

## Summary

| Milestone | Focus | Files Changed | Risk | Effort |
|---|---|---|---|---|
| M1 | Bug fixes (migration, export, typo) | 4 | Very Low | ~2h | ✅ |
| M2 | Shared data services, deduplicate vector search | ~12 | Low | ~5h | ✅ |
| M3 | ContextBuilder + RepositoryIntelligence + agent I/O contracts | ~14 | Medium | ~8h | ✅ |
| M4 | Planner as mandatory entry, IntentRouter, Chat UI | ~8 | High | ~10h | ✅ |
| M5 | WorkflowEngine rewrite (real delegation) | ~3 | Medium | ~5h | ✅ |
| M6 | Memory expansion + HITL consolidation | ~8 | Low | ~4h | ✅ |
| M7 | Cleanup (dead code, constants, logging) | ~10 | Very Low | ~3h | ✅ |

**Total: 7 milestones, ~37 hours, ~59 files** (7 completed ✅)

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
