"""Concise terminal reporting for workflow execution.

MongoDB stage logs remain the durable audit trail. These helpers only format operator-facing
terminal output so a worker run can be followed quickly without printing input/output payloads.
"""

from merchandise_discovery.domain.models.workflow import StageExecution


def _stage_label(stage: StageExecution) -> str:
    """Build one stable label used by every stage terminal message."""

    return f"STAGE {stage.stage_number:02d} | {stage.stage_name}"


def stage_started(stage: StageExecution, run_id: str) -> None:
    """Print a visual boundary when a stage begins."""

    print("\n" + "=" * 76, flush=True)
    print(f"{_stage_label(stage)} | STARTED | run {run_id}", flush=True)
    print("=" * 76, flush=True)


def stage_progress(stage: StageExecution, message: str) -> None:
    """Print one concise milestone without exposing payload contents."""

    print(f"[{_stage_label(stage)}] {message}", flush=True)


def stage_ended(stage: StageExecution, summary: str) -> None:
    """Print the successful stage boundary and its short result summary."""

    print(f"[{_stage_label(stage)}] ENDED | {summary}", flush=True)


def stage_error(stage: StageExecution, error: BaseException) -> None:
    """Print a stage-owned error so failures are attributable in multi-stage output."""

    print(
        f"[{_stage_label(stage)}] ERROR | {type(error).__name__}: {error}",
        flush=True,
    )
