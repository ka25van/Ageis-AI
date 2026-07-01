from typing import Dict, List, Optional, Any
from collections import defaultdict
import re
from uuid import UUID
from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import RepositoryFile
from app.core.di import get_db_session


class RepositoryAnalyzer:
    """Analyzes repository structure: dependencies, APIs, architecture, services."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # --- Dependency Analysis ---
    PYTHON_IMPORT_PATTERNS = [
        r'^from\s+([\w.]+)\s+import\s+.*$',
        r'^import\s+([\w.]+)\s*$',
        r'^from\s+([\w.]+)\s+import\s+\(',
    ]

    JS_IMPORT_PATTERNS = [
        r'import\s+.*\s+from\s+[\'\"]([\w./@-]+)[\'\"]',
        r'require\([\'\"]([\w./@-]+)[\'\"]\)',
    ]

    def extract_dependencies(self, content: str, language: str) -> List[str]:
        """Extract dependency paths from file content."""
        deps = []
        if language == "python":
            patterns = self.PYTHON_IMPORT_PATTERNS
        else:
            patterns = self.JS_IMPORT_PATTERNS

        for pattern in patterns:
            matches = re.findall(pattern, content, re.MULTILINE)
            deps.extend(matches)

        return list(set(deps))

    def categorize_dependency(self, dep_path: str) -> str:
        """Categorize dependency type."""
        if dep_path.startswith("django") or dep_path.startswith("flask") or dep_path.startswith("fastapi"):
            return "framework"
        if "." in dep_path and dep_path.count(".") >= 2:
            return "third_party"
        if dep_path.startswith(".") or dep_path.startswith("app") or dep_path.startswith("src"):
            return "internal"
        return "unknown"

    # --- API Discovery ---
    API_PATTERNS = {
        "fastapi": [
            r'@(?:router|app)\.(?:get|post|put|delete|patch|options|head)\([\'\"]([/\w{}.-]+)[\'\"]',
            r'@(?:router|app)\.(?:get|post|put|delete|patch|options|head)\([\'\"]([/\w{}.-]+)[\'\"].*?\)',
        ],
        "flask": [
            r'@(?:app|bp)\.(?:route|get|post|put|delete|patch)\([\'\"]([/\w{}.-]+)[\'\"]',
        ],
        "express": [
            r'router\.(?:get|post|put|delete|patch|options|head)\([\'\"]([/\w{}.-]+)[\'\"]',
            r'app\.(?:get|post|put|delete|patch|options|head)\([\'\"]([/\w{}.-]+)[\'\"]',
        ],
        "fastapi_pydantic": [
            r'@(?:router|app)\.(?:api_route|route)\([\'\"]([/\w{}.-]+)[\'\"]',
        ],
    }

    def extract_api_routes(self, content: str, language: str) -> List[Dict]:
        """Extract API route definitions."""
        routes = []
        framework = "fastapi" if language == "python" else "express"

        patterns = self.API_PATTERNS.get(framework, [])
        for pattern in patterns:
            matches = re.findall(pattern, content, re.MULTILINE)
            for match in matches:
                routes.append({
                    "path": match,
                    "method": "GET" if "get" in pattern.lower() else "POST",
                    "framework": framework,
                })

        return routes

    def extract_http_routes(self, content: str) -> List[Dict]:
        try:
            import ast
            tree = ast.parse(content)
            routes = []
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    for decorator in node.decorator_list:
                        if hasattr(decorator, 'attr'):
                            routes.append({
                                "function": node.name,
                                "decorator": decorator.attr,
                                "line": node.lineno,
                            })
                # Also check for router.include_router calls
                if isinstance(node, ast.Call):
                    if hasattr(node.func, 'attr') and node.func.attr == 'include_router':
                        routes.append({
                            "type": "router_include",
                            "line": node.lineno,
                        })
            return routes
        except:
            return []

    # --- Architecture Extraction ---
    def analyze_project_structure(self, files: List[Dict]) -> Dict:
        """Analyze project structure to identify architecture patterns."""
        layers = defaultdict(list)
        patterns = {
            "backend": [r'app/', r'src/', r'backend/'],
            "services": [r'services/', r'service/'],
            "models": [r'models/', r'model/', r'entities/'],
            "api": [r'api/', r'routes/', r'endpoints/'],
            "migrations": [r'migrations/', r'db/'],
            "config": [r'config/', r'settings/', r'core/'],
        }

        for file_info in files:
            path = file_info.get("path", "")
            for layer_name, layer_patterns in patterns.items():
                for pattern in layer_patterns:
                    if re.search(pattern, path):
                        layers[layer_name].append(path)
                        break

        return {
            "layers": dict(layers),
            "pattern_count": {k: len(v) for k, v in layers.items()},
        }

    def detect_framework(self, files: List[Dict]) -> str:
        """Detect primary framework from file names."""
        all_paths = " ".join(f.get("path", "") for f in files)

        framework_scores = {
            "FastAPI": ["fastapi", "main.py", "app/main"],
            "Django": ["django", "settings.py", "urls.py", "wsgi.py"],
            "Flask": ["flask", "app.py", "run.py"],
            "React": ["react", "jsx", "tsx", "component"],
            "Vue": ["vue", "vue-component"],
            "Node/Express": ["express", "node_modules", "package.json", "routes"],
        }

        best_framework = "unknown"
        best_score = 0

        for framework, keywords in framework_scores.items():
            score = sum(1 for kw in keywords if kw in all_paths)
            if score > best_score:
                best_score = score
                best_framework = framework

        return best_framework

    # --- Service Discovery ---
    def discover_services(self, files: List[Dict]) -> List[Dict]:
        """Discover services from file paths and patterns."""
        services = []

        for file_info in files:
            path = file_info.get("path", "")
            # Look for service files
            if re.search(r'service', path, re.I):
                service_name = re.split(r'[/\\]', path)[-1].replace(".py", "").replace(".ts", "").replace(".js", "")
                services.append({
                    "name": service_name,
                    "path": path,
                    "type": self.detect_service_type(path),
                })

        return services

    def detect_service_type(self, path: str) -> str:
        """Detect service type from path."""
        if "auth" in path or "login" in path:
            return "authentication"
        if "ingest" in path or "process" in path:
            return "ingestion"
        if "api" in path or "router" in path:
            return "api"
        if "embed" in path:
            return "embedding"
        if "search" in path:
            return "search"
        return "utility"

    async def analyze_repository(self, repository_id: UUID) -> Dict:
        """Full repository analysis."""
        import sqlalchemy as sa
        from app.models.project import Repository, RepositoryFile

        # Get repository
        result = await self.db.execute(
            sa.select(RepositoryFile).where(RepositoryFile.repository_id == repository_id)
        )
        files = result.scalars().all()

        if not files:
            return {"error": "No files found for repository"}

        file_infos = [
            {
                "path": f.path,
                "language": f.language,
                "content": f.content,
                "content_hash": f.content_hash,
                "size_bytes": f.size_bytes,
            }
            for f in files
        ]

        # Analyze
        all_deps = []
        all_routes = []
        for fi in file_infos:
            if fi["content"]:
                deps = self.extract_dependencies(fi["content"], fi["language"] or "")
                all_deps.extend(deps)
                routes = self.extract_api_routes(fi["content"], fi["language"] or "")
                all_routes.extend(routes)

        architecture = self.analyze_project_structure(file_infos)
        framework = self.detect_framework(file_infos)
        services = self.discover_services(file_infos)

        return {
            "framework": framework,
            "dependencies": list(set(all_deps)),
            "dependency_categories": {
                cat: [d for d in all_deps if self.categorize_dependency(d) == cat]
                for cat in ["internal", "third_party", "framework", "unknown"]
            },
            "api_routes": all_routes,
            "architecture": architecture,
            "services": services,
            "file_count": len(files),
        }


async def get_repository_analyzer(db: AsyncSession = Depends(get_db_session)) -> RepositoryAnalyzer:
    return RepositoryAnalyzer(db)