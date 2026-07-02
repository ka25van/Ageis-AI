# Aegis AI

**AI-Powered Engineering Platform** — Understand, review, document, and search any codebase using local AI agents.

## Features

- **6 AI Agents** — Repository, Knowledge, Incident, Documentation, Code Review, and Planner agents analyze your code with Ollama-powered LLMs
- **Repository Ingestion** — Clone GitHub repos, chunk files, generate embeddings (pgvector), and build a searchable knowledge base
- **Semantic Search** — Hybrid search (vector + keyword) across all indexed documents and code chunks
- **Human-in-the-Loop** — State-changing actions require approval before execution
- **Workspace UI** — Dashboard, Projects, Repositories, Knowledge explorer, Agent runs, Settings

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React, TypeScript, TailwindCSS, Vite |
| Backend | FastAPI, Python 3.11+, SQLAlchemy, Alembic |
| AI Runtime | LangGraph, LangChain, Ollama (local LLMs) |
| Database | PostgreSQL + pgvector, Redis |
| Infrastructure | Docker, GitHub Actions, AWS |

## Architecture

```
┌─────────┐     ┌──────────┐     ┌───────────┐     ┌────────────┐
│  React  │ ──▶ │  FastAPI │ ──▶ │ LangGraph │ ──▶ │   Agents   │
│  UI     │     │  Backend │     │  Runtime  │     │ ─────────  │
└─────────┘     └──────────┘     └───────────┘     │ Repository │
                                                   │ Knowledge  │
                   ┌────────────┐                  │ Incident   │
                   │ PostgreSQL │                  │ Docs       │
                   │ + pgvector │                  │ CodeReview │
                   │ + Redis    │                  │ Planner    │
                   └────────────┘                  └────────────┘
```

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 20+
- Docker (for PostgreSQL + Redis)
- Ollama (for local LLMs)

### 1. Start infrastructure

```bash
docker compose up -d postgres redis
```

### 2. Pull LLM models

```bash
ollama pull llama3.2
ollama pull nomic-embed-text
```

### 3. Backend setup

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate     # Windows
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 4. Frontend setup

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 — register an account, create a project, connect a repository, and run agents.

### Docker (full stack)

```bash
docker compose up -d
```

This starts PostgreSQL, Redis, Ollama, backend, and frontend. Pull models inside the Ollama container:

```bash
docker exec aegis-ollama ollama pull llama3.2
docker exec aegis-ollama ollama pull nomic-embed-text
```

## Agents

Each agent uses Ollama + LangChain to analyze repository data:

| Agent | Input | Output |
|-------|-------|--------|
| **Repository** | repository_id | Architecture, tech stack, components, recommendations |
| **Knowledge** | project_id + query | Semantic search results + generative Q&A |
| **Incident** | repository_id | Error pattern analysis, root causes, remediation |
| **Documentation** | repository_id | README, API docs, architecture docs |
| **Code Review** | repository_id | Security issues, best practices, code quality |
| **Planner** | project_id + task | Multi-step task decomposition with LLM |

## Screenshots

<!-- TODO: Add screenshots
![Dashboard](docs/screenshots/dashboard.png)
![Agents](docs/screenshots/agents.png)
![Knowledge](docs/screenshots/knowledge.png)
-->

## Project Structure

```
├── backend/          # FastAPI application
│   ├── app/
│   │   ├── api/      # REST endpoints
│   │   ├── core/     # Config, DI, logging
│   │   ├── db/       # Database session + base
│   │   ├── models/   # SQLAlchemy models
│   │   └── services/ # Business logic + agents
│   ├── Dockerfile
│   └── pyproject.toml
├── frontend/         # React + TypeScript
│   ├── src/
│   │   ├── lib/      # API client, auth context
│   │   └── pages/    # Dashboard, Projects, Agents, etc.
│   ├── Dockerfile
│   └── nginx.conf
├── infra/            # Production deployment configs
├── docker-compose.yml
└── task.md           # Development roadmap
```

## Environment Variables

See `infra/.env.example` for all options. Key ones:

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `ollama` | `ollama` or `openai` |
| `OLLAMA_MODEL` | `llama3.2` | Ollama model name |
| `OPENAI_API_KEY` | — | Required if using OpenAI |
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/aegis` | PostgreSQL connection |
| `SECRET_KEY` | `dev-secret-key-...` | JWT signing key (change in production) |

## Deployment

See [infra/deploy.sh](infra/deploy.sh) and [.github/workflows](.github/workflows) for GitHub Actions CI/CD and AWS deployment.

```bash
# Production Docker
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

## License

MIT
