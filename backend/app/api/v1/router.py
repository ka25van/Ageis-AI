from fastapi import APIRouter

from app.api.v1.endpoints import health, auth, projects, repositories, documents, embeddings, repository_analysis, planner, workflows, memory_api, tools

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