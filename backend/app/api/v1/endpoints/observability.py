from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.di import get_db_session
from app.services.observability import ObservabilityService, get_observability_service

router = APIRouter(prefix="/observability", tags=["observability"])


@router.get("/metrics")
async def get_metrics(
    db: AsyncSession = Depends(get_db_session),
    service: ObservabilityService = Depends(get_observability_service),
):
    """Get Prometheus metrics."""
    metrics = await service.get_metrics()
    return metrics


@router.get("/tracing")
async def get_tracing(
    run_id: str = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db_session),
    service: ObservabilityService = Depends(get_observability_service),
):
    """Get tracing data."""
    tracing = await service.get_tracing(run_id, limit)
    return {"tracing": tracing, "count": len(tracing)}


@router.get("/dashboard")
async def dashboard(
    db: AsyncSession = Depends(get_db_session),
    service: ObservabilityService = Depends(get_observability_service),
):
    """Get dashboard data."""
    data = await service.get_dashboard_data()
    return data


@router.post("/record")
async def record_request(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
    service: ObservabilityService = Depends(get_observability_service),
):
    """Record an HTTP request."""
    await service.record_request(
        request.method,
        request.url.path,
        request.headers.get("status", "200"),
        0,
    )
    return {"status": "recorded"}