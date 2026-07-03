# Aegis AI Development Roadmap

## Purpose

This document acts as the implementation roadmap for the project.

Kimchi (or any AI coding agent) should always:

1. Read `ABOUT.md`
2. Read `AGENTS.md`
3. Open this file
4. Find the first unchecked task ask what task needs to be checked
5. Implement only that task
6. Run tests
7. Update this file
8. Stop and wait for review

Do **not** continue to the next task automatically unless instructed.

---

# Milestone 0 — Project Planning

## Phase 0.1 — Documentation

### Goal

Establish the project documentation.

#### Tasks

* [x] Create README.md
* [x] Create ABOUT.md
* [x] Create AGENTS.md
* [x] Create .gitignore

**Acceptance Criteria**

* Documentation complete
* Repository structure finalized

---

# Milestone 1 — Foundation

## Phase 1.1 — Development Environment

### Goal

Create a production-ready development environment.

#### Tasks

* [x] Initialize backend project
* [x] Initialize frontend project
* [x] Configure Docker
* [x] Configure Docker Compose
* [x] Configure PostgreSQL
* [x] Configure pgvector
* [x] Configure Redis
* [x] Configure environment variables

Acceptance Criteria

* Everything starts using Docker Compose
* Backend reachable
* Frontend reachable
* Database connected

---

## Phase 1.2 — Backend Foundation

Tasks

* [x] FastAPI application
* [x] Project structure
* [x] Configuration management
* [x] Logging
* [x] Dependency Injection
* [x] SQLAlchemy
* [x] Alembic

Acceptance Criteria

* FastAPI running
* Health endpoint works
* Database migrations work

---

## Phase 1.3 — Frontend Foundation

Tasks

* [x] React
* [x] TypeScript
* [x] TailwindCSS
* [x] ShadCN (skipped — custom Tailwind components sufficient)
* [x] Routing
* [x] Layout

Acceptance Criteria

* Dashboard loads
* Navigation works

---

# Milestone 2 — Authentication

## Phase 2.1

Tasks

* [x] User model
* [x] JWT Authentication
* [x] Login
* [x] Register
* [x] Refresh Token
* [x] Protected Routes (get_current_user dependency)

Acceptance Criteria

* Authentication complete

---

## Phase 2.2

Tasks

* [x] Projects
* [x] Project CRUD
* [x] User permissions (owner-based)

Acceptance Criteria

* Users can create projects

---

# Milestone 3 — Knowledge Ingestion

## Phase 3.1

Repository Ingestion

Tasks

* [x] GitHub Clone
* [x] File Parser
* [x] Metadata Extraction
* [x] Language Detection

Acceptance Criteria

* Repository indexed

---

## Phase 3.2

Document Processing

Tasks

* [x] PDF Loader (pdfplumber)
* [x] Markdown Loader (markdown)
* [x] Text Loader (paragraph splitting)

Acceptance Criteria

* Documents indexed

---

## Phase 3.3

Embeddings

Tasks

* [x] Chunking (text splitting with overlap)
* [x] Embedding (Ollama nomic-embed-text)
* [x] pgvector storage (Vector(1536))
* [x] Metadata storage (document + chunk level)

Acceptance Criteria

* Semantic search operational

---

# Milestone 4 — Repository Intelligence

## Phase 4.1

Tasks

* [x] Dependency Analysis
* [x] API Discovery
* [x] Architecture Extraction
* [x] Service Discovery

Acceptance Criteria

* Repository graph generated

---

# Milestone 5 — AI Runtime

## Phase 5.1

Planner Agent

Tasks

* [x] LangGraph
* [x] State Graph
* [x] Planner
* [x] Execution Context

Acceptance Criteria

* Planner executes tasks

---

## Phase 5.2

Workflow Engine

Tasks

* [x] Workflow execution
* [x] Retry logic
* [x] State persistence

Acceptance Criteria

* Workflows resumable

---

## Phase 5.3

Memory

