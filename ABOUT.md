# Aegis AI — Full Application Overview

An open-source Agentic AI Engineering & AIOps Platform. Aegis AI ingests code repositories and documents, analyzes them via LLM-powered agents, supports conversational task routing, human-in-the-loop approvals, a three-tier memory system, and AIOps alert ingestion with automated LLM root-cause analysis — all running locally via Docker.

---

## 1. Architecture Overview

```
                         ┌─────────────┐
                         │   Browser    │
                         │  :80 (prod)  │
                         │ :5173 (dev)  │
                         └──────┬──────┘
                                │ HTTP
                                ▼
                     ┌──────────────────┐
                     │  Nginx (frontend) │
                     │  Serves SPA      │
                     │  /api/v1 -> back │
                     └────────┬─────────┘
                              │
               ┌──────────────┼──────────────┐
               │              │              │
               ▼              ▼              ▼
       ┌────────────┐ ┌──────────┐ ┌──────────────┐
       │  Backend   │ │  Redis   │ │   Postgres   │
       │  :8000     │ │  :6379   │ │   :5432      │
       │  FastAPI   │ │  Cache   │ │   pgvector   │
       └─────┬──────┘ └──────────┘ └──────────────┘
             │
             ▼
       ┌──────────────┐
       │   Ollama     │  (host machine, not containerized)
       │  :11434      │
       │  llama3.2    │
       │  nomic-embed │
       └──────────────┘

┌─────────────────┐
│  Prometheus      │  Docker container, scrapes backend every 15s
│  :9090           │  via GET /api/v1/observability/metrics
│  Alertmanager →  │  POSTs webhook to /api/v1/alerts/webhook
└─────────────────┘
```

5 Docker containers: postgres, redis, backend, frontend, prometheus.  
Ollama runs on the host machine (not containerized) — backend connects via `host.docker.internal:11434`.

---

## 2. Backend (FastAPI + Python 3.11)

### 2.1 Tech Stack
- **Framework**: FastAPI (async), Uvicorn (single worker) — `backend/app/main.py:103`
- **ORM**: SQLAlchemy 2.0 (async), Alembic migrations — `backend/app/db/session.py:6`
- **Database**: PostgreSQL 16 + pgvector extension — `backend/app/db/session.py`
- **Cache**: Redis 7 (AOF persistence) — `backend/app/services/redis_client.py`
- **LLM Integration**: LangChain `ChatOllama` / `ChatOpenAI` — `backend/app/services/llm_service.py:27`
- **Auth**: JWT access+refresh tokens (python-jose), Argon2 hashing — `backend/app/api/v1/endpoints/auth.py`
- **Vector Search**: pgvector IVFFlat index, 768-dim embeddings — `backend/app/services/embeddings.py:23`
- **Structured Logging**: structlog — `backend/app/core/logging.py`
- **Observability**: prometheus_client — `backend/app/services/observability.py:7`
- **Background Tasks**: asyncio.create_task — `backend/app/api/v1/endpoints/alerts.py:167`

### 2.2 Key Files by Layer

| Layer | File | Purpose |
|-------|------|---------|
| **Entrypoint** | `backend/app/main.py` | App factory, middleware, imports MCP modules, router registration |
| **Config** | `backend/app/core/config.py` | Pydantic Settings — reads `.env`, all defaults |
| **DI** | `backend/app/core/di.py` | FastAPI Depends helpers for DB session |
| **DB Session** | `backend/app/db/session.py` | `create_async_engine` with `pool_pre_ping=True, pool_recycle=3600` |
| **DB Base** | `backend/app/db/base.py` | SQLAlchemy declarative Base |
| **Migrations** | `backend/app/alembic/` | Alembic migration scripts |
| **Middleware** | `backend/app/main.py:74` | `@app.middleware("http")` — logs request duration, no metric recording |
| **Models** | `backend/app/models/` | SQLAlchemy ORM models (user, project, repository, document, agent, memory) |
| **Endpoints** | `backend/app/api/v1/endpoints/` | 68+ API routes across routers |
| **Router index** | `backend/app/api/v1/router.py` | Aggregates all sub-routers |
| **Services** | `backend/app/services/` | Business logic, agents, LLM, observability, memory |
| **MCP Tools** | `backend/app/mcp/` | GitHub, Filesystem, Docker, AWS tool adapters |
| **Execution** | `backend/app/services/workflow_engine.py` | DAG orchestration, step dispatch |
| **Planning** | `backend/app/services/planner.py` | Task decomposition, IntentRouter |

### 2.3 API Endpoints (68+ under `/api/v1`)

All routers are registered in `backend/app/api/v1/router.py`.

#### Health (`/health`)
| Method | Path | File | Purpose |
|--------|------|------|---------|
| GET | /health | `endpoints/health.py:13` | Returns `{"status":"ok"}` — Docker healthcheck target |
| GET | /health/db | `endpoints/health.py:19` | Tests async DB connectivity |
| GET | /health/redis | `endpoints/health.py:30` | Tests Redis ping |

#### Auth (`/auth`)
| Method | Path | File | Purpose |
|--------|------|------|---------|
| POST | /auth/register | `endpoints/auth.py:98` | Argon2-hashed password, returns JWT pair |
| POST | /auth/login | `endpoints/auth.py:134` | Email + password verification |
| POST | /auth/refresh | `endpoints/auth.py:173` | 7-day refresh token → new access+refresh pair |
| GET | /auth/me | `endpoints/auth.py:192` | Current user profile from token |
| PATCH | /auth/me | `endpoints/auth.py:219` | Update full_name |
| POST | /auth/change-password | `endpoints/auth.py:240` | Old password verified, new password hashed |

#### Projects (`/projects`)
| Method | Path | File | Purpose |
|--------|------|------|---------|
| POST | /projects | `endpoints/projects.py:25` | Create project (name, description) → DB insert |
| GET | /projects | `endpoints/projects.py:47` | List all projects for current user |
| GET | /projects/{id} | `endpoints/projects.py:56` | Single project with settings |
| PATCH | /projects/{id} | `endpoints/projects.py:72` | Update name/description/settings |
| DELETE | /projects/{id} | `endpoints/projects.py:84` | Cascade delete — repos, docs, runs, memory |

