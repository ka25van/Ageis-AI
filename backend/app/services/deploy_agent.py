from typing import Dict, List
from uuid import UUID
import json

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.llm_service import LLMService, get_llm_service
from app.services.repository_data_service import RepositoryDataService, get_repository_data_service
from app.services.agent_base import AgentResult
from app.services.context_builder import ProjectContext
from app.services.approval_service import ApprovalService, get_approval_service
from app.core.di import get_db_session
from app.core.config import settings


class DeployAgent:
    def __init__(self, repo_data: RepositoryDataService, llm: LLMService, db: AsyncSession, approval_service: ApprovalService):
        self.repo_data = repo_data
        self.llm = llm
        self.db = db
        self.approval_service = approval_service

    async def process(self, context: ProjectContext) -> AgentResult:
        result = await self.analyze_deployment(context.project_id)
        result_text = result.get("analysis", json.dumps(result))
        return AgentResult(
            result=result_text,
            confidence=0.8,
            recommendations=result.get("recommendations", []),
            follow_up_actions=["Request approval for deployment", "Review Docker config"],
            details=result,
        )

    DEPLOY_KEYWORDS = [
        "docker", "dockerfile", "docker-compose", "kubernetes", "k8s",
        "nginx", "apache", "gunicorn", "uvicorn", "wsgi", "asgi",
        "github actions", "gitlab ci", "jenkins", "circleci",
        "terraform", "ansible", "pulumi", "cloudformation",
        "helm", "deployment", "service", "ingress",
        "Dockerfile", "docker-compose.yml", "deploy",
        ".github/workflows", ".gitlab-ci.yml",
    ]

    async def analyze_deployment(self, repository_id: UUID) -> Dict:
        files = await self.repo_data.get_files(repository_id, limit=settings.BATCH_FILE_LIMIT)

        deploy_files = []
        for f in files:
            if f.path.lower().endswith(("dockerfile", "docker-compose.yml", "docker-compose.yaml",
                                          ".github/workflows/main.yml", ".github/workflows/deploy.yml",
                                          "nginx.conf", "terraform/main.tf")):
                deploy_files.append(f)
            elif any(f.path.lower().startswith(prefix) for prefix in [".github/", "ci/", "deploy/"]):
                deploy_files.append(f)
            elif f.content and any(kw.lower() in f.content.lower() for kw in self.DEPLOY_KEYWORDS):
                deploy_files.append(f)

        if not deploy_files:
            return {
                "deployment_files": [],
                "analysis": "No deployment configuration files detected in this repository.",
                "recommendations": [
                    "Add Dockerfile for containerization",
                    "Add docker-compose.yml for local development",
                    "Add CI/CD pipeline configuration",
                ],
            }

        file_previews = []
        for f in deploy_files[:20]:
            content = (f.content or "")[:600]
            file_previews.append(f"Path: {f.path}\nLanguage: {f.language}\n```\n{content}\n```")

        context = "\n\n".join(file_previews)
        system_prompt = """You are a DevOps expert. Analyze these deployment configurations and provide:
1. Current deployment setup summary
2. Infrastructure requirements
3. Security considerations
4. Scalability assessment
5. Improvement recommendations
6. Deployment strategy suggestion (blue-green, rolling, canary)"""

        user_prompt = f"Deployment-related files found ({len(deploy_files)}):\n{context[:6000]}"
        analysis = await self.llm.generate(system_prompt, user_prompt)

        return {
            "deployment_files": [
                {"path": f.path, "language": f.language, "size": f.size_bytes}
                for f in deploy_files[:20]
            ],
            "total_deploy_files": len(deploy_files),
            "analysis": analysis,
            "recommendations": [analysis],
        }

    async def request_approval(self, deployment_id: str, title: str, description: str) -> Dict:
        approval = await self.approval_service.request_approval(
            run_id=deployment_id,
            action_type="deploy",
            action_data={"title": title, "description": description},
        )
        return {
            "approval_id": str(approval.id),
            "status": approval.status,
            "message": "Approval request created",
        }


async def get_deploy_agent(
    repo_data: RepositoryDataService = Depends(get_repository_data_service),
    llm: LLMService = Depends(get_llm_service),
    db: AsyncSession = Depends(get_db_session),
    approval_service: ApprovalService = Depends(get_approval_service),
) -> DeployAgent:
    return DeployAgent(repo_data, llm, db, approval_service)
