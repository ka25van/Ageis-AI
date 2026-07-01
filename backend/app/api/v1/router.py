from fastapi import APIRouter

from app.api.v1.endpoints import health, auth, projects, repositories, documents, embeddings, repository_analysis, planner, workflows, memory_api, tools, repository_agent, knowledge_agent, incident_agent, documentation_agent, code_review, approvals, observability

api_router = APIRouter()

api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(auth.router, prefix="", tags=["auth"])
api_router.include_router(projects.router, prefix="", tags=["projects"])
api_router.include_router(repositories.router, prefix="/repositories", tags=["repositories"])
api_router.include_router(documents.router, prefix="/documents", tags=["documents"])
api_router.include_router(embeddings.router, prefix="/embeddings", tags=["embeddings"])
api_router.include_router(repository_analysis.router, prefix="/analyze", tags=["analysis"])
api_router.include_router(planner.router, prefix="/planner", tags=["planner"])
api_router.include_router(workflows.router, prefix="/workflows", tags=["workflows"])
api_router.include_router(memory_api.router, prefix="/memory", tags=["memory"])
api_router.include_router(tools.router, prefix="/tools", tags=["tools"])
api_router.include_router(repository_agent.router, prefix="/repo-agent", tags=["repository-agent"])
api_router.include_router(knowledge_agent.router, prefix="/knowledge", tags=["knowledge"])
api_router.include_router(incident_agent.router, prefix="/incidents", tags=["incidents"])
api_router.include_router(documentation_agent.router, prefix="/docs", tags=["documentation"])
api_router.include_router(code_review.router, prefix="/code-review", tags=["code-review"])
api_router.include_router(approvals.router, prefix="/approvals", tags=["approvals"])
api_router.include_router(observability.router, prefix="/observability", tags=["observability"])