#### Repositories (`/repositories`)
| Method | Path | File | Purpose |
|--------|------|------|---------|
| POST | /repositories | `endpoints/repositories.py:27` | Register repo url/branch → DB insert, async ingest |
| GET | /repositories | `endpoints/repositories.py:45` | List all for project |
| GET | /repositories/{id} | `endpoints/repositories.py:54` | Single repo details |
| POST | /repositories/{id}/ingest | `endpoints/repositories.py:63` | Clones repo, reads files, stores `RepositoryFile` rows |
| GET | /repositories/{id}/files | `endpoints/repositories.py:86` | Paginated file list + content |
| DELETE | /repositories/{id} | `endpoints/repositories.py:105` | Remove repo and all files |

#### Documents (`/documents`)
| Method | Path | File | Purpose |
|--------|------|------|---------|
| POST | /documents/upload | `endpoints/documents.py:34` | PDF/MD/TXT upload → parse + chunk |
| POST | /documents/text | `endpoints/documents.py:89` | Create from raw text |
| GET | /documents | `endpoints/documents.py:107` | List with pagination |
| GET | /documents/{id} | `endpoints/documents.py:116` | Document + raw content |
| GET | /documents/{id}/chunks | `endpoints/documents.py:126` | Chunks with embeddings |
| DELETE | /documents/{id} | `endpoints/documents.py:143` | Cascade delete chunks |

#### Embeddings (`/embeddings`)
| Method | Path | File | Purpose |
|--------|------|------|---------|
| POST | /embeddings/documents/{id}/generate | `endpoints/embeddings.py:25` | Calls Ollama nomic-embed-text, stores vectors in `document_chunks.embedding` |
| POST | /embeddings/repositories/{id}/generate | `endpoints/embeddings.py:52` | Embeds repo file contents |
| POST | /embeddings/search | `endpoints/embeddings.py:76` | Cosine similarity via pgvector `<=>` operator, returns top-k |
| POST | /embeddings/hybrid-search | `endpoints/embeddings.py:96` | Combines cosine similarity + ILIKE keyword match, weighted rank |

#### Planner (`/planner`)
| Method | Path | File | Purpose |
|--------|------|------|---------|
| POST | /planner/plan | `endpoints/planner.py:91` | Old path: `PlannerAgent.plan_and_execute()` — LLM decomposes → LLM executes per step |
| POST | /planner/route | `endpoints/planner.py:127` | New path: `IntentRouter` → `ExecutionPlan` → `PlanValidator` → `WorkflowEngine` — DAG-based |
| POST | /planner/resume/{run_id} | `endpoints/planner.py:172` | Resume after HITL approval — loads run + pending steps |
| GET | /planner/runs/{run_id} | `endpoints/planner.py:199` | Run status + input/output |
| GET | /planner/runs/{run_id}/steps | `endpoints/planner.py:210` | All steps with results |

#### Memory (`/memory`)
| Method | Path | File | Purpose |
|--------|------|------|---------|
| POST | /memory/short-term/{run_id} | `endpoints/memory.py:27` | Store key-value in AgentStep table |
| GET | /memory/short-term/{run_id}/{key} | `endpoints/memory.py:40` | Retrieve by run_id + key |
| POST | /memory/long-term | `endpoints/memory.py:54` | Key-value with TTL in LongTermMemory |
| GET | /memory/long-term/{key} | `endpoints/memory.py:67` | Retrieve by key |
| POST | /memory/semantic | `endpoints/memory.py:81` | Embed text + store in SemanticMemory |
| POST | /memory/search | `endpoints/memory.py:94` | Cosine similarity search across SemanticMemory |
| GET | /memory/runs/{run_id}/summary | `endpoints/memory.py:107` | Aggregates steps + memory for a run |

#### Alerts (`/alerts`)
| Method | Path | File | Purpose |
|--------|------|------|---------|
| POST | /alerts/webhook | `endpoints/alerts.py:102` | Prometheus Alertmanager receiver — stores alert in SemanticMemory, fires background LLM analysis |
| GET | /alerts/history | `endpoints/alerts.py:166` | Recent alert entries from SemanticMemory |
| GET | /alerts/stats | `endpoints/alerts.py:180` | Firing/resolved alert counts |

#### Observability (`/observability`)
| Method | Path | File | Purpose |
|--------|------|------|---------|
| GET | /observability/metrics | `endpoints/observability.py:23` | Prometheus `generate_latest(REGISTRY)` — text/plain format |
| GET | /observability/tracing | `endpoints/observability.py:38` | Latest AgentStep records from DB |
| GET | /observability/dashboard | `endpoints/observability.py:52` | SQL aggregates from agent_runs + Prometheus gauge sync |
| POST | /observability/record | `endpoints/observability.py:69` | Manually record a request metric (testing only) |

#### MCP Tools (`/tools`)
| Method | Path | File | Purpose |
|--------|------|------|---------|
| GET | /tools | `endpoints/tools.py:18` | List all registered tools from ToolRegistry singleton |
| GET | /tools/{name} | `endpoints/tools.py:27` | Tool description + JSON input schema |
| POST | /tools/{name}/execute | `endpoints/tools.py:37` | Dispatch via `registry.execute(name, args)` → runs subprocess |

#### All Agent Endpoints
| Agent | Prefix | File | Methods |
|-------|--------|------|---------|
| Repository | /repo-agent | `endpoints/repo_agent.py` | GET /{id}/understand, /{id}/summary, /{id}/search |
| Knowledge | /knowledge | `endpoints/knowledge_agent.py` | POST /search, /hybrid, /rank |
| Incident | /incidents | `endpoints/incident_agent.py` | POST /analyze, /root-cause, /recommendations |
| Documentation | /docs | `endpoints/documentation_agent.py` | POST /readme, /api, /architecture |
| Code Review | /code-review | `endpoints/code_review_agent.py` | POST /pr, /security, /best-practices |
| Deploy | /deploy | `endpoints/deploy_agent.py` | POST /analyze |

