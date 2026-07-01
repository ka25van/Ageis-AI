from typing import Dict, List, Optional, Any
from uuid import UUID
from collections import Counter
import re

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.di import get_db_session


class IncidentAgent:
    """Agent for analyzing logs, finding root causes, and recommending fixes."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # Common error patterns
    ERROR_PATTERNS = [
        r'error|exception|traceback|fail|crash|timeout|unreachable',
        r'500|502|503|504',
        r'stack overflow|out of memory|segmentation fault',
        r'connection refused|connection reset|broken pipe',
        r'permission denied|access denied|unauthorized',
        r'deprecated|removed|obsolete',
        r'not found|missing|nonexistent',
        r'invalid|corrupt|malformed|unexpected',
    ]

    ERROR_CATEGORIES = {
        'timeout': 'Performance',
        'memory': 'Resource',
        'permission': 'Security',
        'connection': 'Network',
        'invalid': 'Configuration',
        'not_found': 'Missing',
        'error': 'General',
    }

    async def analyze_logs(self, repository_id: UUID, log_path: str = None) -> Dict:
        """Analyze logs from a repository for error patterns."""
        from app.models.project import RepositoryFile

        result = await self.db.execute(
            select(RepositoryFile).where(RepositoryFile.repository_id == repository_id)
        )
        files = result.scalars().all()

        errors_found = []
        patterns = Counter()

        for f in files:
            if f.content:
                for pattern in self.ERROR_PATTERNS:
                    matches = re.findall(pattern, f.content, re.I)
                    if matches:
                        for match in matches:
                            errors_found.append({
                                "file": f.path,
                                "pattern": match,
                                "line": f.content.index(match) if match in f.content else 0,
                            })
                        patterns[len(matches)] += 1

        return {
            "errors_found": errors_found[:20],
            "total_errors": len(errors_found),
            "error_patterns": dict(patterns),
            "files_analyzed": len(files),
        }

    async def analyze_errors(self, repository_id: UUID) -> Dict:
        """Analyze error patterns for root cause classification."""
        from app.models.project import RepositoryFile

        result = await self.db.execute(
            select(RepositoryFile).where(RepositoryFile.repository_id == repository_id)
        )
        files = result.scalars().all()

        if not files:
            return {"error": "No files found"}

        categories = Counter()
        for f in files:
            if f.content:
                for category_key, category in self.ERROR_CATEGORIES.items():
                    if category_key in f.content.lower():
                        categories[category] += 1

        return {
            "categories": dict(categories),
            "total_issues": sum(categories.values()),
            "recommendations": self._generate_recommendations(categories),
        }

    async def root_cause_analysis(self, repository_id: UUID) -> Dict:
        """Find root causes from error patterns."""
        analysis = await self.analyze_errors(repository_id)

        # Find most common category
        if not analysis.get("categories"):
            return {"error": "No errors found", "recommendations": ["No issues detected"]}

        most_common = max(analysis["categories"], key=analysis["categories"].get)
        return {
            "root_cause": most_common,
            "error_count": analysis["total_issues"],
            "categories": analysis["categories"],
            "recommendations": analysis["recommendations"],
        }

    async def analyze_incidents(self, repository_id: UUID) -> Dict:
        """Analyze all incidents from the repository."""
        from app.models.project import RepositoryFile

        result = await self.db.execute(
            select(RepositoryFile).where(RepositoryFile.repository_id == repository_id)
        )
        files = result.scalars().all()

        if not files:
            return {"error": "No files found"}

        incidents = []
        for f in files:
            if f.content:
                for pattern in self.ERROR_PATTERNS:
                    matches = re.findall(pattern, f.content, re.I)
                    if matches:
                        incidents.append({
                            "file": f.path,
                            "pattern": pattern,
                            "language": f.language,
                            "severity": "high" if "traceback" in pattern else "medium",
                            "count": len(matches),
                        })

        return {
            "incidents": incidents[:10],
            "total_incidents": len(incidents),
        }

    def _generate_recommendations(self, categories: Counter) -> List[str]:
        """Generate recommendations based on error categories."""
        recommendations = []
        for category, count in categories.items():
            if category == "Security":
                recommendations.append("Review access controls and permissions")
            elif category == "Network":
                recommendations.append("Check network connectivity and firewalls")
            elif category == "Configuration":
                recommendations.append("Validate configuration files")
            elif category == "Resource":
                recommendations.append("Increase resource limits or optimize memory")
            elif category == "Performance":
                recommendations.append("Optimize queries and add caching")
            elif category == "Missing":
                recommendations.append("Verify all required dependencies are installed")
            else:
                recommendations.append(f"Investigate {category} issues")

        return recommendations


async def get_incident_agent(
    db: AsyncSession = Depends(get_db_session),
) -> IncidentAgent:
    return IncidentAgent(db)