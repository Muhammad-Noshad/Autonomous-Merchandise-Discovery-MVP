"""Boundary between workflow control flow and individual stage implementations.

The worker depends on this contract rather than importing stage modules directly. Chunk 3 provides
an explicit unavailable implementation so claimed runs fail visibly; later chunks register real
handlers one stage at a time.
"""

from dataclasses import dataclass, field
from typing import Protocol

from merchandise_discovery.domain.models.usage import UsageMetrics
from merchandise_discovery.domain.models.workflow import StageExecution, WorkflowRun


class StageNotImplementedError(RuntimeError):
    """Raised when the worker reaches a stage whose implementation is not registered yet."""


@dataclass(frozen=True)
class StageResult:
    """Structured output returned by a completed stage handler."""

    input_data: dict
    output_data: dict
    output_summary: str
    usage: UsageMetrics = field(default_factory=UsageMetrics)


class StageExecutor(Protocol):
    """Contract that concrete stage registries will implement in the next workflow chunk."""

    def prepare(self, run: WorkflowRun, stage: StageExecution) -> dict:
        """Build the persisted input payload from the run and earlier stage outputs."""

    def execute(self, run: WorkflowRun, stage: StageExecution, input_data: dict) -> StageResult:
        """Transform one claimed stage into a typed result or raise a stage-level failure."""


class UnavailableStageExecutor:
    """Fail clearly until a real stage handler is registered for the requested stage."""

    def prepare(self, run: WorkflowRun, stage: StageExecution) -> dict:
        """Raise an actionable error before an unsupported stage can mutate its output."""

        raise StageNotImplementedError(
            f"Stage {stage.stage_number} ({stage.stage_name}) has no registered handler yet."
        )

    def execute(self, run: WorkflowRun, stage: StageExecution, input_data: dict) -> StageResult:
        """Raise an actionable error without pretending an unimplemented stage succeeded."""

        raise StageNotImplementedError(
            f"Stage {stage.stage_number} ({stage.stage_name}) has no registered handler yet."
        )