---

## 3. Database Schema (12 tables, pgvector)

### 3.1 Tables

| Table | File | Purpose | Key Columns |
|-------|------|---------|-------------|
| `users` | `models/user.py` | User accounts | id (UUID), email, hashed_password, full_name, is_active, is_superuser |
| `api_keys` | `models/user.py:54` | API keys per user | id, user_id (FK), key_hash, key_prefix, is_active, expires_at |
| `projects` | `models/project.py` | Workspace projects | id, name, description, owner_id (FK), settings (JSONB) |
| `repositories` | `models/project.py:27` | Git repositories | id, project_id (FK), url, branch, provider, indexing_status |
| `repository_files` | `models/project.py:48` | Files inside repos | id, repository_id (FK), path, language, size_bytes, content (TEXT) |
| `documents` | `models/document.py` | Uploaded PDFs/MD/TXT | id, project_id (FK), title, source_type, content |
| `document_chunks` | `models/document.py:36` | Chunked docs with embeddings | id, document_id (FK), chunk_index, content, embedding (VECTOR(768)) |
| `agent_runs` | `models/agent.py` | Planner/agent execution runs | id (UUID), project_id, agent_type, status, input/output (JSONB) |
| `agent_steps` | `models/agent.py:29` | Individual steps in a run | id, run_id (FK), step_index, step_type, tool_name, status, duration_ms |
| `approvals` | `models/agent.py:51` | HITL approval records | id, run_id (FK), action_type, action_data (JSONB), status, reviewed_by |
| `long_term_memory` | `models/memory.py` | TTL-based key-value store | id, user_id, key, value (JSONB), expires_at |
| `semantic_memory` | `models/memory.py:27` | Vector-embedded text | id, text, embedding (VECTOR(768)), metadata (JSONB), created_at |

### 3.2 Embedding Dimensions

Vector dimension is 768 (`nomic-embed-text` output). Two IVFFlat indexes:
- `document_chunks_embedding_idx` on `document_chunks.embedding`
- `semantic_memory_embedding_idx` on `semantic_memory.embedding`

Defined in `backend/app/models/document.py:42` and `backend/app/models/memory.py:33`.

---

## 4. LLM Integration

### 4.1 LLMService (`backend/app/services/llm_service.py`)

Singleton service wrapping LangChain:

```python
class LLMService:
    def _get_model(self) -> BaseChatModel:
        # Ollama (default): ChatOllama(model=llama3.2, base_url=host.docker.internal:11434)
        # OpenAI: ChatOpenAI(model=gpt-4, api_key=...)
    async def generate(system_prompt, user_prompt) -> str
        # model | StrOutputParser → ainvoke
    async def generate_with_context(system_prompt, context, query) -> str
        # Same, but with context injected into HumanMessage
```

### 4.2 EmbeddingService (`backend/app/services/embeddings.py`)

Generates 768-dim vectors via `Ollama.generate(model="nomic-embed-text")`:

```python
class EmbeddingService:
    async def generate_embeddings(texts) -> List[List[float]]
        # POST http://host.docker.internal:11434/api/embeddings
    async def semantic_search(query, limit, threshold, table_name)
        # pgvector cosine similarity: embedding <=> :query_embedding
```

### 4.3 Models Used

| Model | Type | Provider | Purpose |
|-------|------|----------|---------|
| `llama3.2` | Chat | Ollama (host) | All agent LLM calls, alert analysis, intent routing |
| `nomic-embed-text` | Embedding | Ollama (host) | All vector embeddings (documents, memory, alerts) |

---

## 5. Agent System — Pin-to-Pin

### 5.1 Execution Flow

```
User types message in Chat (/agents) or POST /planner/route
        │
        ▼
┌────────────────────────────────────────────────┐
│ IntentRouter (backend/app/services/planner.py) │
│                                                │
│ 1. KEYWORD_RULES — 17 rules matched in order:  │
│    - "architecture", "structure" → repository  │
│    - "question", "what", "how" → knowledge     │
│    - "error", "crash", "incident" → incident   │
│    - "readme", "documentation" → documentation │
│    - "review", "pr", "code quality" → code_rev │
│    - "deploy", "docker", "kubernetes" → deploy │
│    - "hello", "hi" → direct LLM response       │
│                                                │
│ 2. Falls back to LLM classification (generate) │
│    if no keyword match                          │
│                                                │
│ 3. Returns ExecutionPlan dataclass with steps   │
└──────────────────────┬─────────────────────────┘
                       │
                       ▼
┌────────────────────────────────────────────────┐
│ PlanValidator (backend/app/services/           │
│               plan_validator.py)               │
│                                                │
│ 1. Cycle detection (DFS on depends_on graph)   │
│ 2. Missing capability check in CapabilityReg.  │
│ 3. Orphan reference check                      │
│ 4. Approval consistency check                  │
└──────────────────────┬─────────────────────────┘
                       │
                       ▼
┌────────────────────────────────────────────────┐
│ WorkflowEngine.execute_plan()                  │
│ (backend/app/services/workflow_engine.py)      │
│                                                │
│ 1. Topological sort (Kahn's algorithm)         │
│ 2. For each step in order:                     │
│    a. Check dependency completion              │
│    b. Build ProjectContext via ContextBuilder  │
│    c. Resolve capability from CapabilityReg.   │
│    d. Create AgentStep record (status=running) │
│    e. ExecutionRuntime.execute_step() → retry  │
│    f. Record result (completed/failed)         │
│    g. Handle rollback if failed + defined      │
│ 3. Return merged step results                  │
└──────────────────────┬─────────────────────────┘
                       │
                       ▼
┌────────────────────────────────────────────────┐
│ CapabilityRegistry.resolve(step.capability)    │
│ (backend/app/services/capability_registry.py)  │
│                                                │
│ Returns Capability with executor callable:     │
│   agent: agent.process(context) → AgentResult  │
│   mcp:   adapt_mcp(name, registry)(context)    │
│   rest:  adapt_rest()(context) → stub          │
│   python: adapt_python()(context) → stub       │
└────────────────────────────────────────────────┘
```

