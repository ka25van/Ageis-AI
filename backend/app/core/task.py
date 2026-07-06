from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Optional
from uuid import UUID


class TaskSource(str, Enum):
    CHAT = "chat"
    API = "api"
    WEBHOOK_GITHUB = "webhook_github"
    PROMETHEUS = "prometheus"

    # Future sources (not yet implemented):
    # JENKINS = "jenkins"
    # CLOUDWATCH = "cloudwatch"
    # SLACK = "slack"
    # JIRA = "jira"
    # SCHEDULED = "scheduled"


class TaskType(str, Enum):
    QUESTION = "question"
    ANALYSIS = "analysis"
    ACTION = "action"
    INCIDENT = "incident"

    # Future types (not yet implemented):
    # DEPLOYMENT = "deployment"
    # CODE_REVIEW = "code_review"


@dataclass
class Task:
    source: TaskSource
    type: TaskType
    input: str
    project_id: UUID
    repository_id: Optional[UUID] = None
    user_id: Optional[UUID] = None
    metadata: Dict = field(default_factory=dict)
