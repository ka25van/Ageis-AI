from typing import Dict, List
from uuid import UUID

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.embeddings import EmbeddingService, get_embedding_service
from app.services.llm_service import LLMService, get_llm_service
from app.services.agent_base import AgentResult
from app.services.context_builder import ProjectContext
from app.core.di import get_db_session


class KnowledgeAgent:
    def __init__(self, db: AsyncSession, embedding_service: EmbeddingService, llm: LLMService):
        self.db = db
        self.embeddings = embedding_service
        self.llm = llm

    async def process(self, context: ProjectContext) -> AgentResult:
        question = context.task_description
        if not question:
            return AgentResult(result="No question provided.", confidence=0.0, recommendations=[], follow_up_actions=[])

        result = await self.query(question, context.project_id, memory_context=context.semantic_memory)
        answer = result.get("answer", "")
        sources = result.get("sources", [])
        return AgentResult(
            result=answer,
            confidence=0.8 if sources else 0.4,
            recommendations=["Search with different keywords" if not sources else "View document sources"],
            follow_up_actions=["Refine your query", "Search hybrid mode"],
            details=result,
        )

    async def retrieve_knowledge(self, query: str, project_id: UUID = None, limit: int = 10) -> Dict:
        results = await self.embeddings.semantic_search(
            query=query,
            project_id=project_id,
            limit=limit,
            similarity_threshold=0.0,
        )
        filtered = [r for r in results if r.get("similarity", 0) >= 0.3]
        return {"results": filtered if filtered else results, "count": len(filtered) if filtered else len(results)}

    async def hybrid_search(self, query: str, project_id: UUID = None, limit: int = 10) -> Dict:
        results = await self.embeddings.hybrid_search(query, project_id, limit)
        return {"results": results, "count": len(results)}

    async def rank_results(self, results: List[Dict], query: str) -> List[Dict]:
        query_lower = query.lower()
        query_words = query_lower.split()
        for r in results:
            content = r.get("content", "")
            content_lower = content.lower()
            word_matches = sum(1 for w in query_words if w in content_lower)
            r["relevance_score"] = (r.get("similarity", 0) * 0.7) + (word_matches / len(content.split()) if content else 0)
        return sorted(results, key=lambda x: x.get("relevance_score", 0), reverse=True)

    async def query(self, question: str, project_id: UUID = None, memory_context: List[Dict] = None) -> Dict:
        search_results = await self.hybrid_search(question, project_id, limit=5)
        context_parts = []

        # Include memory context from ProjectContext (provided by ContextBuilder)
        mem_str = ""
        if memory_context:
            mem_texts = [m.get("text", "") for m in memory_context if m.get("text")]
            if mem_texts:
                mem_str = "\nRelated past knowledge:\n" + "\n---\n".join(mem_texts[:2000])

        if not search_results["results"] and not mem_str:
            return {"answer": "I don't have enough information in the indexed documents to answer that.", "sources": []}

        for r in search_results["results"]:
            title = r.get("document_title", "Unknown")
            content = r.get("content", "")
            context_parts.append(f"[Source: {title}]\n{content}")

        context = "\n\n---\n\n".join(context_parts) + mem_str
        answer = await self.llm.generate(
            "You are a helpful assistant. Answer the question using only the provided context.",
            f"Question: {question}\n\nRelevant context:\n{context[:6000]}",
        )

        return {
            "answer": answer,
            "sources": [{"title": r.get("document_title"), "similarity": r.get("similarity")} for r in search_results["results"][:5]],
        }


async def get_knowledge_agent(
    db: AsyncSession = Depends(get_db_session),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    llm: LLMService = Depends(get_llm_service),
) -> KnowledgeAgent:
    return KnowledgeAgent(db, embedding_service, llm)
