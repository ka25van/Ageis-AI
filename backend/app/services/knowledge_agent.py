from typing import Dict, List, Optional
from uuid import UUID
import json

from fastapi import Depends
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentChunk
from app.services.embeddings import EmbeddingService, get_embedding_service
from app.services.llm_service import LLMService, get_llm_service
from app.services.memory import MemorySystem, get_memory_system
from app.core.di import get_db_session


class KnowledgeAgent:
    def __init__(self, db: AsyncSession, embedding_service: EmbeddingService, llm: LLMService, memory: Optional[MemorySystem] = None):
        self.db = db
        self.embeddings = embedding_service
        self.llm = llm
        self.memory = memory

    async def retrieve_knowledge(self, query: str, project_id: UUID = None, limit: int = 10) -> Dict:
        embedding = await self.embeddings.generate_embeddings([query])
        if not embedding or not embedding[0]:
            return {"results": [], "count": 0}

        query_embedding = embedding[0]
        emb_str = "[" + ",".join(str(v) for v in query_embedding) + "]"

        base_query = f"""
            SELECT dc.id, dc.content, dc.chunk_index, dc.token_count,
                   d.id as document_id, d.title, d.source_type,
                   d.doc_metadata as document_metadata,
                   1 - (dc.embedding <=> '{emb_str}'::vector) as similarity
            FROM document_chunks dc
            JOIN documents d ON dc.document_id = d.id
            WHERE dc.embedding IS NOT NULL
        """
        params: dict = {"limit": limit}

        if project_id:
            base_query += " AND d.project_id = :project_id"
            params["project_id"] = str(project_id)

        base_query += f"""
            AND 1 - (dc.embedding <=> '{emb_str}'::vector) >= :threshold
            ORDER BY dc.embedding <=> '{emb_str}'::vector
            LIMIT :limit
        """
        params["threshold"] = 0.3

        result = await self.db.execute(text(base_query), params)
        rows = result.fetchall()

        if not rows:
            base_query_no_threshold = base_query.replace(f"AND 1 - (dc.embedding <=> '{emb_str}'::vector) >= :threshold", "")
            result = await self.db.execute(text(base_query_no_threshold), {k: v for k, v in params.items() if k != "threshold"})
            rows = result.fetchall()

        results = []
        for row in rows:
            results.append({
                "chunk_id": str(row[0]),
                "content": row[1],
                "chunk_index": row[2],
                "token_count": row[3],
                "document_id": str(row[4]),
                "document_title": row[5],
                "source_type": row[6],
                "document_metadata": row[7],
                "similarity": float(row[8]),
            })

        return {"results": results, "count": len(results)}

    async def hybrid_search(self, query: str, project_id: UUID = None, limit: int = 10) -> Dict:
        semantic_results = await self.retrieve_knowledge(query, project_id, limit)
        semantic_hits = {r["chunk_id"]: r for r in semantic_results["results"]}

        result = await self.db.execute(
            select(DocumentChunk)
            .where(DocumentChunk.content.ilike(f"%{query}%"))
            .limit(limit)
        )
        keyword_results = result.scalars().all()

        combined = {}
        for r in semantic_results["results"]:
            combined[r["chunk_id"]] = r

        for r in keyword_results:
            if str(r.id) not in combined:
                combined[str(r.id)] = {
                    "chunk_id": str(r.id),
                    "content": r.content,
                    "chunk_index": r.chunk_index,
                    "similarity": 0.5,
                }

        ranked = sorted(combined.values(), key=lambda x: x.get("similarity", 0), reverse=True)[:limit]
        return {"results": ranked, "count": len(ranked), "semantic_count": len(semantic_results["results"]),
                "keyword_count": len(keyword_results)}

    async def rank_results(self, results: List[Dict], query: str) -> List[Dict]:
        query_lower = query.lower()
        query_words = query_lower.split()
        for r in results:
            content = r.get("content", "")
            content_lower = content.lower()
            word_matches = sum(1 for w in query_words if w in content_lower)
            r["relevance_score"] = (r.get("similarity", 0) * 0.7) + (word_matches / len(content.split()) if content else 0)
        return sorted(results, key=lambda x: x.get("relevance_score", 0), reverse=True)

    async def query(self, question: str, project_id: UUID = None) -> Dict:
        search_results = await self.hybrid_search(question, project_id, limit=5)
        context_parts = []

        # Include memory context
        memory_context = ""
        if self.memory:
            mem_results = await self.memory.search_semantic(question, limit=3, threshold=0.3)
            if mem_results:
                mem_texts = [r.get("text", "") for r in mem_results if r.get("text")]
                if mem_texts:
                    memory_context = "\nRelated past knowledge:\n" + "\n---\n".join(mem_texts[:2000])

        if not search_results["results"] and not memory_context:
            return {"answer": "I don't have enough information in the indexed documents to answer that.", "sources": []}

        for r in search_results["results"]:
            title = r.get("document_title", "Unknown")
            content = r.get("content", "")
            context_parts.append(f"[Source: {title}]\n{content}")

        context = "\n\n---\n\n".join(context_parts) + memory_context
        answer = await self.llm.generate(
            "You are a helpful assistant. Answer the question using only the provided context.",
            f"Question: {question}\n\nRelevant context:\n{context[:6000]}",
        )

        # Store Q&A in semantic memory
        if self.memory:
            try:
                emb = (await self.memory.embeddings.generate_embeddings([question]))[0]
                if emb:
                    await self.memory.store_semantic(
                        text=f"Q: {question}\nA: {answer[:500]}",
                        embedding=emb,
                        metadata={"type": "qa", "sources": len(search_results["results"])},
                    )
            except Exception:
                pass

        return {
            "answer": answer,
            "sources": [{"title": r.get("document_title"), "similarity": r.get("similarity")} for r in search_results["results"][:5]],
        }


async def get_knowledge_agent(
    db: AsyncSession = Depends(get_db_session),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    llm: LLMService = Depends(get_llm_service),
    memory: Optional[MemorySystem] = Depends(get_memory_system),
) -> KnowledgeAgent:
    return KnowledgeAgent(db, embedding_service, llm, memory=memory)
