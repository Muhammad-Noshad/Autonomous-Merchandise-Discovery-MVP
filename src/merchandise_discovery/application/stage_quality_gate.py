"""Post-stage quality gates for durable workflow execution.

The stage executor owns transformations and the orchestrator owns sequencing. This module owns the
shared safety rule between them: a required stage may not be persisted as completed when it has no
usable output for its successor. Keeping this rule at the execution boundary prevents baseline,
compact, worker, and Streamlit execution paths from drifting apart.
"""

from collections.abc import Iterable

from merchandise_discovery.application.stage_executor import StageResult
from merchandise_discovery.domain.models.common import PipelineVariant
from merchandise_discovery.domain.models.workflow import StageExecution, WorkflowRun


class StageQualityError(ValueError):
    """Raised when a stage completes technically but produces no usable workflow output."""


_BASELINE_OUTPUTS: dict[int, tuple[str, ...]] = {
    1: ("selected_seeds",),
    2: ("identities",),
    3: ("intersections",),
    4: ("selected_intersection_ids",),
    5: ("accepted",),
    6: ("niches", "evidence"),
    7: ("signals",),
    8: ("scores",),
    9: ("concepts",),
    10: ("evaluations",),
    11: ("survivors",),
    12: ("finalists",),
    13: ("briefs",),
    14: ("prompts",),
    15: ("artworks",),
    16: ("evaluations",),
    17: ("artworks",),
    18: ("artworks",),
}

_COMPACT_OUTPUTS: dict[int, tuple[str, ...]] = {
    1: ("selected_seeds",),
    2: ("identities",),
    3: ("intersections",),
    4: ("selected_intersection_ids",),
    6: ("niches", "concepts"),
    7: ("artworks",),
    8: ("evaluations",),
    9: ("artworks",),
    10: ("artworks",),
}

_SOCIAL_BEHAVIOR_OUTPUTS: dict[int, tuple[str, ...]] = {
    1: ("candidates",),
    2: ("artworks",),
}


def _required_outputs(variant: PipelineVariant, stage_number: int) -> tuple[str, ...]:
    """Return the collections that must contain records for this pipeline stage."""

    if variant == PipelineVariant.SOCIAL_BEHAVIOR_TEXT:
        return _SOCIAL_BEHAVIOR_OUTPUTS.get(stage_number, ())
    outputs = _COMPACT_OUTPUTS if variant == PipelineVariant.COMPACT_RESEARCH_FIRST else _BASELINE_OUTPUTS
    return outputs.get(stage_number, ())


def _non_empty_keys(output_data: dict, keys: Iterable[str]) -> list[str]:
    """Identify required collections that are missing, malformed, or empty."""

    return [
        key
        for key in keys
        if not isinstance(output_data.get(key), list) or not output_data[key]
    ]


def validate_stage_result(
    run: WorkflowRun,
    stage: StageExecution,
    result: StageResult,
) -> None:
    """Reject empty required outputs before the stage can become durably completed.

    Stage 7 is a semantic gate in addition to the generic collection checks: a signal record with
    no supporting evidence is not usable for concept generation. Partial research remains allowed;
    only the case where every signal is unsupported fails the run.
    """

    required_keys = _required_outputs(run.config.pipeline_variant, stage.stage_number)
    missing_keys = _non_empty_keys(result.output_data, required_keys)
    if missing_keys:
        missing = ", ".join(missing_keys)
        raise StageQualityError(
            f"Stage {stage.stage_number:02d} ({stage.stage_name}) produced no usable output in: "
            f"{missing}. The run cannot continue because the next stage has no candidates."
        )

    if stage.stage_number == 7:
        signals = result.output_data.get("signals", [])
        evidence_backed = [
            signal for signal in signals if isinstance(signal, dict) and signal.get("evidence_ids")
        ]
        if result.input_data.get("niches") and not evidence_backed:
            raise StageQualityError(
                "Stage 07 (Experience Mining) produced no evidence-backed experience signals. "
                "Research excerpts may be insufficient for concept generation."
            )
