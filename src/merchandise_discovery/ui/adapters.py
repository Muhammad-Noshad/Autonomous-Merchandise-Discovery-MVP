"""Adapters from application contracts to the UI's stable view models.

The visual components were built against fixture models first. These adapters let the same layout
consume persisted workflow records without making Streamlit components aware of MongoDB or Pydantic
storage details.
"""

from datetime import datetime

from merchandise_discovery.application.discovery_service import RunSnapshot
from merchandise_discovery.domain.models.common import RunStatus, StageStatus
from merchandise_discovery.domain.models.workflow import StageExecution, WorkflowRun
from merchandise_discovery.domain.stages.registry import (
    stage_definitions_for,
    visible_stage_numbers,
)
from merchandise_discovery.ui.fixtures import (
    EvidenceFixture,
    RunFixture,
    RunListItemFixture,
    StageFixture,
)


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


def _visible_stage_count(run: WorkflowRun) -> int:
    """Return the active stage count used by the selected pipeline's UI progress summary."""

    return len(visible_stage_numbers(run.config.pipeline_variant))


def _stage_metrics(stage: StageExecution) -> dict[str, str]:
    """Build operational and provider metrics without reporting fake zero-cost AI usage."""

    metrics = {
        "Attempt": str(stage.attempt_number),
        "State version": str(stage.version),
    }
    has_provider_usage = (
        stage.usage.provider != "fixture"
        or stage.usage.total_tokens > 0
        or stage.usage.image_count > 0
        or stage.usage.estimated_cost_usd > 0
    )
    if has_provider_usage:
        metrics.update(
            {
                "Provider": stage.usage.provider,
                "Model": stage.usage.model,
                "Tokens": f"{stage.usage.total_tokens:,}",
                "Est. cost": f"${stage.usage.estimated_cost_usd:.6f}"
                + (" · estimated" if stage.usage.cost_is_estimate else ""),
            }
        )
    return metrics


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

    total_stages = _visible_stage_count(run)
    progress = round(min(run.completed_stages, total_stages) / total_stages * 100)
    return RunListItemFixture(
        run_id=run.run_id,
        title=run.title,
        pipeline_variant=run.config.pipeline_variant.value,
        selection_seed=run.config.selection_seed,
        status=run.status,
        progress=progress,
        updated=_format_timestamp(run.updated_at),
        triggered_by=run.triggered_by,
    )


def snapshot_to_fixture(snapshot: RunSnapshot) -> RunFixture:
    """Map a persisted run snapshot to the existing pipeline/detail view model."""

    run = snapshot.run
    visible_numbers = visible_stage_numbers(run.config.pipeline_variant)
    stage_purposes = {
        definition.number: definition.purpose
        for definition in stage_definitions_for(run.config.pipeline_variant)
    }
    stage_names = {
        definition.number: definition.name
        for definition in stage_definitions_for(run.config.pipeline_variant)
    }
    stages = [
        stage for stage in _latest_stages(snapshot.stages) if stage.stage_number in visible_numbers
    ]
    total_stages = len(visible_numbers)
    completed_stages = min(run.completed_stages, total_stages)
    total_tokens = sum(stage.usage.total_tokens for stage in stages)
    estimated_cost = round(sum(stage.usage.estimated_cost_usd for stage in stages), 8)
    cost_is_estimate = any(stage.usage.cost_is_estimate for stage in stages)
    logs_by_stage: dict[int, list[str]] = {}
    for log in snapshot.logs:
        if log.stage_number is not None:
            logs_by_stage.setdefault(log.stage_number, []).append(log.message)
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
            name=stage_names.get(stage.stage_number, stage.stage_name),
            summary=(
                "Search selected niches, synthesize lived experience, and generate concepts, briefs, and artwork prompts."
                if stage.stage_number == 6 and "AI Merchandise" in stage.stage_name
                else stage_purposes.get(stage.stage_number, "Persisted workflow stage.")
            ),
            status=stage.status,
            duration=_format_duration(stage),
            progress=_progress_percent(stage),
            output_summary=stage.output_summary or "Stage output will appear after execution.",
            inputs={str(key): str(value) for key, value in stage.input_data.items()},
            input_payload=stage.input_data,
            output_payload=stage.output_data,
            metrics=_stage_metrics(stage),
            evidence=_evidence_fixtures(stage.output_data),
            artifacts=[str(item) for item in stage.output_data.get("artifacts", [])]
            if isinstance(stage.output_data.get("artifacts", []), list)
            else [],
            error_message=stage.error_message,
            logs=logs_by_stage.get(stage.stage_number, []),
        )
        for stage in stages
    ]
    return RunFixture(
        run_id=run.run_id,
        title=run.title,
        pipeline_variant=run.config.pipeline_variant.value,
        selection_seed=run.config.selection_seed,
        status=run.status,
        completed_stages=completed_stages,
        total_stages=total_stages,
        estimated_remaining="Calculating" if run.status == RunStatus.RUNNING else "—",
        started=_format_timestamp(run.created_at),
        triggered_by=run.triggered_by,
        version=f"state {run.version}",
        current_stage_number=current_stage,
        stages=stage_fixtures,
        last_error=run.last_error,
        total_tokens=total_tokens,
        estimated_cost_usd=estimated_cost,
        cost_is_estimate=cost_is_estimate,
    )
