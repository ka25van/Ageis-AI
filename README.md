# Aegis AI

**Agentic AI Engineering & AIOps Platform** — Ingest repositories, analyze code via LLM agents, manage engineering knowledge, monitor alerts with AI-driven root cause analysis. All runs locally via Docker + Ollama.

---

## Table of Contents

- [Architecture (HLD)](#architecture-hld)
- [Architecture (LLD)](#architecture-lld)
- [Component Details](#component-details)
- [Tech Stack](#tech-stack)
- [Quick Start (Docker)](#quick-start-docker)
- [Quick Start (Dev Mode)](#quick-start-dev-mode)
- [API Overview](#api-overview)
- [Agents](#agents)
- [Project Structure](#project-structure)

---

## Architecture (HLD)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           Browser (:80 / :5173)                         │
│                    React SPA — 11 pages, auto-refresh                   │
└────────────────────────────┬────────────────────────────────────────────┘
                             │ HTTP
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         Nginx (frontend container)                      │
│  Serves static SPA · try_files → index.html · /api/v1/ → backend:8000  │
│  proxy_read_timeout 300s (prevents 504 on slow LLM calls)               │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     FastAPI Backend (:8000)                             │
│                                                                         │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌───────────────┐    │
│  │   Auth     │  │  Projects  │  │  Repos     │  │  Documents    │    │
│  │  /auth     │  │ /projects  │  │/repositories│  │ /documents    │    │
│  └────────────┘  └────────────┘  └────────────┘  └───────────────┘    │
│                                                                         │
│  ┌────────────────────────────────────────────────────────────────┐    │
│  │                  Agent System                                  │    │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐         │    │
│  │  │Intent    │→│Plan      │→│Workflow  │→│Capability│→ Result │    │
│  │  │Router    │ │Validator │ │Engine    │ │Registry  │         │    │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘         │    │
│  │                           │                                   │    │
│  │         ┌─────────────────┼──────────────────┐               │    │
│  │         ▼                 ▼                  ▼               │    │
│  │  ┌──────────┐  ┌──────────────────┐  ┌──────────────┐       │    │
│  │  │ 6 Agents │  │ 15 MCP Tools     │  │ 2 Stubs      │       │    │
│  │  │(process) │  │(clone, read,     │  │(rest, python)│       │    │
│  │  └──────────┘  │ docker, aws)     │  └──────────────┘       │    │
│  │                └──────────────────┘                         │    │
│  └────────────────────────────────────────────────────────────────┘    │
│                                                                         │
│  ┌──────────────────────┐  ┌──────────────────────┐                    │
│  │   Memory System      │  │   Observability      │                    │
│  │  Short-term (AgentStep)│ │  Prometheus metrics  │                    │
│  │  Long-term (TTL KV)   │  │  Tracing (AgentStep) │                    │
│  │  Semantic (pgvector)  │  │  Dashboard (SQL agg) │                    │
│  └──────────────────────┘  └──────────────────────┘                    │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  AIOps — Alert Pipeline                                        │   │
│  │  /alerts/webhook ← Prometheus Alertmanager                     │   │
│  │    → store in SemanticMemory                                   │   │
│  │    → asyncio background LLM analysis (root cause, remediation)  │   │
│  │    → store alert_analysis in SemanticMemory                     │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
              ┌──────────────┼──────────────────┐
              │              │                  │
              ▼              ▼                  ▼
┌────────────────┐ ┌──────────────┐ ┌──────────────────┐
│  PostgreSQL    │ │    Redis     │ │   Prometheus     │
│  :5432         │ │   :6379      │ │   :9090          │
│  pgvector      │ │   Cache      │ │  scrapes         │
│  12 tables     │ │              │ │  /metrics every  │
│                 │ │              │ │  15s             │
└────────────────┘ └──────────────┘ └──────────────────┘
                             │
                             ▼
                  ┌──────────────────────┐
                  │  Ollama (host)       │
                  │  :11434              │
                  │  llama3.2 (chat)     │
                  │  nomic-embed-text    │
                  │  (embeddings)        │
                  └──────────────────────┘
```

---

## Architecture (LLD)

### Request Flow — Planner Route

```
POST /api/v1/planner/route  { message: "find errors in my repo" }
        │
        ▼
IntentRouter.KEYWORD_RULES                  [backend/app/services/planner.py:175]
  - "error", "crash", "incident" → incident agent
  - falls back to LLM classification if no keyword match
        │
        ▼
Returns ExecutionPlan dataclass              [backend/app/core/execution_plan.py]
  intent: "incident"
  steps: [ExecutionStep(id="step-1", capability="incident", ...)]
        │
        ▼
PlanValidator.validate()                      [backend/app/services/plan_validator.py]
  1. DFS cycle detection on depends_on graph
  2. Capability existence check in CapabilityRegistry
  3. Orphan reference check
  4. Approval consistency check
        │
        ▼
WorkflowEngine.execute_plan()                [backend/app/services/workflow_engine.py]
  1. Topological sort (Kahn's algorithm)
  2. For each step (topological order):
     a. _build_context_for_step()
        - queries DB for repos, docs, files
        - generates embeddings for query
        - searches semantic memory for context
        (or uses dataclasses.replace from EngineeringContext if in Tier 1 path)
     b. registry.resolve(step.capability)     [backend/app/services/capability_registry.py]
        → returns Capability(name, executor, execution_type)
     c. Create AgentStep record (status="running")
     d. ExecutionRuntime.execute_step()        [backend/app/services/workflow_engine.py:68]
        - retries with backoff if RetryPolicy defined
        - enforces timeout_seconds
     e. Record result: step_record.status = "completed"|"failed"
     f. Handle rollback if step.rollback_step set
  3. Merge step_results into response
```

### Memory Flow — Three-Tier

```
┌─────────────────────────────────────────────────────────────────┐
│  Short-Term (per-run, AgentStep table)                          │
│  store:  MemorySystem.store_short_term(run_id, key, value)     │
│  get:    MemorySystem.get_short_term(run_id, key)              │
│  used:   WorkflowEngine — current step context                  │
│  TTL:    Per run (cleaned when run completes)                   │
├─────────────────────────────────────────────────────────────────┤
│  Long-Term (key-value, LongTermMemory table)                    │
│  store:  MemorySystem.store_long_term(user_id, key, value, ttl) │
│  get:    MemorySystem.get_long_term(user_id, key)               │
│  used:   Cross-session preferences, reusable data               │
│  TTL:    Configurable (default 30 days)                         │
├─────────────────────────────────────────────────────────────────┤
│  Semantic (vector, SemanticMemory table + pgvector)             │
│  store:  MemorySystem.store_semantic(text, embedding, metadata) │
│  search: MemorySystem.search_semantic(query, limit, threshold)  │
│  used:   Alerts, planner context injection, knowledge Q&A       │
│  TTL:    Forever                                                │
└─────────────────────────────────────────────────────────────────┘
```

### Alert Pipeline Flow

```
Prometheus Alertmanager
  │ POST /api/v1/alerts/webhook  [backend/app/api/v1/endpoints/alerts.py:102]
  │ { status, alerts: [{ labels, annotations }], ... }
  ▼
alert_webhook()
  1. record_request() → increment http_requests_total Counter
  2. Embed alert body via EmbeddingService
     POST host.docker.internal:11434/api/embeddings (nomic-embed-text)
  3. Store in SemanticMemory:
     text = "Alert: {summary}\n{description}"
     metadata = { type:"alert", status:"firing"|"resolved", alert_names:[], processing:"pending" }
  4. Return immediate response: { status:"received", processing:"in_background" }
  5. asyncio.create_task(_process_alert_background(body, summary, desc))
        │
        ▼ (fire-and-forget)
  _process_alert_background()               [backend/app/api/v1/endpoints/alerts.py:43]
    1. LLMService.generate(system_prompt, alert_body)
       System: "Senior SRE analyzing Prometheus alert — return JSON"
       Timeout: 120s
    2. _extract_json(raw)                   [handles markdown-wrapped JSON]
    3. Parse: root_cause, impact, severity, remediation_steps, prevention, confidence
    4. Open fresh DB session (async_session_maker)
    5. Embed analysis → store in SemanticMemory:
       text = "Alert Analysis: {root_cause}"
       metadata = { type:"alert_analysis", severity, root_cause, confidence, has_remediation }
```

### MCP Tool Dispatch

```
Planner Step with capability="clone_repository"
        │
        ▼
CapabilityRegistry.resolve("clone_repository")
        │
        ▼
adapt_mcp("clone_repository", mcp_registry)    [backend/app/services/execution_adapters.py:28]
  Wraps:  mcp_registry.execute("clone_repository", context.step_input)
            │
            ▼
ToolRegistry.execute(name, args)               [backend/app/mcp/registry.py]
  Looks up handler
            │
            ▼
GitHubMCP.clone_repository(args)               [backend/app/mcp/github.py:74]
  subprocess.run(["git", "clone", "--depth", "1", "--branch", branch, url, dir])
            │
            ▼
Returns AgentResult(result={stdout}, confidence=1.0, ...)
```

---

## Component Details

### Backend (`backend/app/`)

| Layer | Path | Purpose |
|-------|------|---------|
| Entrypoint | `main.py` | App factory, middleware, CORS, imports MCP modules, registers routers |
| Config | `core/config.py` | Pydantic Settings — reads `.env`, all defaults |
| DB Session | `db/session.py` | `create_async_engine(pool_pre_ping=True, pool_recycle=3600)`, `async_session_maker` |
| Models | `models/` | 12 SQLAlchemy ORM tables (user, project, repo, doc, agent, memory) |
| Endpoints | `api/v1/endpoints/` | 68+ routes across 15 routers |
| Services | `services/` | Agents, LLM, embeddings, memory, observability, workflow engine |
| MCP | `mcp/` | GitHub (3), Filesystem (4), Docker (4), AWS (4) — 15 tools |
| Execution | `services/workflow_engine.py` | DAG execution via topological sort, step dispatch |
| Planning | `services/planner.py` | IntentRouter (keyword + LLM fallback), PlannerAgent |
| AIOps | `api/v1/endpoints/alerts.py` | Alert webhook, background LLM analysis, history, stats |

### Frontend (`frontend/src/`)

| Path | Purpose |
|------|---------|
| `lib/api.ts` | Typed fetch wrapper — JWT auth, auto-refresh, 13 API objects |
| `lib/auth.tsx` | Auth context — login state, token management |
| `pages/Dashboard.tsx` | Stats: projects, repos, recent runs |
| `pages/Projects.tsx` | CRUD project management |
| `pages/Repositories.tsx` | Repository list + ingest trigger |
| `pages/Knowledge.tsx` | Document browser, chunk viewer, semantic search |
| `pages/Agents.tsx` | Agent action cards |
| `pages/Chat.tsx` | Conversational planner |
| `pages/OpsDashboard.tsx` | AIOps: agent runs, traces, alerts, analyses (auto-refresh 15s) |
| `pages/ApprovalQueue.tsx` | HITL approval/reject |
| `pages/Settings.tsx` | Profile, password, API keys |

---

## Tech Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Frontend | React, TypeScript, TailwindCSS, Vite | React 18, TS 5.5 |
| Backend | FastAPI, Python, Uvicorn | Python 3.11, FastAPI 0.139 |
| AI Runtime | LangGraph, LangChain | LangGraph 1.2, LangChain 1.3 |
| LLM | Ollama (llama3.2, nomic-embed-text) | Host, not containerized |
| Database | PostgreSQL 16 + pgvector | Docker |
| Cache | Redis 7 | Docker |
| Observability | Prometheus, prometheus_client | Docker |
| Orchestration | Docker Compose | — |
| Auth | JWT (python-jose), Argon2 (passlib) | — |

---

## Quick Start (Docker)

### Prerequisites

- Docker Desktop
- [Ollama](https://ollama.ai) installed locally with models pulled

```powershell
# Pull LLM models (one-time)
ollama pull llama3.2
ollama pull nomic-embed-text
```

### Start All Services

```powershell
# Build and start everything
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

# Check status
docker compose ps

# Watch logs
docker compose logs -f backend
docker compose logs -f frontend
```

### Open Browser

```
http://localhost
```

1. Register an account at `/register`
2. Create a project at `/projects`
3. Add a repository (GitHub URL) at `/repositories`
4. Run agents at `/agents` or ask questions at `/chat`
5. Monitor at `/ops` (Ops Dashboard with alerts, traces, metrics)

### Test Alert Pipeline

```powershell
$body = @'
{
  "status":"firing",
  "alerts":[
    {
      "status":"firing",
      "labels":{"alertname":"HighCPU","severity":"critical"},
      "annotations":{"summary":"CPU > 95% on prod-web-01","description":"CPU at 97% for 10 minutes"}
    }
  ],
  "commonAnnotations":{"summary":"CPU > 95% on prod-web-01"}
}
'@
$body | Set-Content -Path "$env:TEMP\alert.json"
curl.exe -s -X POST http://localhost:8000/api/v1/alerts/webhook `
  -H "Content-Type: application/json" -d "@$env:TEMP\alert.json"
```

Check `/ops` — raw alert appears immediately, LLM analysis appears ~60s later.

### Stop Everything

```powershell
docker compose down

# To reset databases (removes all data)
docker compose down -v
```

---

## Quick Start (Dev Mode)

### 1. Start Infrastructure

```powershell
docker compose up -d postgres redis prometheus
```

### 2. Backend

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 3. Frontend

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

---

## API Overview

All endpoints under `/api/v1/`. Full details in `ABOUT.md`.

| Group | Prefix | Endpoints |
|-------|--------|-----------|
| Health | `/health` | 3 (root, db, redis) |
| Auth | `/auth` | 6 (register, login, refresh, me, change-password, api-keys) |
| Projects | `/projects` | 5 (CRUD) |
| Repositories | `/repositories` | 6 (CRUD + ingest + files) |
| Documents | `/documents` | 6 (upload, text, list, get, chunks, delete) |
| Embeddings | `/embeddings` | 4 (generate doc/repo, search, hybrid-search) |
| Planner | `/planner` | 5 (plan, route, resume, get run, get steps) |
| Memory | `/memory` | 11 (short/long/semantic/conversation/summary) |
| Alerts | `/alerts` | 3 (webhook, history, stats) |
| Observability | `/observability` | 4 (metrics, tracing, dashboard, record) |
| Tools (MCP) | `/tools` | 3 (list, get, execute) |
| Agents (6) | `/repo-agent`, `/knowledge`, `/incidents`, `/docs`, `/code-review`, `/deploy` | 14 total |

---

## Agents

| Agent | Capability | Input | Output | File |
|-------|-----------|-------|--------|------|
| **Repository** | `repository` | project_id | Architecture, tech stack, design patterns, recommendations | `services/repository_agent.py` |
| **Knowledge** | `knowledge` | project_id + query | Semantic search results + generative Q&A with memory context | `services/knowledge_agent.py` |
| **Incident** | `incident` | repository_id | Error keyword scanning, root cause, remediation | `services/incident_agent.py` |
| **Documentation** | `documentation` | repository_id | README, API docs, architecture docs in markdown | `services/documentation_agent.py` |
| **Code Review** | `code_review` | repository_id | Security audit, code quality, best practices | `services/code_review_agent.py` |
| **Deploy** | `deploy` | repository_id | Docker/CI/CD/infra analysis | `services/deploy_agent.py` |
| **Planner** | (meta) | project_id + task | Decomposes into ExecutionPlan DAG, routes to agents | `services/planner.py` |

---

## Project Structure

```
├── ABOUT.md                  # Full application overview (pin-to-pin)
├── AGENTS.md                 # Agent architecture reference
├── README.md                 # This file
├── docker-compose.yml        # Local dev — postgres, redis, backend, frontend, prometheus
├── docker-compose.prod.yml   # Production overlay
│
├── backend/
│   ├── Dockerfile             # Multi-stage: builder (wheel) + runner (non-root)
│   ├── pyproject.toml         # Python deps
│   └── app/
│       ├── main.py            # App factory, middleware, router registration
│       ├── alembic/           # DB migrations
│       ├── core/
│       │   ├── config.py      # Pydantic Settings
│       │   ├── di.py          # FastAPI Depends helpers
│       │   ├── task.py        # Task dataclass (PROMETHEUS, INCIDENT sources)
│       │   └── execution_plan.py  # ExecutionPlan, ExecutionStep, RetryPolicy
│       ├── db/
│       │   ├── base.py        # SQLAlchemy declarative Base
│       │   └── session.py     # Engine + async_session_maker
│       ├── models/
│       │   ├── user.py        # users, api_keys
│       │   ├── project.py     # projects, repositories, repository_files
│       │   ├── document.py    # documents, document_chunks (VECTOR)
│       │   ├── agent.py       # agent_runs, agent_steps, approvals
│       │   └── memory.py      # long_term_memory, semantic_memory (VECTOR)
│       ├── api/v1/endpoints/   # 15 router files
│       ├── services/
│       │   ├── planner.py         # IntentRouter, PlannerAgent
│       │   ├── workflow_engine.py # DAG execution, step dispatch
│       │   ├── capability_registry.py  # Single dispatch point
│       │   ├── execution_adapters.py   # adapt_agent/mcp/rest/python
│       │   ├── plan_validator.py       # DAG validation
│       │   ├── context_builder.py      # ProjectContext with step_input
│       │   ├── llm_service.py         # LangChain ChatOllama/ChatOpenAI
│       │   ├── embeddings.py          # Ollama embed + pgvector search
│       │   ├── memory.py              # Three-tier MemorySystem
│       │   ├── observability.py       # Prometheus metrics + DB queries
│       │   └── *_agent.py            # 6 agent implementations
│       └── mcp/
│           ├── registry.py    # ToolRegistry singleton
│           ├── interface.py   # ToolInterface for /tools API
│           ├── github.py      # 3 tools (git subprocess)
│           ├── filesystem.py  # 4 tools (file I/O)
│           ├── docker.py      # 4 tools (docker CLI)
│           └── aws.py         # 4 tools (aws CLI)
│
├── frontend/
│   ├── Dockerfile             # Node build → nginx serve
│   ├── nginx.conf             # SPA fallback + /api/v1/ proxy (300s timeout)
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   └── src/
│       ├── App.tsx            # Router (11 routes)
│       ├── lib/
│       │   ├── api.ts         # Typed fetch client (13 API objects)
│       │   └── auth.tsx       # Auth context + JWT management
│       └── pages/             # 11 page components
│
├── infra/
│   ├── prometheus.yml         # Scrape config (targets backend:8000)
│   ├── nginx.prod.conf        # Production Nginx with SSL
│   ├── deploy.sh              # Production deployment script
│   ├── docker-compose.aws.yml # AWS ECS-ready
│   ├── init-db.sql            # pgvector + uuid-ossp
│   └── .env.example           # Environment template
```

---

## License

MIT