### 5.2 Agents Registered at Startup

Registered in `backend/app/services/workflow_engine.py:476` — `get_workflow_engine()` factory:

```python
# Line 476-500
registry.register("repository", "Analyze code structure", adapt_agent(repo_agent))
registry.register("knowledge", "Search docs & answer", adapt_agent(knowledge_agent))
registry.register("incident", "Find errors & root cause", adapt_agent(incident_agent))
registry.register("documentation", "Generate docs", adapt_agent(doc_agent))
registry.register("code_review", "Review code quality", adapt_agent(code_review_agent))
registry.register("deploy", "Analyze deployment configs", adapt_agent(deploy_agent))

# MCP tools registered from ToolRegistry (lines 482-493)
for tool in mcp_registry.list_tools():
    registry.register(tool["name"], tool["description"], adapt_mcp(tool["name"], mcp_registry))

# Stubs (lines 494-499)
registry.register("rest_call", "Make HTTP request", adapt_rest())
registry.register("python_exec", "Run Python snippet", adapt_python())
```

**23 capabilities total**: 6 agents + 15 MCP tools + 2 stubs.

### 5.3 Agent Base Interface

All agents use `AgentResult` dataclass (`backend/app/services/agent_base.py`):

```python
@dataclass
class AgentResult:
    result: str               # Main output text
    confidence: float         # 0.0-1.0
    recommendations: List[str] # Actionable next steps
    follow_up_actions: List[str]
    details: Dict             # Structured inner data
```

Each agent's `.process(context: ProjectContext) -> AgentResult` reads `context.project` (with `step_input`, `repository_id`) and returns structured results.

### 5.4 ProjectContext (`backend/app/services/context_builder.py`)

```python
@dataclass
class ProjectContext:
    project_id: UUID
    repository_id: Optional[UUID]
    name: str
    description: str
    repositories: List[Dict]
    documents: List[Dict]
    files: List[Dict]
    user_id: UUID
    step_input: Dict                 # Step-specific input params (for MCP dispatch)
    settings: Optional[ProjectSettings]
```

Built by `ContextBuilder.build()` — runs 3 DB queries (repositories, documents, files) and 2 embedding calls (embed the query, search semantic memory). When called with an existing EngineeringContext (Tier 1 path), uses `dataclasses.replace()` to clone with updated `step_input` only — avoids redundant queries.

### 5.5 Execution Adapters (`backend/app/services/execution_adapters.py`)

```python
def adapt_agent(agent) -> Callable:
    # Agent.process() already matches (context) -> AgentResult

def adapt_mcp(tool_name, mcp_registry) -> Callable:
    # Wraps: mcp_registry.execute(tool_name, context.step_input) -> AgentResult

def adapt_rest() -> Callable:
    # Stub: returns "REST calls not implemented" AgentResult

def adapt_python() -> Callable:
    # Stub: returns "Python execution not implemented" AgentResult
```

---

## 6. MCP Tool System — Pin-to-Pin

### 6.1 Registration Flow

```
app.main.py (line 13): import app.mcp.github
        │
        ▼
backend/app/mcp/github.py (module-level code runs on import):
    registry = get_registry()          # Global ToolRegistry singleton
    gh_mcp = GitHubMCP(registry)        # Registers 3 tools
        registry.register("clone_repository", schema, handler)
        registry.register("create_branch", schema, handler)
        registry.register("create_pull_request", schema, handler)

Same pattern for:
  backend/app/mcp/filesystem.py (4 tools)
  backend/app/mcp/docker.py (4 tools)
  backend/app/mcp/aws.py (4 tools)
```

### 6.2 ToolRegistry (`backend/app/mcp/registry.py`)

```python
class ToolRegistry:
    _tools: Dict[str, ToolDefinition]     # name → metadata + schema
    _handlers: Dict[str, Callable]        # name → async handler

    def register(name, description, input_schema, handler):
        # Stores in both dicts

    def execute(name, args) -> Dict:
        # Looks up handler, calls handler(args)

    def list_tools() -> List[Dict]:
        # Returns all tool metadata
```

### 6.3 All 15 Registered Tools

| Tool | Adapter File | Implementation |
|------|-------------|----------------|
| `clone_repository` | `mcp/github.py:74` | `git clone --depth 1 --branch <b> --single-branch <url> <dir>` |
| `create_branch` | `mcp/github.py:85` | `git checkout -b <branch> <base>` |
| `create_pull_request` | `mcp/github.py:98` | Placeholder — returns dict, no GitHub API call |
| `read_file` | `mcp/filesystem.py:42` | Opens file, reads content |
| `write_file` | `mcp/filesystem.py:54` | Writes content to file |
| `search_files` | `mcp/filesystem.py:66` | Glob search in directory |
| `list_directory` | `mcp/filesystem.py:83` | Lists directory contents |
| `build_image` | `mcp/docker.py:49` | `docker build -t <tag> <path>` |
| `run_container` | `mcp/docker.py:62` | `docker run -d --name <name> <image>` |
| `stop_container` | `mcp/docker.py:79` | `docker stop <container>` |
| `get_logs` | `mcp/docker.py:91` | `docker logs <container>` |
| `s3_list_buckets` | `mcp/aws.py:77` | `aws s3api list-buckets` |
| `s3_upload_file` | `mcp/aws.py:90` | `aws s3 cp <local> s3://<bucket>/<key>` |
| `ec2_list_instances` | `mcp/aws.py:103` | `aws ec2 describe-instances` |
| `cloudwatch_get_metrics` | `mcp/aws.py:116` | `aws cloudwatch get-metric-statistics` |

