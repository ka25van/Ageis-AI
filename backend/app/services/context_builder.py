from dataclasses import dataclass, field
from typing import Dict, List, Optional
from uuid import UUID

from fastapi import Depends

from app.services.repository_data_service import RepositoryDataService, get_repository_data_service
from app.services.repository_intelligence import RepositoryIntelligence, get_repository_intelligence
from app.services.memory import MemorySystem, get_memory_system
from app.services.embeddings import EmbeddingService, get_embedding_service
from app.core.config import settings
from app.core.task import Task


# --- Bounded sub-contexts for EngineeringContext ---

@dataclass
class RepositoryContext:
    summary: str = ""
    languages: List[str] = field(default_factory=list)
    dependency_graph: Dict = field(default_factory=dict)
    architecture_layers: List[str] = field(default_factory=list)
    api_routes: List[Dict] = field(default_factory=list)
    entry_points: List[str] = field(default_factory=list)
    file_count: int = 0


@dataclass
class KnowledgeContext:
    results: List[Dict] = field(default_factory=list)
    query: str = ""


@dataclass
class InfrastructureContext:
    docker_files: List[Dict] = field(default_factory=list)
    ci_configs: List[Dict] = field(default_factory=list)
    has_docker: bool = False
    has_ci: bool = False


@dataclass
class MemoryContext:
    semantic_memory: List[Dict] = field(default_factory=list)
    conversation_history: List[Dict] = field(default_factory=list)


@dataclass
class ExecutionContext:
    recent_runs: List[Dict] = field(default_factory=list)


@dataclass
class WorkflowContext:
    state: Dict = field(default_factory=dict)
    pending_approvals: List[Dict] = field(default_factory=list)


@dataclass
class EngineeringContext:
    """Root aggregate for all engineering knowledge.
    
    Composed of bounded sub-contexts rather than one growing dataclass.
    Planner consumes EngineeringContext and delegates sub-contexts to agents.
    """
    task: Task
    project: "ProjectContext"
    repository: RepositoryContext = field(default_factory=RepositoryContext)
    knowledge: KnowledgeContext = field(default_factory=KnowledgeContext)
    infrastructure: InfrastructureContext = field(default_factory=InfrastructureContext)
    memory: MemoryContext = field(default_factory=MemoryContext)
    execution: ExecutionContext = field(default_factory=ExecutionContext)
    workflow: WorkflowContext = field(default_factory=WorkflowContext)


# --- ProjectContext (unchanged for backward compatibility) ---

@dataclass
class ProjectContext:
    project_id: UUID
    project_name: str = ""
    repository_summary: str = ""
    file_previews: str = ""
    languages: List[str] = field(default_factory=list)
    dependency_graph: Dict = field(default_factory=dict)
    architecture_layers: List[str] = field(default_factory=list)
    api_routes: List[Dict] = field(default_factory=list)
    entry_points: List[str] = field(default_factory=list)
    semantic_memory: List[Dict] = field(default_factory=list)
    workflow_state: Dict = field(default_factory=dict)
    task_description: str = ""
    step_input: Dict = field(default_factory=dict)


# Configurable truncation limits
MAX_FILE_PREVIEW_CHARS = 5000
MAX_REPO_SUMMARY_CHARS = 2000
MAX_MEMORY_ENTRIES = 5
MAX_ROUTES = 20
MAX_LAYERS = 10


