from typing import Dict, List, Optional, Callable, Any, Awaitable
from fastapi import Depends


class CapabilityNotFoundError(Exception):
    pass


class Capability:
    def __init__(self, name: str, description: str, executor: Callable[..., Awaitable[Any]], execution_type: str = "agent"):
        self.name = name
        self.description = description
        self.executor = executor
        self.execution_type = execution_type


class CapabilityRegistry:
    def __init__(self):
        self._capabilities: Dict[str, Capability] = {}

    def register(self, name: str, description: str, executor: Callable[..., Awaitable[Any]], execution_type: str = "agent") -> None:
        self._capabilities[name] = Capability(name=name, description=description, executor=executor, execution_type=execution_type)

    def resolve(self, name: str) -> Capability:
        cap = self._capabilities.get(name)
        if not cap:
            raise CapabilityNotFoundError(f"Capability '{name}' not registered")
        return cap

    def has(self, name: str) -> bool:
        return name in self._capabilities

    def list_capabilities(self) -> List[Dict]:
        return [
            {"name": c.name, "description": c.description, "execution_type": c.execution_type}
            for c in self._capabilities.values()
        ]

    def list_names(self) -> List[str]:
        return list(self._capabilities.keys())

    def missing(self, names: List[str]) -> List[str]:
        return [n for n in names if n not in self._capabilities]


# Global singleton
registry = CapabilityRegistry()


def get_capability_registry() -> CapabilityRegistry:
    return registry