All MCP tools use `subprocess.run()` to call CLI binaries (git, docker, aws). No SDK integrations.

### 6.4 Dispatch Paths

**Path A — Direct API**: `POST /api/v1/tools/{name}/execute` → `tools.py` → `registry.execute(name, args)` → handler

**Path B — Via WorkflowEngine**: Planner step with capability matching MCP tool name → `CapabilityRegistry.resolve()` → `adapt_mcp()` wrapper → `mcp_registry.execute(name, args)` → handler

---

## 7. AIOps — Alert Pipeline (Pin-to-Pin)

### 7.1 Architecture

```
Prometheus Alertmanager
    │
    │ HTTP POST /api/v1/alerts/webhook
    │ Payload: AlertmanagerWebhook JSON
    ▼
┌──────────────────────────────────────────────┐
│ alert_webhook()                               │
│ backend/app/api/v1/endpoints/alerts.py:102    │
│                                               │
│ 1. record_request() — increment Prometheus    │
│    http_requests_total counter                │
│                                               │
│ 2. Embed alert body via EmbeddingService      │
│    → POST host.docker.internal:11434/api/     │
│        embeddings (nomic-embed-text)           │
│                                               │
│ 3. Store in SemanticMemory:                   │
│    text = "Alert: <summary>\n<description>"   │
│    metadata = {                               │
│      type: "alert",                           │
│      status: "firing"|"resolved",             │
│      alert_names: [...],                      │
│      processing: "pending"                    │
│    }                                          │
│                                               │
│ 4. asyncio.create_task(                       │
│      _process_alert_background(...))          │
│    → Returns immediately                      │
└──────────────────────┬───────────────────────┘
                       │
                       │ (fire-and-forget)
                       ▼
┌──────────────────────────────────────────────┐
│ _process_alert_background()                   │
│ backend/app/api/v1/endpoints/alerts.py:43     │
│                                               │
│ 1. LLMService.generate()                      │
│    System: "Senior SRE analyzing Prometheus   │
│             alert — return valid JSON"        │
│    Timeout: 120s                              │
│                                               │
│ 2. _extract_json() — handles markdown-wrapped │
│    JSON (```json ... ```) and raw {...}       │
│                                               │
│ 3. Parse: root_cause, impact, severity,       │
│    remediation_steps, prevention, confidence  │
│                                               │
│ 4. Open NEW DB session (async_session_maker)  │
│    → EmbedService → MemorySystem              │
│                                               │
│ 5. Store analysis in SemanticMemory:          │
│    text = "Alert Analysis: <root_cause>"      │
│    metadata = {                               │
│      type: "alert_analysis",                  │
│      severity: "critical"|"high"|"medium"|"low"│
│      root_cause: "...",                       │
│      confidence: 0.0-1.0,                     │
│      has_remediation: true/false              │
│    }                                          │
└──────────────────────────────────────────────┘
```

### 7.2 Alert Data Flow

```
SemanticMemory stores BOTH raw alerts and analyses:

Entry 1 (type: "alert"):
  text: "Alert: CPU > 95% on prod-web-01\nCPU usage at 97% for 10 min"
  metadata: { type: "alert", status: "firing", alert_names: ["HighCPU"], processing: "pending" }

Entry 2 (type: "alert_analysis"):
  text: "Alert Analysis: High CPU on prod-web-01"
  metadata: {
    type: "alert_analysis",
    severity: "critical",
    root_cause: "Memory leak in payment-service",
    confidence: 0.85,
    has_remediation: true,
    alert_summary: "CPU > 95% on prod-web-01"
  }
```

### 7.3 Endpoints

| Endpoint | What it does | Code |
|----------|-------------|------|
| `POST /alerts/webhook` | Receives Alertmanager payload → stores alert → fires background LLM analysis | `endpoints/alerts.py:102` |
| `GET /alerts/history?limit=N` | `search_semantic("alert notification incident", limit, threshold=0.0)` — returns all alert + analysis entries | `endpoints/alerts.py:166` |
| `GET /alerts/stats` | Counts firing vs resolved entries from semantic memory | `endpoints/alerts.py:180` |

### 7.4 Background Task Isolation

```python
async def _process_alert_background(alert_body, incident_summary, description):
    # Uses LLMService singleton (no Depends needed)
    llm = LLMService()
    raw = await asyncio.wait_for(llm.generate(system_prompt, alert_body), timeout=120.0)
    parsed = json.loads(_extract_json(raw))

    # Opens fresh DB session (not request-scoped)
    async with async_session_maker() as db:
        embeddings = EmbeddingService(db)
        memory = MemorySystem(db, embeddings)
        emb = (await embeddings.generate_embeddings([analysis_text]))[0]
        await memory.store_semantic(text=..., embedding=emb, metadata=...)
```

### 7.5 Alertmanager Webhook Payload Format

```json
{
  "status": "firing",
  "alerts": [{
    "status": "firing",
    "labels": { "alertname": "HighCPU", "severity": "critical" },
    "annotations": { "summary": "CPU > 95%", "description": "CPU at 97%" },
    "startsAt": "2026-07-06T12:00:00Z"
  }],
  "commonLabels": { "severity": "critical" },
  "commonAnnotations": { "summary": "CPU > 95% on prod-web-01" }
}
```

---

## 8. Prometheus & Observability — Pin-to-Pin

### 8.1 Prometheus Scrape Pipeline

```
Prometheus container (prom/prometheus:latest, port 9090)
    │
    │ Scrape config (infra/prometheus.yml):
    │   job_name: 'aegis-backend'
    │   metrics_path: /api/v1/observability/metrics
    │   targets: ['backend:8000']   (Docker network DNS)
    │   scrape_interval: 15s
    │
    ▼ Every 15s
GET http://backend:8000/api/v1/observability/metrics
    │
    ▼
backend/app/api/v1/endpoints/observability.py:23
    @router.get("/metrics", response_class=PlainTextResponse)
    async def get_metrics(service = Depends(get_observability_service)):
        metrics = await service.get_metrics()
        return PlainTextResponse(metrics, media_type="text/plain; version=0.0.4")
    │
    ▼
backend/app/services/observability.py:32
    async def get_metrics(self) -> str:
        return generate_latest(REGISTRY).decode("utf-8")
    │
    ▼
prometheus_client serializes all registered metrics:
    - http_requests_total{method, endpoint, status}
    - http_request_duration_seconds_bucket{method, endpoint, le}
    - active_runs  (synced from DB on each dashboard call)
    - total_errors{type}  (always 0 — never written)
    - Python default process metrics (cpu, memory, gc)
```

