# Aegis AI — Agent Architecture

## Agent Definitions

All agents are defined in `backend/app/services/`. Each agent:
- Reads real repository/document data from the database
- Calls an LLM (Ollama or OpenAI) via LangChain for analysis
- Returns structured results to the frontend

### 1. Repository Agent (`repository_agent.py`)

**Endpoint**: `GET /repo-agent/{id}/understand`

Sends file listings, language stats, and content previews to the LLM. Returns architecture analysis, tech stack, design patterns, and recommendations.

### 2. Knowledge Agent (`knowledge_agent.py`)

**Endpoints**: `POST /knowledge/search`, `POST /knowledge/hybrid`

Performs hybrid search (pgvector cosine similarity + keyword ILIKE) across `DocumentChunk` embeddings. Also supports generative Q&A via the `query()` method.

### 3. Incident Agent (`incident_agent.py`)

**Endpoint**: `POST /incidents/analyze`

Scans `RepositoryFile` content for error keywords, sends findings to LLM for root cause analysis and remediation recommendations.

### 4. Documentation Agent (`documentation_agent.py`)

**Endpoints**: `POST /docs/readme`, `POST /docs/api`, `POST /docs/architecture`

Sends file structure and content previews to LLM. Generates README, API docs, and architecture documentation in markdown.

### 5. Code Review Agent (`code_review_agent.py`)

**Endpoints**: `POST /code-review/pr`, `POST /code-review/security`, `POST /code-review/best-practices`

Sends code previews to LLM. Identifies security vulnerabilities, code quality issues, and best practice gaps.

### 6. Deploy Agent (`deploy_agent.py`)

**Endpoint**: `POST /deploy/analyze`

Scans repository for Dockerfiles, docker-compose, CI workflows, nginx configs, and infra scripts. Sends them to LLM for deployment analysis and infrastructure recommendations.

### 7. Planner Agent (`planner.py`)

**Endpoint**: `POST /planner/plan`

LangGraph-based state machine. Accepts a task description, uses LLM for task decomposition, creates `AgentRun` + `AgentStep` records, and executes steps sequentially.

**Integrations:**
- **MCP Tools**: If a step's `tool` matches a registered MCP tool (GitHub, Filesystem, Docker, AWS), the planner dispatches execution to that tool instead of the LLM. Falls back to LLM if no MCP tool matches.
- **Memory System**: Before analyzing, the planner searches `SemanticMemory` for past tasks with similar embeddings. Results are injected into the LLM prompt as context. After completion, the task and results are stored in `SemanticMemory` for future runs.
- **AgentRun/AgentStep**: Creates database records for audit trail and approval integration.

### 8. Knowledge Agent — Memory Integration

The `KnowledgeAgent.query()` method now:
- Searches `SemanticMemory` for past Q&A pairs on similar topics before calling the LLM
- Includes matched past Q&A as additional context in the prompt
- Stores each new Q&A pair into `SemanticMemory` after generation

## MCP Tool System

Defined in `backend/app/mcp/`. Registered at app startup via imports in `main.py`.

| Adapter | File | Tools |
|---------|------|-------|
| GitHub | `github.py` | clone_repository, create_branch, create_pr |
| Filesystem | `filesystem.py` | read_file, write_file, search_files, list_directory |
| Docker | `docker.py` | build_image, run_container, stop_container, list_containers |
| AWS | `aws.py` | s3_list_buckets, s3_upload_file, ec2_list_instances, ecs_list_clusters |

**Endpoints**: `GET /tools`, `POST /tools/{name}/execute`, `GET /tools/{name}`

Tools are registered in the global `ToolRegistry` (`registry.py`) and dispatched by the Planner agent and the `/tools` API endpoint.

## Memory System

Defined in `backend/app/services/memory.py`. Three-tier memory:

| Tier | Storage | Purpose |
|------|---------|---------|
| Short-term | `AgentStep` records (DB) | Current execution context per run |
| Long-term | `LongTermMemory` table (DB) | Persistent key-value across sessions (TTL-based) |
| Semantic | `SemanticMemory` table (pgvector) | Vector-embedded text for similarity search |

**Endpoints**: `POST /memory/short-term/{run_id}`, `GET /memory/short-term/{run_id}/{key}`, `POST /memory/long-term`, `GET /memory/long-term/{key}`, `POST /memory/semantic`, `POST /memory/search`, `GET /memory/runs/{run_id}/summary`

**Integration points:**
- `PlannerAgent`: Injects past semantic memory context before task analysis, stores results after completion
- `KnowledgeAgent`: Searches semantic memory for past similar Q&A during `query()`
- `DeployAgent`: Can store/retrieve deployment analysis results

## LLM Integration

All agents use `LLMService` (`backend/app/services/llm_service.py`), which supports:

- **Ollama** (default): `ChatOllama` via `langchain-ollama`
- **OpenAI**: `ChatOpenAI` via `langchain-openai`

Provider is configured via `LLM_PROVIDER` in `.env`.

## Adding a New Agent

1. Create `backend/app/services/your_agent.py` with a class + factory function
2. Create `backend/app/api/v1/endpoints/your_agent.py` with routes
3. Register the router in `backend/app/api/v1/router.py`
4. Add the agent card in `frontend/src/pages/Agents.tsx`
5. Add API calls in `frontend/src/lib/api.ts`
6. If the agent should use memory, inject `MemorySystem` via `Depends(get_memory_system)`
7. If the agent should use MCP tools, import and dispatch via the global `registry`
