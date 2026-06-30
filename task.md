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

* [ ] GitHub Clone
* [ ] File Parser
* [ ] Metadata Extraction
* [ ] Language Detection

Acceptance Criteria

* Repository indexed

---

## Phase 3.2

Document Processing

Tasks

* [ ] PDF Loader
* [ ] Markdown Loader
* [ ] Text Loader

Acceptance Criteria

* Documents indexed

---

## Phase 3.3

Embeddings

Tasks

* [ ] Chunking
* [ ] Embedding
* [ ] pgvector storage
* [ ] Metadata storage

Acceptance Criteria

* Semantic search operational

---

# Milestone 4 — Repository Intelligence

## Phase 4.1

Tasks

* [ ] Dependency Analysis
* [ ] API Discovery
* [ ] Architecture Extraction
* [ ] Service Discovery

Acceptance Criteria

* Repository graph generated

---

# Milestone 5 — AI Runtime

## Phase 5.1

Planner Agent

Tasks

* [ ] LangGraph
* [ ] State Graph
* [ ] Planner
* [ ] Execution Context

Acceptance Criteria

* Planner executes tasks

---

## Phase 5.2

Workflow Engine

Tasks

* [ ] Workflow execution
* [ ] Retry logic
* [ ] State persistence

Acceptance Criteria

* Workflows resumable

---

## Phase 5.3

Memory

Tasks

* [ ] Short-term memory
* [ ] Long-term memory
* [ ] Semantic memory

Acceptance Criteria

* Agents remember previous executions

---

# Milestone 6 — MCP Integration

## Phase 6.1

Tasks

* [ ] Tool Registry
* [ ] Tool Interface
* [ ] Tool Adapter

Acceptance Criteria

* Agent can call tools

---

## Phase 6.2

GitHub MCP

Tasks

* [ ] Repository clone
* [ ] Branch creation
* [ ] Pull Requests

Acceptance Criteria

* GitHub integration operational

---

## Phase 6.3

Filesystem MCP

Tasks

* [ ] Read files
* [ ] Write files
* [ ] Search

Acceptance Criteria

* Filesystem tools operational

---

## Phase 6.4

Docker MCP

Tasks

* [ ] Build
* [ ] Run
* [ ] Stop
* [ ] Logs

Acceptance Criteria

* Docker integration complete

---

## Phase 6.5

AWS MCP

Tasks

* [ ] S3
* [ ] EC2
* [ ] CloudWatch

Acceptance Criteria

* AWS integration operational

---

# Milestone 7 — Engineering Agents

## Phase 7.1

Repository Agent

* [ ] Understand code
* [ ] Summarize architecture
* [ ] Search code

---

## Phase 7.2

Knowledge Agent

* [ ] Retrieve knowledge
* [ ] Hybrid search
* [ ] Ranking

---

## Phase 7.3

Incident Agent

* [ ] Log analysis
* [ ] Root cause analysis
* [ ] Recommendations

---

## Phase 7.4

Documentation Agent

* [ ] README generation
* [ ] API documentation
* [ ] Architecture documentation

---

## Phase 7.5

Code Review Agent

* [ ] PR review
* [ ] Security review
* [ ] Best practices

---

# Milestone 8 — Workspace UI

Tasks

* [ ] Dashboard
* [ ] Chat
* [ ] Repository Explorer
* [ ] Knowledge Explorer
* [ ] Agent Runs
* [ ] Timeline
* [ ] Approval Queue
* [ ] Settings

Acceptance Criteria

* Complete workspace operational

---

# Milestone 9 — Human Approval

Tasks

* [ ] Approval Queue
* [ ] Action Review
* [ ] Execution Confirmation
* [ ] Audit Logging

Acceptance Criteria

* State-changing actions require approval

---

# Milestone 10 — Observability

Tasks

* [ ] Structured Logging
* [ ] Metrics
* [ ] Tracing
* [ ] Prometheus
* [ ] Grafana

Acceptance Criteria

* Agent executions observable

---

# Milestone 11 — Deployment

Tasks

* [ ] Production Docker
* [ ] GitHub Actions
* [ ] AWS Deployment
* [ ] Health Checks

Acceptance Criteria

* Production deployment successful

---

# Milestone 12 — Final Polish

Tasks

* [ ] Documentation
* [ ] Screenshots
* [ ] Demo GIF
* [ ] README updates
* [ ] Performance optimization
* [ ] Bug fixes

Acceptance Criteria

* Portfolio-ready application
* End-to-end testing complete
* Documentation finalized
* Stable release candidate