### 8.2 Prometheus Metrics Defined

```python
# backend/app/services/observability.py:15-18
http_requests_total = Counter("http_requests_total", ..., ["method", "endpoint", "status"])
http_request_duration_seconds = Histogram("http_request_duration_seconds", ..., ["method", "endpoint"])
active_runs = Gauge("active_runs", "Currently active agent runs")
total_errors = Counter("total_errors", "Total errors", ["type"])
```

### 8.3 What Populates Each Metric

| Metric | Where Written | Value |
|--------|---------------|-------|
| `http_requests_total` | `observability.py:27` — `record_request()` | Incremented on: webhook POST, manual /record endpoint |
| `http_request_duration_seconds` | `observability.py:30` — `record_request()` | Observed on same calls |
| `active_runs` | `observability.py:92` — `get_dashboard_data()` | Set to COUNT of `status='running'` in agent_runs table |
| `total_errors` | Never written | Always 0 |

**Important**: There is NO automatic middleware that captures all HTTP requests. `record_request()` is called explicitly from:
1. `endpoints/alerts.py:126` — on every webhook call  
2. `endpoints/observability.py:50` — the manual `/record` endpoint

### 8.4 ObservabilityService (`backend/app/services/observability.py:21`)

```python
class ObservabilityService:
    async def record_request(method, endpoint, status, duration_ms):
        # Increments Counter, observes Histogram

    async def get_metrics() -> str:
        # generate_latest(REGISTRY) — all Prometheus metrics serialized

    async def get_tracing(run_id=None, limit=50) -> list:
        # SELECT * FROM agent_steps ORDER BY created_at DESC LIMIT N
        # Returns step_id, run_id, step_type, name, status, duration_ms, created_at

    async def get_dashboard_data() -> Dict:
        # SQL aggregate queries on agent_runs:
        #   total_runs, completed, failed, running (COUNT with CASE)
        #   agent_counts (GROUP BY agent_type)
        # Also: active_runs.set(running_count)  # Sync Prometheus gauge
```

### 8.5 Tracing Data

Written by `WorkflowEngine.execute_plan()` at `backend/app/services/workflow_engine.py:211-239`:

```python
# Start of step
step_record = AgentStep(run_id=..., step_index=..., step_type=..., name=..., status="running")
self.db.add(step_record)
await self.db.commit()

# Execute
result = await runtime.execute_step(step, capability.executor, context)

# End of step
step_record.status = result.status          # "completed" | "failed"
step_record.duration_ms = result.duration_ms
step_record.output_data = {"result": ...}   # or {"error": ...}
step_record.completed_at = datetime.utcnow()
await self.db.commit()
```

### 8.6 Dashboard Aggregation

```
GET /api/v1/observability/dashboard
    │
    ▼
SQL:
  SELECT
    COUNT(*) as total_runs,
    COUNT(CASE WHEN status='completed' THEN 1 END) as completed,
    COUNT(CASE WHEN status='failed' THEN 1 END) as failed,
    COUNT(CASE WHEN status='running' THEN 1 END) as running
  FROM agent_runs

  SELECT agent_type, COUNT(*) as count
  FROM agent_runs GROUP BY agent_type
    │
    ▼
Returns HTTP 200 JSON:
  { total_runs: N, completed: N, failed: N, running: N, agent_counts: { "planner": 2 } }
```

### 8.7 Docker Compose Config

```yaml
# docker-compose.yml:49-59
prometheus:
  image: prom/prometheus:latest
  container_name: aegis-prometheus
  volumes:
    - ./infra/prometheus.yml:/etc/prometheus/prometheus.yml
  ports:
    - "${PROMETHEUS_PORT:-9090}:9090"
  depends_on:
    - backend
```

```yaml
# infra/prometheus.yml
global:
  scrape_interval: 15s
scrape_configs:
  - job_name: 'aegis-backend'
    metrics_path: /api/v1/observability/metrics
    static_configs:
      - targets: ['backend:8000']
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']
```

---

## 9. Frontend (React + Vite + Tailwind)

### 9.1 Tech Stack
- React 18, TypeScript 5.5 — compiled by `tsc -b`
- Vite 5.4 (build tool), React Router 6.26 (client-side routing)
- Tailwind CSS 3.4 (utility-first), Lucide React (icons)
- shadcn/ui component system (tailwind-merge + clsx class management)

### 9.2 Build Process

```
Dockerfile (frontend/Dockerfile):
  1. node:20-alpine — npm install (243 packages)
  2. npm run build → tsc -b + vite build
  3. Output: dist/ (index.html + assets/)
  4. nginx:1.27-alpine — serves dist/ from /usr/share/nginx/html
```

### 9.3 Page Routes (11 pages)

| Path | Component | Auth | API Calls on Mount |
|------|-----------|------|-------------------|
| `/login` | `pages/Login.tsx` | No | `authApi.login()` on submit |
| `/register` | `pages/Register.tsx` | No | `authApi.register()` on submit |
| `/dashboard` | `pages/Dashboard.tsx` | Yes | Projects, repositories, document counts |
| `/projects` | `pages/Projects.tsx` | Yes | `projectsApi.list()` |
| `/repositories` | `pages/Repositories.tsx` | Yes | `repositoriesApi.list()` |
| `/knowledge` | `pages/Knowledge.tsx` | Yes | Documents list, chunk viewer |
| `/agents` | `pages/Agents.tsx` | Yes | Agent cards — fires POST to agent endpoints |
| `/chat` | `pages/Chat.tsx` | Yes | `plannerApi.route()` — sends message, streams response |
| `/approvals` | `pages/ApprovalQueue.tsx` | Yes | Pending approvals list + approve/reject actions |
| `/ops` | `pages/OpsDashboard.tsx` | Yes | Dashboard + tracing + alert stats + alert history — polls every 15s |
| `/settings` | `pages/Settings.tsx` | Yes | Profile, password, API keys |

