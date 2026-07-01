from typing import Dict, List, Optional, Any
from uuid import UUID
from datetime import datetime

from fastapi import Depends
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.repository_analysis import RepositoryAnalyzer
from app.core.di import get_db_session


class DocumentationAgent:
    """Agent for generating README, API docs, and architecture docs."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def generate_readme(self, repository_id: UUID) -> Dict:
        """Generate a README from repository structure."""
        from app.models.project import RepositoryFile

        result = await self.db.execute(
            select(RepositoryFile).where(RepositoryFile.repository_id == repository_id)
        )
        files = result.scalars().all()

        # Collect info
        languages = set(f.language for f in files if f.language)
        framework = self._detect_framework(files)
        readme_files = [f for f in files if "readme" in f.path.lower()]

        readme = f"""# {files[0].path.split('/')[0] if files else 'Unknown'} Repository

## Overview
A repository with {len(files)} files across {len(languages)} languages.

## Languages
{', '.join(languages) if languages else 'Unknown'}

## Framework
{framework or 'Unknown'}

## Structure
{self._summarize_structure(files)}

## Getting Started
Clone this repository and explore the code.

## Features
- {len(files)} files indexed
- {sum(1 for f in files if f.content)} files with content
- {len(readme_files)} README files found
"""
        return {"readme": readme, "files_analyzed": len(files)}

    async def generate_api_documentation(self, repository_id: UUID) -> Dict:
        """Generate API documentation from repository routes."""
        from app.models.project import RepositoryFile

        result = await self.db.execute(
            select(RepositoryFile).where(RepositoryFile.repository_id == repository_id)
        )
        files = result.scalars().all()

        routes = []
        for f in files:
            if f.content:
                # Look for API routes
                if "fastapi" in f.content.lower() or "apirouter" in f.content.lower():
                    lines = f.content.split("\n")
                    for i, line in enumerate(lines):
                        if "@router" in line or "@app" in line or "APIRouter" in line:
                            routes.append({"file": f.path, "line": i + 1, "code": line.strip()})

        return {
            "routes": routes[:10],
            "total_routes": len(routes),
            "summary": f"Found {len(routes)} API routes",
        }

    async def generate_architecture_documentation(self, repository_id: UUID) -> Dict:
        """Generate architecture documentation."""
        from app.models.project import RepositoryFile

        result = await self.db.execute(
            select(RepositoryFile).where(RepositoryFile.repository_id == repository_id)
        )
        files = result.scalars().all()

        layers = {"api": [], "models": [], "services": [], "tools": [], "config": []}
        for f in files:
            for layer in layers:
                if f"/{layer}/" in f.path.lower():
                    layers[layer].append(f.path)

        return {
            "layers": {k: v for k, v in layers.items() if v},
            "total_files": len(files),
            "summary": f"Architecture: {', '.join(k for k, v in layers.items() if v)}",
        }

    def _detect_framework(self, files: list) -> str:
        """Detect framework from file content."""
        all_content = " ".join(f.content or "" for f in files)
        if "fastapi" in all_content.lower():
            return "FastAPI"
        if "django" in all_content.lower():
            return "Django"
        if "flask" in all_content.lower():
            return "Flask"
        return "Unknown"

    def _summarize_structure(self, files: list) -> str:
        """Summarize directory structure."""
        paths = [f.path for f in files]
        dirs = set(p.split("/")[0] for p in paths if "/" in p)
        return f"Directories: {', '.join(dirs)}"


async def get_documentation_agent(
    db: AsyncSession = Depends(get_db_session),
) -> DocumentationAgent:
    return DocumentationAgent(db)