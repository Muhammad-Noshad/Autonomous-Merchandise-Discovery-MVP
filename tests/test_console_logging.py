"""Tests for concise, stage-attributed terminal reporting."""

from merchandise_discovery.domain.models.workflow import StageExecution
from merchandise_discovery.shared.logging import (
    stage_ended,
    stage_error,
    stage_progress,
    stage_started,
)


def test_stage_console_reporter_formats_lifecycle_boundaries(capsys) -> None:
    """Successful output contains milestones without dumping stage payloads."""

    stage = StageExecution(
        run_id="run-1",
        stage_number=1,
        stage_name="Autonomous Seed Discovery",
    )

    stage_started(stage, stage.run_id)
    stage_progress(stage, "Input prepared")
    stage_ended(stage, "Selected 3 seed groups.")

    output = capsys.readouterr().out
    assert "STAGE 01 | Autonomous Seed Discovery | STARTED | run run-1" in output
    assert "[STAGE 01 | Autonomous Seed Discovery] Input prepared" in output
    assert "[STAGE 01 | Autonomous Seed Discovery] ENDED | Selected 3 seed groups." in output


def test_stage_console_reporter_labels_errors_with_stage(capsys) -> None:
    """Failure output identifies the exact stage and exception type."""

    stage = StageExecution(run_id="run-1", stage_number=3, stage_name="Intersection Generation")

    stage_error(stage, ValueError("invalid provider output"))

    output = capsys.readouterr().out
    assert "[STAGE 03 | Intersection Generation] ERROR | ValueError: invalid provider output" in output
