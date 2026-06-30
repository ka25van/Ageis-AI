from fastapi import APIRouter

from app.api.v1.endpoints import health, auth, projects

api_router = APIRouter()

api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(auth.router, prefix="", tags=["auth"])
api_router.include_router(projects.router, prefix="", tags=["projects"])