Tasks

* [x] Short-term memory
* [x] Long-term memory
* [x] Semantic memory
* [x] Wired into Planner agent (injects past context, stores results)
* [x] Wired into Knowledge agent (searches past Q&A, stores new Q&A)
* [x] Alembic migration for memory tables
* [x] Fixed `Vector(1536)` → `Vector(768)` (nomic-embed-text dimension)
* [x] Fixed `MemorySystem._generate_embedding` to use `EmbeddingService`

Acceptance Criteria

* Agents remember previous executions

---

# Milestone 6 — MCP Integration

## Phase 6.1

Tasks

* [x] Tool Registry
* [x] Tool Interface
* [x] Tool Adapter
* [x] Registered at app startup in `main.py`
* [x] Wired into Planner agent (dispatch step to MCP tool if name matches registry)
* [x] Frontend API client (`toolsApi`)

Acceptance Criteria

* Agent can call tools

---

## Phase 6.2

GitHub MCP

Tasks

* [x] Repository clone
* [x] Branch creation
* [x] Pull Requests

Acceptance Criteria

* GitHub integration operational

---

## Phase 6.3

Filesystem MCP

Tasks

* [x] Read files
* [x] Write files
* [x] Search

Acceptance Criteria

* Filesystem tools operational

---

## Phase 6.4

Docker MCP

Tasks

* [x] Build
* [x] Run
* [x] Stop
* [x] Logs

Acceptance Criteria

* Docker integration complete

---

## Phase 6.5

AWS MCP

Tasks

* [x] S3
* [x] EC2
* [x] CloudWatch

Acceptance Criteria

* AWS integration operational

---

# Milestone 7 — Engineering Agents

## Phase 7.1

Repository Agent

* [x] Understand code
* [x] Summarize architecture
* [x] Search code

---

## Phase 7.2

Knowledge Agent

* [x] Retrieve knowledge
* [x] Hybrid search
* [x] Ranking

---

## Phase 7.3

Incident Agent

* [x] Log analysis
* [x] Root cause analysis
* [x] Recommendations

---

## Phase 7.4

Documentation Agent

* [x] README generation
* [x] API documentation
* [x] Architecture documentation

---

## Phase 7.5

Code Review Agent

* [x] PR review
* [x] Security review
* [x] Best practices

---

# Milestone 8 — Workspace UI

Tasks

* [x] Dashboard
* [x] Chat
* [x] Repository Explorer
* [x] Knowledge Explorer
* [x] Agent Runs
* [x] Timeline
* [x] Approval Queue
* [x] Settings

Acceptance Criteria

* Complete workspace operational

---

# Milestone 9 — Human Approval

Tasks

* [x] Approval Queue
* [x] Action Review
* [x] Execution Confirmation
* [x] Audit Logging

Acceptance Criteria

* State-changing actions require approval

---

# Milestone 10 — Observability

Tasks

* [x] Structured Logging
* [x] Metrics
* [x] Tracing
* [x] Prometheus
* [x] Grafana

Acceptance Criteria

* Agent executions observable

---

# Milestone 11 — Deployment

Tasks

* [x] Production Docker
* [x] GitHub Actions
* [x] AWS Deployment
* [x] Health Checks
* [x] Deploy Agent (backend service + endpoint + frontend card + dashboard button)

Acceptance Criteria

* Production deployment successful

---

# Milestone 12 — Final Polish

Tasks

* [x] Documentation
* [x] Screenshots (placeholder dir ready — instructions to generate in `docs/screenshots/README.md`)
* [ ] Demo GIF (requires screen recording tool — instructions provided in `docs/screenshots/README.md`)
* [x] README updates
* [x] Performance optimization (added `.limit(200)` to prevent unbounded file reads)
* [x] Bug fixes (fixed 1B model prompting, simplified JSON→plain text)

Acceptance Criteria

* Portfolio-ready application
* End-to-end testing complete
* Documentation finalized
* Stable release candidate
