from typing import Dict, List, Optional, Any
from uuid import UUID

from fastapi import Depends
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentChunk
from app.services.embeddings import EmbeddingService, get_embedding_service
from app.core.di import get_db_session


class KnowledgeAgent:
    """Agent for retrieving and ranking knowledge from documents."""

    def __init__(self, db: AsyncSession, embedding_service: EmbeddingService):
        self.db = db
        self.embeddings = embedding_service

    async def retrieve_knowledge(self, query: str, project_id: UUID = None, limit: int = 10) -> Dict:
        """Retrieve knowledge using hybrid search."""
        # Generate embedding for semantic search
        embedding = await self.embeddings.generate_embeddings([query])

        if not embedding or not embedding[0]:
            return {"results": [], "count": 0}

        query_embedding = embedding[0]

        # Build query
        base_query = """
            SELECT dc.id, dc.content, dc.chunk_index, dc.token_count,
                   d.id as document_id, d.title, d.source_type,
                   d.metadata as document_metadata,
                   1 - (dc.embedding <=> :query_embedding) as similarity
            FROM document_chunks dc
            JOIN documents d ON dc.document_id = d.id
            WHERE dc.embedding IS NOT NULL
        """
        params = {"query_embedding": query_embedding, "limit": limit}

        if project_id:
            base_query += " AND d.project_id = :project_id"
            params["project_id"] = str(project_id)

        base_query += """
            AND 1 - (dc.embedding <=> :query_embedding) >= :threshold
            ORDER BY dc.embedding <=> :query_embedding
            LIMIT :limit
        """
        params["threshold"] = 0.7

        result = await self.db.execute(text(base_query), params)
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
        """Hybrid search combining semantic and keyword search."""
        # Semantic search
        semantic_results = await self.retrieve_knowledge(query, project_id, limit)
        semantic_hits = {r["chunk_id"]: r for r in semantic_results["results"]}

        # Keyword search (simple text match)
        from app.models.document import DocumentChunk
        result = await self.db.execute(
            select(DocumentChunk)
            .where(DocumentChunk.content.ilike(f"%{query}%"))
            .limit(limit)
        )
        keyword_results = result.scalars().all()

        # Merge and rank
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

        # Rank by similarity
        ranked = sorted(combined.values(), key=lambda x: x.get("similarity", 0), reverse=True)[:limit]
        return {"results": ranked, "count": len(ranked), "semantic_count": len(semantic_results["results"]),
                "keyword_count": len(keyword_results)}

    async def rank_results(self, results: List[Dict], query: str) -> List[Dict]:
        """Re-rank results by relevance to the query."""
        query_lower = query.lower()
        query_words = query_lower.split()

        for r in results:
            content = r.get("content", "")
            content_lower = content.lower()
            word_matches = sum(1 for w in query_words if w in content_lower)
            r["relevance_score"] = (r.get("similarity", 0) * 0.7) + (word_matches / len(content.split()) if content else 0)

        return sorted(results, key=lambda x: x.get("relevance_score", 0), reverse=True)


async def get_knowledge_agent(
    db: AsyncSession = Depends(get_db_session),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
) -> KnowledgeAgent:
    return KnowledgeAgent(db, embedding_service)