class ContextBuilder:
    """Orchestrates data collection into a single ProjectContext for agents.
    
    Also serves as the memory gateway — agents store/search memory through ContextBuilder
    instead of importing MemorySystem directly.
    """

    def __init__(self, repo_data: RepositoryDataService, intelligence: RepositoryIntelligence, memory: Optional[MemorySystem] = None, embeddings: Optional[EmbeddingService] = None):
        self.repo_data = repo_data
        self.intelligence = intelligence
        self.memory = memory
        self.embeddings = embeddings

    async def store_memory(self, text: str, metadata: Dict = None) -> None:
        """Store a text entry in semantic memory. Called by agents after processing."""
        if not self.memory:
            return
        try:
            emb = (await self.memory.embeddings.generate_embeddings([text]))[0]
            if emb:
                await self.memory.store_semantic(text=text, embedding=emb, metadata=metadata or {})
        except Exception:
            pass

    async def after_agent(self, agent_name: str, result: Dict, task_description: str = "") -> None:
        """Post-processing after an agent execution: store result in semantic memory."""
        text = result.get("result", "")
        if not text:
            return
        await self.store_memory(
            text=f"Agent: {agent_name}\nTask: {task_description}\nResult: {text[:1000]}",
            metadata={"type": f"agent:{agent_name}", "confidence": result.get("confidence", 0)},
        )

    async def build(self, repository_id: UUID, task_description: str = "") -> ProjectContext:
        repo = await self.repo_data.get_repository(repository_id)
        repo_name = repo.name if repo else "unknown"
        project_id = repo.project_id if repo else repository_id

        languages = await self.repo_data.get_languages(repository_id)
        file_previews = await self.repo_data.get_file_summary(repository_id, limit=settings.REPOSITORY_FILE_LIMIT, preview_chars=settings.FILE_PREVIEW_CHARS)

        summary = await self.intelligence.get_summary(repository_id)
        deps = await self.intelligence.get_dependency_graph(repository_id)
        architecture = await self.intelligence.get_architecture(repository_id)
        routes = await self.intelligence.get_api_routes(repository_id)
        entry_points = await self.intelligence.get_entry_points(repository_id)

        semantic_memory = []
        if self.memory and task_description:
            mem_results = await self.memory.search_semantic(task_description, limit=3, threshold=settings.SIMILARITY_THRESHOLD)
            semantic_memory = [
                {"text": m.get("text", ""), "similarity": m.get("similarity", 0)}
                for m in mem_results[:MAX_MEMORY_ENTRIES]
            ]

        ctx = ProjectContext(
            project_id=project_id,
            project_name=repo_name,
            repository_summary=str(summary)[:MAX_REPO_SUMMARY_CHARS],
            file_previews=file_previews[:MAX_FILE_PREVIEW_CHARS],
            languages=languages,
            dependency_graph=deps,
            architecture_layers=list(architecture.get("layers", {}).keys())[:MAX_LAYERS],
            api_routes=routes[:MAX_ROUTES],
            entry_points=entry_points[:10],
            semantic_memory=semantic_memory,
            task_description=task_description,
        )
        return ctx

    async def build_engineering_context(self, task: Task) -> EngineeringContext:
        """Build full EngineeringContext from a Task.
        
        Composes sub-contexts from multiple data sources.
        Planner consumes this — agents consume ec.project for backward compat.
        """
        pc = await self.build(task.repository_id, task.input) if task.repository_id else ProjectContext(
            project_id=task.project_id, task_description=task.input,
        )

        repo_ctx = RepositoryContext()
        infra_ctx = InfrastructureContext()
        knowledge_ctx = KnowledgeContext(query=task.input)
        memory_ctx = MemoryContext()
        exec_ctx = ExecutionContext()
        workflow_ctx = WorkflowContext()

        if task.repository_id:
            rid = task.repository_id
            summary = await self.intelligence.get_summary(rid)
            deps = await self.intelligence.get_dependency_graph(rid)
            architecture = await self.intelligence.get_architecture(rid)
            routes = await self.intelligence.get_api_routes(rid)
            entry_points = await self.intelligence.get_entry_points(rid)

            repo_ctx = RepositoryContext(
                summary=str(summary)[:MAX_REPO_SUMMARY_CHARS],
                languages=await self.repo_data.get_languages(rid),
                dependency_graph=deps,
                architecture_layers=list(architecture.get("layers", {}).keys())[:MAX_LAYERS],
                api_routes=routes[:MAX_ROUTES],
                entry_points=entry_points[:10],
                file_count=summary.get("file_count", 0),
            )

        if self.embeddings:
            try:
                knowledge_results = await self.embeddings.hybrid_search(
                    task.input, task.project_id, limit=5,
                )
                knowledge_ctx = KnowledgeContext(results=knowledge_results, query=task.input)
            except Exception:
                pass

        if self.memory:
            try:
                mem_results = await self.memory.search_semantic(
                    task.input, limit=5, threshold=settings.SIMILARITY_THRESHOLD,
                )
                memory_ctx = MemoryContext(
                    semantic_memory=[
                        {"text": m.get("text", ""), "similarity": m.get("similarity", 0)}
                        for m in mem_results[:MAX_MEMORY_ENTRIES]
                    ],
                )
            except Exception:
                pass

        return EngineeringContext(
            task=task,
            project=pc,
            repository=repo_ctx,
            knowledge=knowledge_ctx,
            infrastructure=infra_ctx,
            memory=memory_ctx,
            execution=exec_ctx,
            workflow=workflow_ctx,
        )


async def get_context_builder(
    repo_data: RepositoryDataService = Depends(get_repository_data_service),
    intelligence: RepositoryIntelligence = Depends(get_repository_intelligence),
    memory: Optional[MemorySystem] = Depends(get_memory_system),
    embeddings: Optional[EmbeddingService] = Depends(get_embedding_service),
) -> ContextBuilder:
    return ContextBuilder(repo_data, intelligence, memory=memory, embeddings=embeddings)
