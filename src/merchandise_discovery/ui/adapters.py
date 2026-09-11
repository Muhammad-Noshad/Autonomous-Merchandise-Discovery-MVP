"""Adapters from application contracts to the UI's stable view models.

The visual components were built against fixture models first. These adapters let the same layout
consume persisted workflow records without making Streamlit components aware of MongoDB or Pydantic
storage details.
"""

from datetime import datetime

from merchandise_discovery.application.discovery_service import RunSnapshot
from merchandise_discovery.domain.models.common import RunStatus, StageStatus
from merchandise_discovery.domain.models.workflow import StageExecution, WorkflowRun
from merchandise_discovery.domain.stages.registry import STAGE_DEFINITIONS
from merchandise_discovery.ui.fixtures import (
    EvidenceFixture,
    RunFixture,
    RunListItemFixture,
    StageFixture,
)

STAGE_PURPOSES = {definition.number: definition.purpose for definition in STAGE_DEFINITIONS}


def _format_duration(stage: StageExecution) -> str:
    """Format persisted stage timestamps for compact pipeline labels."""

    if stage.started_at is None:
        return "Optional" if stage.status == StageStatus.SKIPPED else "Queued"
    end = stage.completed_at or stage.updated_at
    seconds = max(0, int((end - stage.started_at).total_seconds()))
    if seconds < 60:
        return f"{seconds}s"
    return f"{seconds // 60}m {seconds % 60:02d}s"


def _format_timestamp(value: datetime) -> str:
    """Format a UTC timestamp without exposing an implementation-specific datetime object to UI."""

    return value.astimezone().strftime("%Y-%m-%d %H:%M %Z")


def _progress_percent(stage: StageExecution) -> int:
    """Convert validated stage progress into the percentage expected by Streamlit."""

    if stage.progress_total < 1:
        return 0
    return min(100, round(stage.progress_current / stage.progress_total * 100))


def _latest_stages(stages: list[StageExecution]) -> list[StageExecution]:
    """Keep the newest attempt per stage while preserving pipeline order for the detail page."""

    latest: dict[int, StageExecution] = {}
    for stage in stages:
        current = latest.get(stage.stage_number)
        if current is None or stage.attempt_number >= current.attempt_number:
            latest[stage.stage_number] = stage
    return [latest[number] for number in sorted(latest)]


def _evidence_fixtures(payload: dict) -> list[EvidenceFixture]:
    """Map Stage 6's serialized evidence into the citations used by the detail panel."""

    records = payload.get("evidence", [])
    if not isinstance(records, list):
        return []
    return [
        EvidenceFixture(
            title=str(record.get("title", "Untitled source")),
            source=str(record.get("source", "Unknown source")),
            date=str(record.get("retrieved_at", "Not recorded"))[:10],
            excerpt=str(record.get("excerpt", "No excerpt recorded.")),
        )
        for record in records
        if isinstance(record, dict)
    ]


def workflow_to_list_item(run: WorkflowRun) -> RunListItemFixture:
    """Map a persisted run aggregate to the compact history-row contract."""

    progress = round(run.completed_stages / run.total_stages * 100)
    return RunListItemFixture(
        run_id=run.run_id,
        title=run.title,
        status=run.status,
        progress=progress,
        updated=_format_timestamp(run.updated_at),
        triggered_by=run.triggered_by,
    )


def snapshot_to_fixture(snapshot: RunSnapshot) -> RunFixture:
    """Map a persisted run snapshot to the existing pipeline/detail view model."""

    run = snapshot.run
    stages = _latest_stages(snapshot.stages)
    current_stage = run.current_stage_number or next(
        (
            stage.stage_number
            for stage in stages
            if stage.status not in {StageStatus.COMPLETED, StageStatus.SKIPPED}
        ),
        1,
    )
    stage_fixtures = [
        StageFixture(
            number=stage.stage_number,
            name=stage.stage_name,
            summary=STAGE_PURPOSES.get(stage.stage_number, "Persisted workflow stage."),
            status=stage.status,
            duration=_format_duration(stage),
            progress=_progress_percent(stage),
            output_summary=stage.output_summary or "Stage output will appear after execution.",
            inputs={str(key): str(value) for key, value in stage.input_data.items()},
            input_payload=stage.input_data,
            output_payload=stage.output_data,
            metrics={"Attempt": str(stage.attempt_number), "State version": str(stage.version)},
            evidence=_evidence_fixtures(stage.output_data),
            artifacts=[str(item) for item in stage.output_data.get("artifacts", [])]
            if isinstance(stage.output_data.get("artifacts", []), list)
            else [],
            error_message=stage.error_message,
        )
        for stage in stages
    ]
    return RunFixture(
        run_id=run.run_id,
        title=run.title,
        status=run.status,
        completed_stages=run.completed_stages,
        total_stages=run.total_stages,
        estimated_remaining="Calculating" if run.status == RunStatus.RUNNING else "—",
        started=_format_timestamp(run.created_at),
        triggered_by=run.triggered_by,
        version=f"state {run.version}",
        current_stage_number=current_stage,
        stages=stage_fixtures,
        last_error=run.last_error,
    )
