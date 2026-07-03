from typing import Dict, List, Optional, TypedDict


class AgentResult(TypedDict, total=False):
    result: str
    confidence: float
    recommendations: List[str]
    follow_up_actions: List[str]
    details: Optional[Dict]
