from typing import Dict, List, Optional, Any
from uuid import UUID
from datetime import datetime, timedelta
import json

from fastapi import Depends
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from pgvector.sqlalchemy import Vector

from app.models.document import DocumentChunk
from app.models.agent import AgentRun
from app.core.di import get_db_session
from app.core.config import settings


class MemorySystem:
    """Three-tier memory system: short-term, long-term, semantic."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # --- Short-Term Memory ---
    async def store_short_term(self, run_id: UUID, key: str, value: Any) -> None:
        """Store short-term (current execution) memory."""
        from app.models.agent import AgentStep
        step = AgentStep(
            run_id=run_id,
            step_index=-1,
            step_type="memory",
            name=f"memory:{key}",
            input_data={"key": key, "value": value},
            output_data={"stored": True},
            status="completed",
        )
        self.db.add(step)
        await self.db.commit()

    async def get_short_term(self, run_id: UUID, key: str) -> Optional[Any]:
        """Retrieve short-term memory."""
        result = await self.db.execute(
            select(AgentStep).where(
                AgentStep.run_id == run_id,
                AgentStep.name == f"memory:{key}",
            ).order_by(AgentStep.created_at.desc()).limit(1)
        )
        step = result.scalar_one_or_none()
        if step:
            return step.input_data.get("value")
        return None

    # --- Long-Term Memory ---
    async def store_long_term(self, user_id: UUID, key: str, value: Any, ttl_days: int = 30) -> None:
        """Store long-term (persistent across sessions) memory."""
        from app.models.memory import LongTermMemory
        memory = LongTermMemory(
            user_id=user_id,
            key=key,
            value=value,
            expires_at=datetime.utcnow() + timedelta(days=ttl_days),
        )
        self.db.add(memory)
        await self.db.commit()

    async def get_long_term(self, user_id: UUID, key: str) -> Optional[Any]:
        """Retrieve long-term memory."""
        from app.models.memory import LongTermMemory
        result = await self.db.execute(
            select(LongTermMemory).where(
                LongTermMemory.user_id == user_id,
                LongTermMemory.key == key,
                LongTermMemory.expires_at > datetime.utcnow(),
            ).order_by(LongTermMemory.created_at.desc()).limit(1)
        )
        mem = result.scalar_one_or_none()
        if mem:
            return mem.value
        return None

    # --- Semantic Memory ---
    async def store_semantic(self, text: str, embedding: List[float], metadata: Dict = None) -> None:
        """Store semantic memory (vector embeddings)."""
        from app.models.memory import SemanticMemory
        memory = SemanticMemory(
            text=text,
            embedding=embedding,
            metadata=metadata or {},
        )
        self.db.add(memory)
        await self.db.commit()

    async def search_semantic(
        self, query: str, limit: int = 5, threshold: float = 0.7
    ) -> List[Dict]:
        """Search semantic memory by embedding similarity."""
        from app.models.memory import SemanticMemory

        # Generate query embedding
        query_embedding = await self._generate_embedding(query)

        result = await self.db.execute(
            text("""
                SELECT id, text, metadata, 
                       1 - (embedding <=> :query) as similarity
                FROM semantic_memory
                WHERE 1 - (embedding <=> :query) >= :threshold
                ORDER BY embedding <=> :query
                LIMIT :limit
            """),
            {"query": query_embedding, "threshold": threshold, "limit": limit},
        )
        return [dict(row) for row in result]

    async def _generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for query text."""
        import httpx
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"{settings.OLLAMA_BASE_URL}/api/embeddings",
                    json={"model": settings.EMBEDDING_MODEL, "prompt": text},
                )
                if response.status_code == 200:
                    return response.json().get("embedding", [0.0] * 1536)
        except:
            pass
        return [0.0] * 1536

    async def summarize_run(self, run_id: UUID) -> Dict:
        """Summarize an agent run's memory."""
        from app.models.agent import AgentStep
        result = await self.db.execute(
            select(AgentStep).where(AgentStep.run_id == run_id).order_by(AgentStep.step_index)
        )
        steps = result.scalars().all()

        return {
            "total_steps": len(steps),
            "steps": [
                {"step_index": s.step_index, "step_type": s.step_type, "name": s.name}
                for s in steps
            ],
        }


class LongTermMemory:
    """Long-term memory storage model."""
    pass  # Placeholder - will use SQLAlchemy model


class SemanticMemory:
    """Semantic memory storage model."""
    pass  # Placeholder - will use SQLAlchemy model


async def get_memory_system(db: AsyncSession = Depends(get_db_session)) -> MemorySystem:
    return MemorySystem(db)