from typing import Dict, Optional
from datetime import datetime, timedelta
import time

from fastapi import Depends

from prometheus_client import Counter, Histogram, Gauge, generate_latest, REGISTRY
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import AgentRun, AgentStep
from app.core.di import get_db_session

# Prometheus metrics
http_requests_total = Counter("http_requests_total", "Total HTTP requests", ["method", "endpoint", "status"])
http_request_duration_seconds = Histogram("http_request_duration_seconds", "HTTP request duration", ["method", "endpoint"])
active_runs = Gauge("active_runs", "Currently active agent runs")
total_errors = Counter("total_errors", "Total errors encountered", ["type"])


class ObservabilityService:
    """Service for collecting metrics, tracing, and Prometheus data."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def record_request(self, method: str, endpoint: str, status: int, duration_ms: float):
        """Record HTTP request metrics."""
        http_requests_total.labels(method=method, endpoint=endpoint, status=status).inc()
        http_request_duration_seconds.labels(method=method, endpoint=endpoint).observe(duration_ms / 1000)

    async def get_metrics(self) -> str:
        """Get Prometheus metrics in text format."""
        return generate_latest(REGISTRY).decode("utf-8")

    async def get_tracing(self, run_id: str = None, limit: int = 50) -> list:
        """Get tracing data for agent runs."""
        query = select(AgentStep).order_by(AgentStep.created_at.desc()).limit(limit)
        if run_id:
            query = query.where(AgentStep.run_id == run_id)

        result = await self.db.execute(query)
        steps = result.scalars().all()

        return [
            {
                "id": str(s.id),
                "run_id": str(s.run_id),
                "step_type": s.step_type,
                "name": s.name,
                "status": s.status,
                "duration_ms": s.duration_ms,
                "created_at": s.created_at.isoformat(),
            }
            for s in steps
        ]

    async def get_dashboard_data(self) -> Dict:
        """Get comprehensive dashboard data."""
        # Get run stats
        result = await self.db.execute(
            text("""
                SELECT
                    COUNT(*) as total_runs,
                    COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed,
                    COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed,
                    COUNT(CASE WHEN status = 'running' THEN 1 END) as running
                FROM agent_runs
            """)
        )
        stats = result.fetchone()
        stats_dict = dict(stats) if stats else {}

        # Get agent type breakdown
        result = await self.db.execute(
            text("""
                SELECT agent_type, COUNT(*) as count
                FROM agent_runs
                GROUP BY agent_type
            """)
        )
        agents = result.fetchall()

        return {
            "total_runs": stats_dict.get("total_runs", 0),
            "completed": stats_dict.get("completed", 0),
            "failed": stats_dict.get("failed", 0),
            "running": stats_dict.get("running", 0),
            "agent_counts": {a[0]: a[1] for a in agents},
        }


async def get_observability_service(
    db: AsyncSession = Depends(get_db_session),
) -> ObservabilityService:
    return ObservabilityService(db)