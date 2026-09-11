"""Deterministic executor for the first five discovery stages.

The executor owns orchestration concerns: loading prior stage outputs, supplying repositories to
stage functions, and persisting artifact snapshots. Each stage module remains a pure transformation
that can later be moved behind a worker, API, or test harness independently.
"""

from merchandise_discovery.application.stage_executor import StageNotImplementedError, StageResult
from merchandise_discovery.domain.models.workflow import StageExecution, WorkflowRun
from merchandise_discovery.domain.stages import stage_01_seed_discovery as stage_01
from merchandise_discovery.domain.stages import stage_02_identity_expansion as stage_02
from merchandise_discovery.domain.stages import stage_03_intersection_generation as stage_03
from merchandise_discovery.domain.stages import stage_04_coherence_hypothesis as stage_04
from merchandise_discovery.domain.stages import stage_05_pre_research_filter as stage_05
from merchandise_discovery.infrastructure.mongo.repositories.intersection_repository import (
    IntersectionRepository,
)
from merchandise_discovery.infrastructure.mongo.repositories.seed_repository import SeedRepository
from merchandise_discovery.infrastructure.mongo.repositories.stage_execution_repository import (
    StageExecutionRepository,
)
from merchandise_discovery.shared.seed_loader import load_seed_fixture


class DiscoveryStageExecutor:
    """Load, run, and persist Stages 1–5 without coupling domain code to MongoDB."""

    def __init__(
        self,
        seed_repository: SeedRepository,
        intersection_repository: IntersectionRepository,
        stage_repository: StageExecutionRepository,
    ):
        self._seeds = seed_repository
        self._intersections = intersection_repository
        self._stage_repository = stage_repository

    def prepare(self, run: WorkflowRun, stage: StageExecution) -> dict:
        """Build a serializable input payload from run configuration and prior stage output."""

        if stage.stage_number == 1:
            return stage_01.SeedDiscoveryInput(
                seed_source=run.config.seed_source,
                max_seed_items=max(6, min(12, run.config.max_intersections + 2)),
            ).model_dump(mode="python")

        previous = self._stage_repository.get_latest(run.run_id, stage.stage_number - 1)
        if previous is None or not previous.output_data:
            raise ValueError(f"Stage {stage.stage_number} is missing prior stage output.")

        if stage.stage_number == 2:
            prior = stage_01.SeedDiscoveryOutput.model_validate(previous.output_data)
            return stage_02.IdentityExpansionInput(selected_seeds=prior.selected_seeds).model_dump(
                mode="python"
            )
        if stage.stage_number == 3:
            prior = stage_02.IdentityExpansionOutput.model_validate(previous.output_data)
            return stage_03.IntersectionGenerationInput(
                identities=prior.identities,
                max_intersections=run.config.max_intersections,
            ).model_dump(mode="python")
        if stage.stage_number == 4:
            prior = stage_03.IntersectionGenerationOutput.model_validate(previous.output_data)
            return stage_04.CoherenceInput(intersections=prior.intersections).model_dump(mode="python")
        if stage.stage_number == 5:
            prior = stage_04.CoherenceOutput.model_validate(previous.output_data)
            return stage_05.PreResearchFilterInput(
                intersections=prior.intersections,
                max_intersections=run.config.max_intersections,
            ).model_dump(mode="python")
        raise StageNotImplementedError(
            f"Stage {stage.stage_number} ({stage.stage_name}) has no registered handler yet."
        )

    def execute(self, run: WorkflowRun, stage: StageExecution, input_data: dict) -> StageResult:
        """Run one supported stage and retain the exact input/output payloads for auditability."""

        if stage.stage_number == 1:
            input_model = stage_01.SeedDiscoveryInput.model_validate(input_data)
            seeds = self._seeds.list_all()
            if not seeds:
                seeds = load_seed_fixture()
                self._seeds.replace_all(seeds)
            output = stage_01.execute(input_model, seeds)
            summary = f"Selected {len(output.selected_seeds)} seed groups."
        elif stage.stage_number == 2:
            input_model = stage_02.IdentityExpansionInput.model_validate(input_data)
            output = stage_02.execute(input_model)
            summary = f"Expanded {len(output.identities)} identity dimensions."
        elif stage.stage_number == 3:
            input_model = stage_03.IntersectionGenerationInput.model_validate(input_data)
            output = stage_03.execute(input_model, run_id=run.run_id)
            summary = f"Generated {len(output.intersections)} candidate intersections."
        elif stage.stage_number == 4:
            input_model = stage_04.CoherenceInput.model_validate(input_data)
            output = stage_04.execute(input_model)
            summary = f"Scored {len(output.intersections)} intersections with hypotheses."
        elif stage.stage_number == 5:
            input_model = stage_05.PreResearchFilterInput.model_validate(input_data)
            output = stage_05.execute(input_model)
            self._intersections.replace_for_run(run.run_id, output.all_intersections)
            summary = (
                f"Accepted {len(output.accepted)} of {len(output.all_intersections)} "
                "intersections for research."
            )
        else:
            raise StageNotImplementedError(
                f"Stage {stage.stage_number} ({stage.stage_name}) has no registered handler yet."
            )

        return StageResult(
            input_data=input_model.model_dump(mode="python"),
            output_data=output.model_dump(mode="python"),
            output_summary=summary,
        )
