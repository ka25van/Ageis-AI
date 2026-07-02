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
