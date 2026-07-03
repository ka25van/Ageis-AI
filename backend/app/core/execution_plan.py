from dataclasses import dataclass, field
from typing import Dict, List, Optional
from uuid import UUID, uuid4


@dataclass
class RetryPolicy:
    max_retries: int = 3
    retry_delay_seconds: float = 2.0
    backoff_multiplier: float = 2.0


@dataclass
class RollbackStrategy:
    steps: List[str] = field(default_factory=list)
    automatic: bool = False


@dataclass
class ExecutionStep:
    id: str
    name: str
    description: str = ""
    capability: str = ""
    input: Dict = field(default_factory=dict)
    depends_on: List[str] = field(default_factory=list)
    requires_approval: bool = False
    retry_policy: Optional[RetryPolicy] = None
    timeout_seconds: Optional[int] = None
    expected_output: str = ""
    rollback_step: Optional[str] = None


@dataclass
class ExecutionPlan:
    plan_id: str = ""
    intent: str = ""
    task_description: str = ""
    steps: List[ExecutionStep] = field(default_factory=list)
    required_capabilities: List[str] = field(default_factory=list)
    approvals_required: List[str] = field(default_factory=list)
    rollback_strategy: Optional[RollbackStrategy] = None
    estimated_duration_seconds: Optional[int] = None
    metadata: Dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.plan_id:
            self.plan_id = str(uuid4())