### 9.4 API Client (`frontend/src/lib/api.ts`)

Typed fetch wrapper with these features:
- JWT Bearer token from `localStorage`
- Auto 401 → refresh token endpoint → retry original request
- Token persistence across sessions
- 13 typed API objects:

| Client | Methods |
|--------|---------|
| `authApi` | login, register, refresh, me, updateProfile, changePassword, listApiKeys, createApiKey, deleteApiKey |
| `projectsApi` | create, list, get, update, delete |
| `repositoriesApi` | create, list, get, ingest, listFiles, delete |
| `documentsApi` | create, list, get, getChunks, delete |
| `embeddingsApi` | generateDocumentEmbeddings, generateRepoEmbeddings, search, hybridSearch |
| `plannerApi` | plan, route, resume, getRun, getRunSteps |
| `memoryApi` | shortTermStore, shortTermGet, longTermStore, longTermGet, semanticStore, semanticSearch, conversationStore, conversationGet, conversationClear |
| `alertsApi` | stats, history |
| `repoAgentApi` | understand, summary |
| `knowledgeAgentApi` | search, hybrid |
| `incidentAgentApi` | analyze, rootCause, recommendations |
| `docAgentApi` | readme, api, architecture |
| `codeReviewApi` | prReview, security, bestPractices |

### 9.5 OpsDashboard (`frontend/src/pages/OpsDashboard.tsx`)

The AIOps observability page. On mount and every 15s:

```typescript
const [dashRes, traceRes, alertRes, alertHistoryRes] = await Promise.all([
  fetch('/api/v1/observability/dashboard'),        // Agent run stats
  fetch('/api/v1/observability/tracing?limit=20'),  // Latest steps
  alertsApi.stats(),                                 // Alert counts
  alertsApi.history(20),                             // Recent alerts + analyses
])
```

**Renders 6 sections:**
1. **Stats Cards** (6) — Total Runs, Success Rate %, Failed, Active Runs, Alerts (Firing), Total Alerts
2. **Agent Run Breakdown** — Horizontal bar chart per agent type
3. **Alert Status** — Firing count (red) + Resolved count (green) + Failure rate
4. **Alert Feed** — Two renderers:
   - Raw alerts (`type:"alert"`) — alert name, status badge (firing=red, resolved=green), timestamp
   - Analysis entries (`type:"alert_analysis"`) — severity badge, root cause text, confidence %, remediation indicator
5. **Execution Traces** — Table: Step Name, Type badge, Status pill (completed=green, failed=red, running=blue), Duration (s), Time
6. **Prometheus Link** — External link to `/api/v1/observability/metrics`

### 9.6 Nginx Config (`frontend/nginx.conf`)

```nginx
server {
    listen 80;
    root /usr/share/nginx/html;
    index index.html;

    # SPA fallback — serve index.html for all non-file routes
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Proxy API requests to backend
    location /api/v1/ {
        proxy_pass http://backend:8000/api/v1/;
        proxy_read_timeout 300s;    # LLM calls can take 2-3 min
        proxy_connect_timeout 60s;
    }

    # Gzip
    gzip on;
    gzip_types text/css application/javascript application/json image/svg+xml;
}
```

---

## 10. Memory System — Three-Tier

### 10.1 Tier Definitions

| Tier | Table | File | TTL | Written By |
|------|-------|------|-----|------------|
| **Short-term** | `agent_steps` | `models/agent.py:29` | Per-run | `WorkflowEngine.execute_plan()` — per step |
| **Long-term** | `long_term_memory` | `models/memory.py` | Configurable (default 30d) | `MemorySystem.store_long_term()` — any agent |
| **Semantic** | `semantic_memory` | `models/memory.py:27` | Forever | Alerts webhook, planner, knowledge agent |

### 10.2 MemorySystem (`backend/app/services/memory.py:16`)

```python
class MemorySystem:
    async def store_short_term(run_id, key, value)
        # AgentStep with name="memory:<key>"
    async def get_short_term(run_id, key)
        # SELECT FROM agent_steps WHERE name="memory:<key>" ORDER BY created_at DESC

    async def store_long_term(user_id, key, value, ttl_days=30)
        # LongTermMemory with expires_at = now + ttl_days
    async def get_long_term(user_id, key)
        # SELECT WHERE key=key AND expires_at > now()

    async def store_semantic(text, embedding, metadata=None)
        # SemanticMemory(text, embedding, doc_metadata)
    async def search_semantic(query, limit=5, threshold=0.5)
        # Embed query → pgvector cosine similarity search
    async def list_semantic(limit=50)
        # SELECT ORDER BY created_at DESC
```

### 10.3 Integration Points

| Integration | Where | What Happens |
|-------------|-------|--------------|
| **PlannerAgent** | `planner.py:135-145` | Before planning: searches semantic memory for similar tasks → injects as context. After completion: stores task+plan as new semantic memory entry |
| **KnowledgeAgent** | `knowledge_agent.py` | `query()` method: searches semantic memory for past Q&A → injects into prompt. Stores new Q&A after generation |
| **Alert Webhook** | `alerts.py:148-167` | Stores raw alert in semantic memory, fires background LLM analysis which stores a second `alert_analysis` entry |
| **DeployAgent** | (declared, not yet wired) | Can store/retrieve deployment analysis results |

---

## 11. Docker Deployment

### 11.1 Services

