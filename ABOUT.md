# Aegis AI — Full Application Overview

An open-source Agentic AI Engineering & AIOps Platform. Aegis AI ingests code repositories and documents, analyzes them via LLM-powered agents, supports conversational task routing, human-in-the-loop approvals, and a three-tier memory system — all running locally via Docker.

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
```

4 Docker containers managed via `docker-compose.yml` + `docker-compose.prod.yml`.

---

## 2. Backend (FastAPI + Python 3.11)

### 2.1 Tech Stack
- **Framework**: FastAPI (async), Uvicorn
- **ORM**: SQLAlchemy 2.0 (async), Alembic migrations
- **Database**: PostgreSQL 16 + pgvector extension
- **Cache**: Redis 7 (AOF persistence)
- **LLM Integration**: LangChain (ChatOllama / ChatOpenAI)
- **Auth**: JWT (access + refresh tokens via python-jose), Argon2 password hashing
- **Vector Search**: pgvector (IVFFlat index, 768-dim embeddings)
- **Structured Logging**: structlog
- **Observability**: Prometheus metrics (Counter, Histogram, Gauge)
- **Background Tasks**: asyncio tasks

### 2.2 API Endpoints (68 total under `/api/v1`)

#### Health (`/health`)
| Method | Path | Purpose |
|--------|------|---------|
| GET | /health | Root health check |
| GET | /health/db | Database connectivity |
| GET | /health/redis | Redis connectivity |

#### Auth (`/auth`)
| Method | Path | Purpose |
|--------|------|---------|
| POST | /auth/register | Register new user |
| POST | /auth/login | Login with email/password |
| POST | /auth/refresh | Refresh JWT token pair |
| GET | /auth/me | Get current user profile |
| PATCH | /auth/me | Update profile (full_name) |
| POST | /auth/change-password | Change password |
| GET | /auth/api-keys | List API keys |
| POST | /auth/api-keys | Create API key |
| DELETE | /auth/api-keys/{id} | Delete API key |

#### Projects (`/projects`)
| Method | Path | Purpose |
|--------|------|---------|
| POST | /projects | Create project |
| GET | /projects | List all projects |
| GET | /projects/{id} | Get project details |
| PATCH | /projects/{id} | Update project |
| DELETE | /projects/{id} | Delete project |

#### Repositories (`/repositories`)
| Method | Path | Purpose |
|--------|------|---------|
| POST | /repositories | Register repository |
| GET | /repositories | List all repositories |
| GET | /repositories/{id} | Get repository details |
| POST | /repositories/{id}/ingest | Trigger file ingestion |
| GET | /repositories/{id}/files | List repository files |
| DELETE | /repositories/{id} | Delete repository |

#### Documents (`/documents`)
| Method | Path | Purpose |
|--------|------|---------|
| POST | /documents/upload | Upload PDF/MD/TXT file |
| POST | /documents/text | Create text document |
| GET | /documents | List all documents |
| GET | /documents/{id} | Get document with content |
| GET | /documents/{id}/chunks | Get document chunks |
| DELETE | /documents/{id} | Delete document |

#### Embeddings (`/embeddings`)
| Method | Path | Purpose |
|--------|------|---------|
| POST | /embeddings/documents/{id}/generate | Generate embeddings for document chunks |
| POST | /embeddings/repositories/{id}/generate | Generate embeddings for repo files |
| POST | /embeddings/search | Semantic search (cosine similarity) |
| POST | /embeddings/hybrid-search | Hybrid search (semantic + ILIKE keyword) |

#### Repository Analysis (`/analyze`)
| Method | Path | Purpose |
|--------|------|---------|
| POST | /analyze/{id} | Full repository analysis (deps, APIs, architecture) |
| GET | /analyze/{id}/dependencies | Dependency graph |
| GET | /analyze/{id}/services | Service discovery + architecture |

#### Planner (`/planner`)
| Method | Path | Purpose |
|--------|------|---------|
| POST | /planner/plan | Plan + execute a task via DAG |
| POST | /planner/route | Route message to agents + execute |
| POST | /planner/resume/{run_id} | Resume after HITL approval |
| GET | /planner/runs/{run_id} | Get run status |
| GET | /planner/runs/{run_id}/steps | Get run steps with results |

#### Workflows (`/workflows`)
| Method | Path | Purpose |
|--------|------|---------|
| GET | /workflows/runs | List agent runs |
| POST | /workflows/execute | Execute custom workflow |
| GET | /workflows/runs/{id}/state | Get workflow state |
| POST | /workflows/runs/{id}/resume | Resume workflow |
| POST | /workflows/runs/{id}/retry | Retry failed workflow |

#### Memory (`/memory`)
| Method | Path | Purpose |
|--------|------|---------|
| POST | /memory/short-term/{run_id} | Store short-term memory |
| GET | /memory/short-term/{run_id}/{key} | Read short-term memory |
| POST | /memory/long-term | Store long-term memory (TTL key-value) |
| GET | /memory/long-term/{key} | Read long-term memory |
| POST | /memory/semantic | Store semantic memory (vector-embedded) |
| GET | /memory/semantic | List semantic memory entries |
| POST | /memory/search | Search semantic memory by similarity |
| POST | /memory/conversation/{project_id} | Store chat message |
| GET | /memory/conversation/{project_id} | Get conversation history |
| DELETE | /memory/conversation/{project_id} | Clear conversation |
| GET | /memory/runs/{run_id}/summary | Summarize a run |

#### MCP Tools (`/tools`)
| Method | Path | Purpose |
|--------|------|---------|
| GET | /tools | List all registered MCP tools |
| GET | /tools/{name} | Get tool metadata + schema |
| POST | /tools/{name}/execute | Execute a tool |

#### Repository Agent (`/repo-agent`)
| Method | Path | Purpose |
|--------|------|---------|
| GET | /repo-agent/{id}/understand | LLM architecture analysis |
| GET | /repo-agent/{id}/summary | Summarize architecture |
| GET | /repo-agent/{id}/search | Search codebase |

#### Knowledge Agent (`/knowledge`)
| Method | Path | Purpose |
|--------|------|---------|
| POST | /knowledge/search | Retrieve docs + LLM answer |
| POST | /knowledge/hybrid | Hybrid search + rank |
| POST | /knowledge/rank | Re-rank results |

#### Incident Agent (`/incidents`)
| Method | Path | Purpose |
|--------|------|---------|
| POST | /incidents/analyze | Scan repo for error keywords + root cause |
| POST | /incidents/root-cause | Deep root cause analysis |
| POST | /incidents/recommendations | Remediation recommendations |

#### Documentation Agent (`/docs`)
| Method | Path | Purpose |
|--------|------|---------|
| POST | /docs/readme | Generate README.md |
| POST | /docs/api | Generate API documentation |
| POST | /docs/architecture | Generate architecture docs |

#### Code Review Agent (`/code-review`)
| Method | Path | Purpose |
|--------|------|---------|
| POST | /code-review/pr | PR review (security + quality) |
| POST | /code-review/security | Security vulnerability audit |
| POST | /code-review/best-practices | Best practices analysis |

#### Approvals (`/approvals`)
| Method | Path | Purpose |
|--------|------|---------|
| POST | /approvals/{run_id} | Request HITL approval |
| POST | /approvals/{id}/approve | Approve a pending action |
| POST | /approvals/{id}/reject | Reject + provide reason |
| GET | /approvals/pending | List pending approvals |
| GET | /approvals/audit | Approval audit log |

#### Observability (`/observability`)
| Method | Path | Purpose |
|--------|------|---------|
| GET | /observability/metrics | Prometheus metrics |
| GET | /observability/tracing | Execution tracing data |
| GET | /observability/dashboard | Dashboard aggregate stats |
| POST | /observability/record | Record a request metric |

#### Deploy Agent (`/deploy`)
| Method | Path | Purpose |
|--------|------|---------|
| POST | /deploy/analyze | Analyze Docker/CI/CD/infra configs |

---

## 3. Database Schema (8 tables, pgvector)

### 3.1 Tables

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `users` | User accounts | id, email, hashed_password, full_name, is_active, is_superuser |
| `api_keys` | API keys per user | id, user_id (FK), key_hash, key_prefix, is_active, expires_at |
| `projects` | Workspace projects | id, name, description, owner_id (FK), settings (JSONB) |
| `repositories` | Git repositories | id, project_id (FK), url, branch, provider, indexing_status |
| `repository_files` | Files inside repos | id, repository_id (FK), path, language, size_bytes, content |
| `documents` | Uploaded PDFs/MD/TXT | id, project_id (FK), title, source_type, content |
| `document_chunks` | Chunked docs with embeddings | id, document_id (FK), chunk_index, content, embedding (VECTOR(768)) |
| `agent_runs` | Planner/agent execution runs | id, project_id, agent_type, status, input/output (JSONB) |
| `agent_steps` | Individual steps in a run | id, run_id (FK), step_index, step_type, tool_name, status |
| `approvals` | HITL approval records | id, run_id (FK), action_type, action_data (JSONB), status, reviewed_by |
| `long_term_memory` | TTL-based key-value store | id, user_id, key, value (JSONB), expires_at |
| `semantic_memory` | Vector-embedded text | id, text, embedding (VECTOR(768)), metadata (JSONB) |

### 3.2 Embedding Dimensions

The vector dimension is 768 (nomic-embed-text output). Two IVFFlat indexes exist on `document_chunks.embedding` and `semantic_memory.embedding`.

---

## 4. Agent System

### 4.1 Architecture

```
User Task
    │
    ▼
