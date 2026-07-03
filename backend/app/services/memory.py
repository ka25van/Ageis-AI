from typing import Dict, List, Optional, Any
from uuid import UUID
from datetime import datetime, timedelta

from fastapi import Depends
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import DocumentChunk
from app.models.agent import AgentRun
from app.services.embeddings import EmbeddingService, get_embedding_service
from app.core.di import get_db_session


class MemorySystem:
    def __init__(self, db: AsyncSession, embeddings: EmbeddingService):
        self.db = db
        self.embeddings = embeddings

    async def store_short_term(self, run_id: UUID, key: str, value: Any) -> None:
        from app.models.agent import AgentStep
        step = AgentStep(
            run_id=run_id, step_index=-1, step_type="memory",
            name=f"memory:{key}",
            input_data={"key": key, "value": value},
            output_data={"stored": True}, status="completed",
        )
        self.db.add(step)
        await self.db.commit()

    async def get_short_term(self, run_id: UUID, key: str) -> Optional[Any]:
        from app.models.agent import AgentStep
        result = await self.db.execute(
            select(AgentStep).where(
                AgentStep.run_id == run_id, AgentStep.name == f"memory:{key}",
            ).order_by(AgentStep.created_at.desc()).limit(1)
        )
        step = result.scalar_one_or_none()
        return step.input_data.get("value") if step else None

    async def store_long_term(self, user_id: UUID, key: str, value: Any, ttl_days: int = 30) -> None:
        from app.models.memory import LongTermMemory
        self.db.add(LongTermMemory(
            user_id=user_id, key=key, value=value,
            expires_at=datetime.utcnow() + timedelta(days=ttl_days),
        ))
        await self.db.commit()

    async def get_long_term(self, user_id: UUID, key: str) -> Optional[Any]:
        from app.models.memory import LongTermMemory
        result = await self.db.execute(
            select(LongTermMemory).where(
                LongTermMemory.user_id == user_id, LongTermMemory.key == key,
                LongTermMemory.expires_at > datetime.utcnow(),
            ).order_by(LongTermMemory.created_at.desc()).limit(1)
        )
        mem = result.scalar_one_or_none()
        return mem.value if mem else None

    async def store_semantic(self, text: str, embedding: List[float], metadata: Dict = None) -> None:
        from app.models.memory import SemanticMemory
        self.db.add(SemanticMemory(text=text, embedding=embedding, metadata=metadata or {}))
        await self.db.commit()

    async def search_semantic(self, query: str, limit: int = 5, threshold: float = 0.5) -> List[Dict]:
        from app.models.memory import SemanticMemory
        qe = (await self.embeddings.generate_embeddings([query]))[0]
        if not qe:
            return []
        emb_str = "[" + ",".join(str(v) for v in qe) + "]"
        result = await self.db.execute(text(f"""
            SELECT id, text, metadata, 1 - (embedding <=> '{emb_str}'::vector) as similarity
            FROM semantic_memory
            WHERE 1 - (embedding <=> '{emb_str}'::vector) >= :threshold
            ORDER BY embedding <=> '{emb_str}'::vector LIMIT :limit
        """), {"threshold": threshold, "limit": limit})
        return [dict(row) for row in result]

    async def summarize_run(self, run_id: UUID) -> Dict:
        result = await self.db.execute(
            select(AgentRun).where(AgentRun.id == run_id)
        )
        run = result.scalar_one_or_none()
        if not run:
            return {"error": "Run not found"}
        return {
            "run_id": str(run.id), "agent_type": run.agent_type,
            "status": run.status, "input": run.input_data, "output": run.output_data,
        }


async def get_memory_system(
    db: AsyncSession = Depends(get_db_session),
    embeddings: EmbeddingService = Depends(get_embedding_service),
) -> MemorySystem:
    return MemorySystem(db, embeddings)