```yaml
# docker-compose.yml
services:
  postgres:
    image: pgvector/pgvector:pg16
    ports: ["5432:5432"]
    healthcheck: { test: pg_isready }
    volumes: [postgres_data:/var/lib/postgresql/data]

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
    healthcheck: { test: redis-cli ping }

  backend:
    build: ./backend
    ports: ["8000:8000"]
    depends_on: [postgres, redis]
    environment:
      - DATABASE_URL=postgresql+asyncpg://postgres:${POSTGRES_PASSWORD}@postgres:5432/aegis
      - OLLAMA_BASE_URL=http://host.docker.internal:11434
    healthcheck: { test: curl -f http://localhost:8000/api/v1/health }

  frontend:
    build: ./frontend
    ports: ["80:80"]
    depends_on: [backend]
    healthcheck: { test: curl -f http://localhost:80 }

  prometheus:
    image: prom/prometheus:latest
    ports: ["9090:9090"]
    volumes: [./infra/prometheus.yml:/etc/prometheus/prometheus.yml]
    depends_on: [backend]
```

### 11.2 Key Fixes Applied

| Issue | Fix | File |
|-------|-----|------|
| `git` not in backend container | Added to apt-get install in Dockerfile | `backend/Dockerfile` |
| Postgres `InterfaceError: connection is closed` | `pool_pre_ping=True, pool_recycle=3600` | `db/session.py:10-11` |
| nginx 504 timeout on slow LLM calls | `proxy_read_timeout 300s` | `frontend/nginx.conf` |
| Prometheus scrape content-type wrong | `media_type="text/plain; version=0.0.4"` | `endpoints/observability.py:30` |
| Dashboard asyncpg Row compatibility | `dict(stats._mapping)`, `a.agent_type/a.count` | `services/observability.py:72-85` |

---

## 12. Key Architectural Decisions

| Decision | Rationale |
|----------|-----------|
| **Planner/WorkflowEngine split** | Planner reasons and produces ExecutionPlan; WorkflowEngine orchestrates only. Clear separation of concerns. |
| **DAG execution via topological sort** | Independent steps can run in parallel. Kahn's algorithm. |
| **CapabilityRegistry as single dispatch point** | No separate executor layer. Adapters normalize all execution types (agent, MCP, REST, Python) at registration time. |
| **No global CapabilityRegistry singleton** | Populated per-request in factory function. |
| **Ollama on host** | Avoid GPU passthrough complexity. Container connects via host.docker.internal. |
| **step_input in ProjectContext** | Only difference between agent and MCP dispatch — MCP tools need step-specific params. |
| **Plain-text prompts + JSON parsing + fallback** | Keeps LLM calls simple. `_extract_json()` handles markdown-wrapped output. |
| **pgvector for embeddings** | Native PostgreSQL extension — no vector DB lock-in. No external service dependency. |
| **structlog for logging** | Structured JSON logs for production observability. |
| **Prometheus metrics + DB aggregates** | Metrics for counters/latency (prometheus_client), dashboard data from SQL (runs, steps). |
| **Alert background task isolation** | Opens fresh DB session via `async_session_maker` — avoids request-scoped dependency lifetime issues. |
| **120s LLM timeout** | llama3.2 on 3.5 GiB RAM takes 30-60s for analysis. |
| **MCP no special treatment** | All 15 MCP tools registered as capabilities in same CapabilityRegistry as agents. No separate dispatch path. |
| **EngineeringContext composition** | Root aggregate with 8 bounded sub-contexts. `dataclasses.replace()` for per-step cloning. |

---

## 13. Project Files

| File | Purpose |
|------|---------|
| `AGENTS.md` | Agent architecture reference — agent definitions, MCP tool system, memory tiers, LLM integration, adding new agents |
| `ABOUT.md` | This file — full application overview |
| `task.md` | ✅ Original project spec |
| `task_v2.md` | ✅ Complete (7 milestones) — Planner-centric migration |
| `task_v3.md` | ✅ M1 complete — Generic adapter architecture |
| `TASK.md` | DO NOT MODIFY — original spec |
| `docker-compose.yml` | Local dev — postgres, redis, backend, frontend, prometheus |
| `docker-compose.prod.yml` | Production overlay — CORS, secrets, restricted ports |
| `infra/prometheus.yml` | Prometheus scrape config — targets backend:8000 |
| `infra/docker-compose.aws.yml` | AWS ECS-ready compose file |
| `infra/deploy.sh` | Production deployment script |
| `infra/nginx.prod.conf` | Production Nginx config with SSL |
| `infra/init-db.sql` | DB init SQL (pgvector, uuid-ossp) |
| `infra/.env.example` | Environment variable template |
| `frontend/nginx.conf` | Nginx config for frontend container — SPA fallback + API proxy + 300s timeout |

---

## 14. Quick Start

```powershell
# Prerequisites: Docker Desktop + Ollama (with models pulled)
#   ollama pull llama3.2
#   ollama pull nomic-embed-text

# 1. Start all services
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

# 2. Open browser → http://localhost
#    Register at /register, create project, add repo, explore agents

# 3. Test alert pipeline (send a Prometheus-style alert)
$body = @'
{ "status":"firing", "alerts":[{ "status":"firing",
  "labels":{"alertname":"HighCPU","severity":"critical"},
  "annotations":{"summary":"CPU > 95% on prod-web-01","description":"CPU at 97% for 10 min"}}],
  "commonAnnotations":{"summary":"CPU > 95%"}}
'@ ; $body | Set-Content "$env:TEMP\alert.json"
curl.exe -s -X POST http://localhost:8000/api/v1/alerts/webhook -H "Content-Type: application/json" -d "@$env:TEMP\alert.json"

# 4. Check Ops Dashboard at /ops (auto-refreshes every 15s)
#    Raw alert appears immediately → LLM analysis appears ~60s later

# 5. View Prometheus metrics
#    http://localhost:9090 (Prometheus UI)
#    http://localhost:8000/api/v1/observability/metrics (raw text)

# Cloudflare Tunnel for public access
& "$env:USERPROFILE\cloudflared.exe" tunnel --url http://localhost:80
```
