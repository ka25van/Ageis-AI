from typing import Dict
from uuid import UUID
from datetime import datetime
import json

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import RepositoryFile
from app.models.agent import AgentRun, Approval
from app.services.llm_service import LLMService, get_llm_service
from app.core.di import get_db_session


class DeployAgent:
    def __init__(self, db: AsyncSession, llm: LLMService):
        self.db = db
        self.llm = llm

    DEPLOY_KEYWORDS = [
        "Dockerfile", "docker-compose", "nginx.conf", ".github/workflows",
        "deploy", "helm", "k8s", "kubernetes", "terraform", "pulumi",
        "cloudformation", ".env.example", "Makefile", "Dockerfile.",
    ]

    async def analyze_deployment(self, repository_id: UUID, user_id: UUID = None) -> Dict:
        result = await self.db.execute(
            select(RepositoryFile).where(RepositoryFile.repository_id == repository_id).limit(200)
        )
        files = result.scalars().all()

        deploy_files = []
        for f in files:
            path_lower = f.path.lower()
            if any(kw.lower() in path_lower for kw in self.DEPLOY_KEYWORDS):
                deploy_files.append({
                    "path": f.path,
                    "content_preview": (f.content or "")[:800],
                })

        if not deploy_files:
            context = json.dumps({"file_paths": [f.path for f in files[:50]]}, indent=2)
            system_prompt = "You are a DevOps consultant. Suggest what deployment configs should be added."
            user_prompt = f"Project files:\n{context}"
            analysis = await self.llm.generate(system_prompt, user_prompt)
        else:
            context = json.dumps(deploy_files[:15], indent=2)
            system_prompt = "You are a DevOps and deployment expert. Review these configs and give recommendations."
            user_prompt = f"Deployment configuration files:\n{context}"
            analysis = await self.llm.generate(system_prompt, user_prompt)

        run = AgentRun(
            project_id=repository_id,
            agent_type="deploy",
            status="completed",
            input_data={"repository_id": str(repository_id)},
            output_data={"analysis": analysis, "deploy_files_found": len(deploy_files)},
        )
        self.db.add(run)
        await self.db.commit()
        await self.db.refresh(run)

        approval = Approval(
            run_id=run.id,
            action_type="deploy_analysis",
            action_data={"analysis_preview": analysis[:500], "deploy_files_found": len(deploy_files)},
            status="pending",
            requested_by=user_id,
        )
        self.db.add(approval)
        await self.db.commit()
        await self.db.refresh(approval)

        return {
            "deploy_files_found": len(deploy_files),
            "total_files": len(files),
            "deploy_files": [f["path"] for f in deploy_files[:15]],
            "analysis": analysis,
            "approval": {
                "id": str(approval.id),
                "run_id": str(approval.run_id),
                "status": approval.status,
            },
        }


async def get_deploy_agent(
    db: AsyncSession = Depends(get_db_session),
    llm: LLMService = Depends(get_llm_service),
) -> DeployAgent:
    return DeployAgent(db, llm)