┌──────────────┐
│ IntentRouter │  Keyword + LLM fallback routing
│              │  Returns ExecutionPlan (DAG of steps)
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ PlanValidator│  Validates: cycles, missing deps, capability availability
│              │  Checks approval requirements
└──────┬───────┘
       │
       ▼
┌──────────────┐
│WorkflowEngine│  Executes DAG via topological sort (Kahn's algorithm)
│              │  Independent steps run in parallel
│              │  Per-step: retries with backoff, timeout, rollback
└──────┬───────┘
       │
       ▼
┌──────────────┐
│CapabilityReg.│  Routes to agent / MCP tool / REST / Python
│ + Adapters   │  Normalizes all to (context) -> AgentResult
└──────────────┘
```

### 4.2 Agents (7 specialized + 1 meta-planner)

| Agent | File | Purpose |
|-------|------|---------|
| **Planner Agent** | `planner.py` | Meta-agent. Decomposes tasks into ExecutionPlan DAG. Integrates memory + MCP tools. |
| **Repository Agent** | `repository_agent.py` | Analyzes codebases: architecture, tech stack, design patterns, code search |
| **Knowledge Agent** | `knowledge_agent.py` | Hybrid search over documents. LLM Q&A with memory context injection |
| **Incident Agent** | `incident_agent.py` | Error keyword scanning + LLM root cause + remediation |
| **Documentation Agent** | `documentation_agent.py` | Generates README, API docs, architecture docs in markdown |
| **Code Review Agent** | `code_review_agent.py` | Security audit, code quality, best practices via LLM |
| **Deploy Agent** | `deploy_agent.py` | Analyzes Dockerfiles, compose, CI/CD, infra configs |

### 4.3 ExecutionPlan → ExecutionStep

The contract between Planner and WorkflowEngine:

```python
@dataclass
class ExecutionStep:
    id: str                           # Unique step ID
    name: str                         # Human-readable name
    capability: str                   # Capability name to dispatch (e.g. "repository", "knowledge")
    input: Dict                       # Step-specific params (becomes step_input in ProjectContext)
    depends_on: List[str]            # DAG dependencies (IDs of predecessor steps)
    requires_approval: bool
    retry_policy: Optional[RetryPolicy]  # max_retries, retry_delay, backoff_multiplier
    timeout_seconds: Optional[int]
    rollback_step: Optional[str]      # ID of the rollback step

@dataclass  
class ExecutionPlan:
    intent: str
    task_description: str
    steps: List[ExecutionStep]
    approvals_required: List[str]     # Step IDs needing approval
    rollback_strategy: Optional[RollbackStrategy]
```

### 4.4 CapabilityRegistry + Execution Adapters

A single `CapabilityRegistry` holds all dispatch targets. Four adapter factories normalize execution types:

| Adapter | Factory | Normalizes |
|---------|---------|------------|
| `adapt_agent` | Identity wrapper | Agent `.process()` methods already match `(context) -> AgentResult` |
| `adapt_mcp` | Captures `tool_name`, dispatches via MCP registry | Splits `step_input` as tool params |
| `adapt_rest` | Stub | Makes HTTP calls |
| `adapt_python` | Stub | Executes Python snippets |

At startup, `get_workflow_engine()` registers:
- **6 agents** (repository, knowledge, incident, documentation, code_review, deploy)
- **15 MCP tools** (3 GitHub + 4 Filesystem + 4 Docker + 4 AWS)
- **2 stubs** (rest_call, python_exec)

### 4.5 MCP Tool System

14 tools across 4 adapters, all registered in `ToolRegistry` (singleton):

| Adapter | Tools |
|---------|-------|
| **GitHub** | clone_repository, create_branch, create_pull_request |
| **Filesystem** | read_file, write_file, search_files, list_directory |
| **Docker** | build_image, run_container, stop_container, get_logs |
| **AWS** | s3_list_buckets, s3_upload_file, ec2_list_instances, cloudwatch_get_metrics |

Tools are registered at app startup via `import app.mcp.github` etc. in `main.py`.

### 4.6 Memory System (Three-Tier)

| Tier | Storage | TTL | Purpose |
|------|---------|-----|---------|
| **Short-term** | `AgentStep` DB records | Per-run | Current execution context (inputs, outputs, status per step) |
| **Long-term** | `LongTermMemory` table | Configurable TTL | Persistent key-value across sessions |
| **Semantic** | `SemanticMemory` table + pgvector | Forever | Vector-embedded text for similarity search |

Integration points:
- **PlannerAgent**: Injects matching semantic memory into LLM prompt before planning; stores results after completion
- **KnowledgeAgent**: Searches semantic memory for past Q&A before calling LLM; stores new Q&A after

---

## 5. Frontend (React + Vite + Tailwind)

### 5.1 Tech Stack
- React 18, TypeScript 5.5
- Vite 5.4 (build tool), React Router 6.26
- Tailwind CSS 3.4, Lucide React icons
- shadcn/ui component system (tailwind-merge + clsx)

### 5.2 Page Routes (10 pages)

| Path | Component | Auth | Purpose |
|------|-----------|------|---------|
| `/login` | Login.vue-style | No | Email/password login |
| `/register` | Register | No | User registration |
| `/dashboard` | Dashboard | Yes | Stats overview (projects, repos, runs) |
| `/projects` | Projects | Yes | CRUD project management |
| `/repositories` | Repositories | Yes | Repository list + ingest trigger |
| `/knowledge` | Knowledge | Yes | Document browser, chunk viewer, semantic memory search |
| `/agents` | Agents | Yes | Agent action cards + planner execution |
| `/chat` | Chat | Yes | Conversational planner with expandable results |
| `/approvals` | ApprovalQueue | Yes | HITL approval/reject actions |
| `/settings` | Settings | Yes | Profile, password change, API key management |

### 5.3 API Client (`lib/api.ts`)

Typed fetch wrapper with:
- JWT Bearer token injection
- Auto-refresh on 401 (uses refresh token)
- Token persistence in localStorage
- Typed API objects for: authApi, projectsApi, repositoriesApi, documentsApi, plannerApi, repoAgentApi, knowledgeAgentApi, incidentAgentApi, docAgentApi, codeReviewApi, deployApi, approvalsApi, memoryApi, agentRunsApi

---

## 6. Deployment

### 6.1 Docker Compose (Local Dev)

File: `docker-compose.yml`

| Service | Image | Port | Depends On | Healthcheck |
|---------|-------|------|------------|-------------|
| postgres | pgvector/pgvector:pg16 | 5432 | - | pg_isready |
| redis | redis:7-alpine | 6379 | - | redis-cli ping |
| backend | Custom Dockerfile | 8000 | postgres, redis | HTTP /api/v1/health |
| frontend | Custom Dockerfile | 80 | backend | curl localhost:80 |

Ollama runs on the **host machine** (not containerized). Backend connects via `host.docker.internal:11434`.

### 6.2 Production Overlay

File: `docker-compose.prod.yml`
- Restricts port exposure (containers not exposed to host by default)
- Requires `SECRET_KEY` env var (will fail if unset)
- Mounts `init-db.sql` to auto-create pgvector extensions
- Sets `LOG_LEVEL=WARNING`
- Sets CORS origins to production domain

### 6.3 Backend Dockerfile (multi-stage)

- **Builder**: `python:3.11-slim`, installs build-essential + libpq-dev, builds wheels
- **Runner**: `python:3.11-slim`, installs libpq-dev + curl, installs from wheels, copies app code
- Runs as non-root `app` user
- CMD: `uvicorn app.main:app --host 0.0.0.0 --port 8000`

### 6.4 Frontend Dockerfile (multi-stage)

- **Builder**: `node:20-alpine`, installs deps, builds with `VITE_API_URL=/api/v1`
- **Runner**: `nginx:1.27-alpine`, serves built static files
- Nginx proxies `/api/v1/` to `backend:8000`

### 6.5 Nginx Config

- Serves SPA with fallback: `try_files $uri $uri/ /index.html`
- Proxies `/api/v1/` to `http://backend:8000/api/v1/`
- Gzip compression enabled for CSS/JS/JSON/SVG

### 6.6 Local Development

```powershell
# Backend (requires venv + Ollama running locally)
cd backend
.\venv\Scripts\python -m uvicorn app.main:app --reload --port 8000

# Frontend (dev server with hot reload)
cd frontend
npm run dev    # Starts on :5173, proxies /api to localhost:8000
```

### 6.7 Production via Docker

```powershell
# Build and start all services
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

# View logs
docker compose logs -f backend
docker compose logs -f frontend

# Stop everything
docker compose down

# Reset databases (removes volumes)
docker compose down -v
```

---

## 7. Configuration

### 7.1 Environment Variables

| Variable | Default | Service | Purpose |
|----------|---------|---------|---------|
| `SECRET_KEY` | dev-secret-key... | Backend | JWT signing key |
| `POSTGRES_PASSWORD` | postgres | Postgres | DB password |
| `REDIS_PASSWORD` | (empty) | Redis | Redis password |
| `DATABASE_URL` | postgresql+asyncpg://... | Backend | DB connection string |
| `REDIS_URL` | redis://localhost:6379/0 | Backend | Redis connection string |
| `OLLAMA_BASE_URL` | http://localhost:11434 | Backend | Ollama endpoint |
| `OLLAMA_MODEL` | llama3.2 | Backend | Model for generation |
| `EMBEDDING_MODEL` | nomic-embed-text | Backend | Model for embeddings |
| `LLM_PROVIDER` | ollama | Backend | `ollama` or `openai` |
| `OPENAI_API_KEY` | (empty) | Backend | OpenAI key (if provider=openai) |
| `VITE_API_URL` | /api/v1 | Frontend | API base URL (relative via nginx proxy) |

### 7.2 Python Dependencies

Key packages: fastapi, uvicorn, sqlalchemy 2.0, asyncpg, pgvector, redis, httpx, python-jose, passlib[argon2], structlog, pdfplumber, markdown, langgraph, langchain, langchain-ollama, langchain-openai, prometheus-client

### 7.3 Frontend Dependencies

React 18, react-router-dom 6, lucide-react, tailwindcss 3, vite 5, typescript 5

---

## 8. Security

- **JWT Auth**: Access token (30 min) + refresh token (7 days)
- **Password Hashing**: Argon2 via passlib
- **API Keys**: Hashed storage, prefix-based identification
- **CORS**: Configurable origins, default allows dev ports
- **Non-root user**: Backend and frontend run as non-root in containers
- **HITL Approval**: Destructive/deploy actions require manual approval via web UI

---

## 9. Key Architectural Decisions

| Decision | Rationale |
|----------|-----------|
| **Planner/WorkflowEngine split** | Planner reasons and produces ExecutionPlan; WorkflowEngine orchestrates only. Clear separation of concerns. |
| **DAG execution via topological sort** | Independent steps run in parallel. Kahn's algorithm. |
| **CapabilityRegistry as single dispatch point** | No separate executor layer. Adapters normalize all execution types (agent, MCP, REST, Python) at registration time. |
| **No global singleton** | CapabilityRegistry populated per-request in factory function. |
| **Ollama on host** | Avoid GPU passthrough complexity. Container connects via host.docker.internal. |
| **step_input in ProjectContext** | Only difference between agent and MCP dispatch — MCP tools need step-specific params. |
| **Plain-text prompts + JSON parsing** | Keeps LLM calls simple. No structured output formats. |
| **pgvector for embeddings** | Native PostgreSQL extension — no vector DB lock-in. |
| **structlog for logging** | Structured JSON logs for production observability. |
| **Prometheus metrics** | Counter (requests), Histogram (latency), Gauge (active runs) built into every endpoint. |

---

## 10. CI/CD (`.github/workflows/`)

| Workflow | Purpose |
|----------|---------|
| `ci.yml` | Run on push — lint, type-check, test |
| `deploy.yml` | CD pipeline — build images, push to registry, deploy to server |

---

## 11. Project History (task progression)

| File | Status | Content |
|------|--------|---------|
| `task.md` | ✅ Complete | Original project spec |
| `task_v1.md` | ✅ Complete | V1 milestones |
| `task_v2.md` | ✅ Complete (7 milestones) | Planner-centric migration |
| `task_v3.md` | ✅ M1 complete | Generic adapter architecture (CapabilityRegistry evolution) |
| `AGENTS.md` | ✅ Current | Agent architecture reference |

### Milestones Achieved (task_v2.md)
1. **M1** — ExecutionPlan dataclasses + CapabilityRegistry + PlanValidator
2. **M2** — ExecutionRuntime (retries, timeout, cancellation, telemetry)
3. **M3** — WorkflowEngine consumes ExecutionPlan via topological sort
4. **M4** — IntentRouter returns ExecutionPlan; PlannerAgent.plan() no side effects
5. **M5** — HITL persistence + approval endpoints + resume flow
6. **M6** — Chat routing fix + repo agent fix + frontend fixes
7. **M7** — Cleanup: config constants, logging, 17 unused endpoints removed

### Milestones Achieved (task_v3.md)
1. **M1** — Generic adapter architecture: execution_adapters.py, CapabilityRegistry extended, MCP tools wired via adapters, step_input in ProjectContext

---

## 12. Quick Start

```powershell
# Prerequisites: Docker Desktop + Ollama (with models pulled)

# 1. Clone and set up
cd ageis-ai

# 2. Start services
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

# 3. Open browser
# Local:    http://localhost
# Remote:   cloudflared tunnel --url http://localhost:80

# 4. Register an account at /register
# 5. Create a project, add a repository, explore agents
```
