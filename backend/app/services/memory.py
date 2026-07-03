from typing import Dict, List, Optional, Any
from uuid import UUID
from datetime import datetime, timedelta

from fastapi import Depends
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import DocumentChunk
from app.models.agent import AgentRun, AgentStep
from app.models.memory import LongTermMemory, SemanticMemory
from app.services.embeddings import EmbeddingService, get_embedding_service
from app.core.di import get_db_session


class MemorySystem:
    def __init__(self, db: AsyncSession, embeddings: EmbeddingService):
        self.db = db
        self.embeddings = embeddings

    async def store_short_term(self, run_id: UUID, key: str, value: Any) -> None:
        step = AgentStep(
            run_id=run_id, step_index=-1, step_type="memory",
            name=f"memory:{key}",
            input_data={"key": key, "value": value},
            output_data={"stored": True}, status="completed",
        )
        self.db.add(step)
        await self.db.commit()

    async def get_short_term(self, run_id: UUID, key: str) -> Optional[Any]:
        result = await self.db.execute(
            select(AgentStep).where(
                AgentStep.run_id == run_id, AgentStep.name == f"memory:{key}",
            ).order_by(AgentStep.created_at.desc()).limit(1)
        )
        step = result.scalar_one_or_none()
        return step.input_data.get("value") if step else None

    async def store_long_term(self, user_id: UUID, key: str, value: Any, ttl_days: int = 30) -> None:
        self.db.add(LongTermMemory(
            user_id=user_id, key=key, value=value,
            expires_at=datetime.utcnow() + timedelta(days=ttl_days),
        ))
        await self.db.commit()

    async def get_long_term(self, user_id: UUID, key: str) -> Optional[Any]:
        result = await self.db.execute(
            select(LongTermMemory).where(
                LongTermMemory.user_id == user_id, LongTermMemory.key == key,
                LongTermMemory.expires_at > datetime.utcnow(),
            ).order_by(LongTermMemory.created_at.desc()).limit(1)
        )
        mem = result.scalar_one_or_none()
        return mem.value if mem else None

    async def store_semantic(self, text: str, embedding: List[float], metadata: Dict = None) -> None:
        self.db.add(SemanticMemory(text=text, embedding=embedding, doc_metadata=metadata or {}))
        await self.db.commit()

    async def list_semantic(self, limit: int = 50) -> List[Dict]:
        result = await self.db.execute(
            select(SemanticMemory).order_by(SemanticMemory.created_at.desc()).limit(limit)
        )
        rows = result.scalars().all()
        return [
            {
                "id": str(r.id),
                "text": r.text[:500],
                "metadata": r.doc_metadata,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ]

    async def search_semantic(self, query: str, limit: int = 5, threshold: float = 0.5) -> List[Dict]:
        return await self.embeddings.semantic_search(
            query=query, limit=limit,
            similarity_threshold=threshold,
            table_name="semantic_memory",
        )

    # --- Conversation Memory ---

    async def store_conversation(self, project_id: UUID, user_id: UUID, role: str, content: str) -> None:
        key = f"conversation:{project_id}:{user_id}"
        existing = await self.get_long_term(user_id, key)
        messages = existing if isinstance(existing, list) else []
        messages.append({"role": role, "content": content, "timestamp": datetime.utcnow().isoformat()})
        # Truncate to last 50 messages
        if len(messages) > 50:
            messages = messages[-50:]
        await self.store_long_term(user_id, key, messages, ttl_days=7)

    async def get_conversation(self, project_id: UUID, user_id: UUID, limit: int = 20) -> List[Dict]:
        key = f"conversation:{project_id}:{user_id}"
        existing = await self.get_long_term(user_id, key)
        if not existing or not isinstance(existing, list):
            return []
        return existing[-limit:]

    async def clear_conversation(self, project_id: UUID, user_id: UUID) -> None:
        key = f"conversation:{project_id}:{user_id}"
        result = await self.db.execute(
            select(LongTermMemory).where(
                LongTermMemory.user_id == user_id, LongTermMemory.key == key,
            )
        )
        mem = result.scalar_one_or_none()
        if mem:
            await self.db.delete(mem)
            await self.db.commit()

    # --- Repository Memory (persisted cache) ---

    async def store_repository_memory(self, repository_id: UUID, analysis: Dict) -> None:
        await self.store_long_term(
            user_id=UUID("00000000-0000-0000-0000-000000000000"),
            key=f"repo_analysis:{repository_id}",
            value=analysis,
            ttl_days=30,
        )

    async def get_repository_memory(self, repository_id: UUID) -> Optional[Dict]:
        return await self.get_long_term(
            user_id=UUID("00000000-0000-0000-0000-000000000000"),
            key=f"repo_analysis:{repository_id}",
        )

    async def delete_repository_memory(self, repository_id: UUID) -> None:
        key = f"repo_analysis:{repository_id}"
        result = await self.db.execute(
            select(LongTermMemory).where(
                LongTermMemory.user_id == UUID("00000000-0000-0000-0000-000000000000"),
                LongTermMemory.key == key,
            )
        )
        mem = result.scalar_one_or_none()
        if mem:
            await self.db.delete(mem)
            await self.db.commit()

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