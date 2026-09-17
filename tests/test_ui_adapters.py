"""Tests for converting persisted workflow contracts into stable UI view models."""

from merchandise_discovery.application.discovery_service import RunSnapshot
from merchandise_discovery.domain.models.common import RunStatus, StageStatus
from merchandise_discovery.domain.models.usage import UsageMetrics
from merchandise_discovery.domain.models.workflow import StageExecution, WorkflowRun
from merchandise_discovery.ui.adapters import snapshot_to_fixture, workflow_to_list_item


def test_snapshot_adapter_preserves_persisted_stage_state() -> None:
    """Live detail data retains status, progress, attempts, output, and errors for the UI."""

    run = WorkflowRun(title="Live detail")
    stage = StageExecution(
        run_id=run.run_id,
        stage_number=1,
        stage_name="Seed discovery",
        status=StageStatus.FAILED,
        progress_current=2,
        progress_total=4,
        attempt_number=2,
        input_data={"seed_limit": 5},
        output_data={"selected_seeds": [{"seed_id": "seed-1"}]},
        error_message="Provider unavailable",
    )

    fixture = snapshot_to_fixture(RunSnapshot(run=run, stages=[stage]))

    assert fixture.current_stage_number == 1
    assert fixture.stages[0].progress == 50
    assert fixture.stages[0].metrics["Attempt"] == "2"
    assert "Tokens" not in fixture.stages[0].metrics
    assert fixture.stages[0].error_message == "Provider unavailable"
    assert fixture.stages[0].summary.startswith("Select high-value audience")
    assert fixture.stages[0].input_payload == {"seed_limit": 5}
    assert fixture.stages[0].output_payload == {"selected_seeds": [{"seed_id": "seed-1"}]}


def test_workflow_adapter_calculates_history_progress() -> None:
    """Run history derives a bounded display percentage from persisted completion counts."""

    run = WorkflowRun(title="History", completed_stages=8)

    item = workflow_to_list_item(run)

    assert item.progress == 44


def test_completed_run_history_is_displayed_as_fully_complete() -> None:
    """A terminal run is 100% resolved even if its legacy counter omitted a skipped stage."""

    run = WorkflowRun(title="Legacy completed run", status=RunStatus.COMPLETED, completed_stages=16)

    item = workflow_to_list_item(run)
    fixture = snapshot_to_fixture(RunSnapshot(run=run, stages=[]))

    assert item.progress == 100
    assert fixture.completed_stages == fixture.total_stages == 18


def test_snapshot_adapter_shows_provider_usage_only_when_ai_is_used() -> None:
    """Provider-backed stages expose consumption while deterministic stages stay uncluttered."""

    run = WorkflowRun(title="Provider usage")
    stage = StageExecution(
        run_id=run.run_id,
        stage_number=1,
        stage_name="Seed discovery",
        usage=UsageMetrics(
            provider="openai",
            model="gpt-4o-mini",
            input_tokens=120,
            output_tokens=30,
            total_tokens=150,
            estimated_cost_usd=0.0002,
        ),
    )

    fixture = snapshot_to_fixture(RunSnapshot(run=run, stages=[stage]))

    assert fixture.stages[0].metrics["Provider"] == "openai"
    assert fixture.stages[0].metrics["Tokens"] == "150"
    assert fixture.stages[0].metrics["Est. cost"] == "$0.000200"


def test_snapshot_adapter_recovers_original_artwork_for_legacy_final_gallery() -> None:
    """Older final snapshots can use the preceding critique output for before/after comparison."""

    run = WorkflowRun(title="Legacy artwork comparison", completed_stages=18)
    original = {
        "artwork_id": "artwork-1",
        "source_url": "https://example.com/original.png",
        "storage_key": "artwork/original.png",
    }
    revised = {
        "artwork_id": "artwork-1",
        "source_url": "https://example.com/revised.png",
        "storage_key": "artwork/revised.png",
    }
    critique = StageExecution(
        run_id=run.run_id,
        stage_number=16,
        stage_name="Artwork Critique",
        status=StageStatus.COMPLETED,
        output_data={"artworks": [original], "evaluations": [{"artwork_id": "artwork-1"}]},
    )
    revision = StageExecution(
        run_id=run.run_id,
        stage_number=17,
        stage_name="Artwork Revision",
        status=StageStatus.COMPLETED,
        output_data={
            "artworks": [revised],
            "evaluations": [{"artwork_id": "artwork-1"}],
            "revisions": [{"artwork_id": "artwork-1", "revised": True}],
        },
    )
    final = StageExecution(
        run_id=run.run_id,
        stage_number=18,
        stage_name="Artwork Results",
        status=StageStatus.COMPLETED,
        output_data={"artworks": [revised], "evaluations": [{"artwork_id": "artwork-1"}]},
    )

    fixture = snapshot_to_fixture(RunSnapshot(run=run, stages=[critique, revision, final]))

    assert fixture.stages[-1].output_payload["original_artworks"] == [original]
