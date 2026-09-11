"""Shared stage contracts.

Stage-specific input and output models belong beside their stage implementation. These shared
contracts only define the boundary needed by the orchestrator and worker.
"""

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class StageContext:
    """Immutable execution context passed to a stage."""

    run_id: str
    attempt_number: int


class StageServices(Protocol):
    """Dependency boundary for repositories, providers, and storage services."""

    def __getattr__(self, name: str) -> Any:
        """Allow stage-specific dependencies without coupling stages to implementations."""

