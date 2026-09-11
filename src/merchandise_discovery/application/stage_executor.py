"""Boundary between workflow control flow and individual stage implementations.

The worker depends on this contract rather than importing stage modules directly. Chunk 3 provides
an explicit unavailable implementation so claimed runs fail visibly; later chunks register real
handlers one stage at a time.
"""

from dataclasses import dataclass
from typing import Protocol

from merchandise_discovery.domain.models.workflow import StageExecution, WorkflowRun


class StageNotImplementedError(RuntimeError):
    """Raised when the worker reaches a stage whose implementation is not registered yet."""


@dataclass(frozen=True)
class StageResult:
    """Structured output returned by a completed stage handler."""

    output_data: dict
    output_summary: str


class StageExecutor(Protocol):
    """Contract that concrete stage registries will implement in the next workflow chunk."""

    def execute(self, run: WorkflowRun, stage: StageExecution) -> StageResult:
        """Transform one claimed stage into a typed result or raise a stage-level failure."""


class UnavailableStageExecutor:
    """Fail clearly until a real stage handler is registered for the requested stage."""

    def execute(self, run: WorkflowRun, stage: StageExecution) -> StageResult:
        """Raise an actionable error without pretending an unimplemented stage succeeded."""

        raise StageNotImplementedError(
            f"Stage {stage.stage_number} ({stage.stage_name}) has no registered handler yet."
        )
