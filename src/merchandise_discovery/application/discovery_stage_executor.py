"""Executor for the deterministic discovery and research stages.

The executor owns orchestration concerns: loading prior stage outputs, supplying repositories and
providers to stage functions, and persisting artifact snapshots. Each stage module remains
independently portable and provider dependencies are injected here.
"""

from merchandise_discovery.application.stage_executor import StageNotImplementedError, StageResult
from merchandise_discovery.domain.models.workflow import StageExecution, WorkflowRun
from merchandise_discovery.domain.stages import stage_01_seed_discovery as stage_01
from merchandise_discovery.domain.stages import stage_02_identity_expansion as stage_02
from merchandise_discovery.domain.stages import stage_03_intersection_generation as stage_03
from merchandise_discovery.domain.stages import stage_04_coherence_hypothesis as stage_04
from merchandise_discovery.domain.stages import stage_05_pre_research_filter as stage_05
from merchandise_discovery.domain.stages import stage_06_niche_research as stage_06
from merchandise_discovery.domain.stages import stage_07_experience_mining as stage_07
from merchandise_discovery.domain.stages import stage_08_opportunity_scoring as stage_08
from merchandise_discovery.infrastructure.mongo.repositories.evidence_repository import (
    EvidenceRepository,
)
from merchandise_discovery.infrastructure.mongo.repositories.intersection_repository import (
    IntersectionRepository,
)
from merchandise_discovery.infrastructure.mongo.repositories.niche_repository import NicheRepository
from merchandise_discovery.infrastructure.mongo.repositories.seed_repository import SeedRepository
from merchandise_discovery.infrastructure.mongo.repositories.stage_execution_repository import (
    StageExecutionRepository,
)
from merchandise_discovery.infrastructure.providers.research_provider import ResearchProvider
from merchandise_discovery.shared.seed_loader import load_seed_fixture


class DiscoveryStageExecutor:
    """Load, run, and persist Stages 1-8 without coupling domain code to MongoDB."""

    def __init__(
        self,
        seed_repository: SeedRepository,
        intersection_repository: IntersectionRepository,
        stage_repository: StageExecutionRepository,
        niche_repository: NicheRepository,
        evidence_repository: EvidenceRepository,
        research_provider: ResearchProvider,
    ):
        self._seeds = seed_repository
        self._intersections = intersection_repository
        self._stage_repository = stage_repository
        self._niches = niche_repository
        self._evidence = evidence_repository
        self._research_provider = research_provider

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
        if stage.stage_number == 6:
            prior = stage_05.PreResearchFilterOutput.model_validate(previous.output_data)
            return stage_06.NicheResearchInput(
                intersections=prior.accepted,
                max_researched_niches=run.config.max_researched_niches,
            ).model_dump(mode="python")
        if stage.stage_number == 7:
            prior = stage_06.NicheResearchOutput.model_validate(previous.output_data)
            return stage_07.ExperienceMiningInput(
                niches=prior.niches,
                evidence=prior.evidence,
            ).model_dump(mode="python")
        if stage.stage_number == 8:
            research = self._stage_repository.get_latest(run.run_id, 6)
            if research is None or not research.output_data:
                raise ValueError("Stage 8 is missing Stage 6 research output.")
            research_output = stage_06.NicheResearchOutput.model_validate(research.output_data)
            mined = stage_07.ExperienceMiningOutput.model_validate(previous.output_data)
            return stage_08.OpportunityScoreInput(
                niches=research_output.niches,
                signals=mined.signals,
            ).model_dump(mode="python")
        raise StageNotImplementedError(
            f"Stage {stage.stage_number} ({stage.stage_name}) has no registered handler yet."
        )

    def execute(self, run: WorkflowRun, stage: StageExecution, input_data: dict) -> StageResult:
        """Run one supported stage and retain exact input/output payloads for auditability."""

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
        elif stage.stage_number == 6:
            input_model = stage_06.NicheResearchInput.model_validate(input_data)
            output = stage_06.execute(input_model, self._research_provider, run_id=run.run_id)
            self._niches.replace_for_run(run.run_id, output.niches)
            self._evidence.replace_for_run(run.run_id, output.evidence)
            summary = (
                f"Researched {len(output.niches)} niches and stored "
                f"{len(output.evidence)} source records."
            )
        elif stage.stage_number == 7:
            input_model = stage_07.ExperienceMiningInput.model_validate(input_data)
            output = stage_07.execute(input_model)
            summary = f"Mined recurring experience signals for {len(output.signals)} niches."
        elif stage.stage_number == 8:
            input_model = stage_08.OpportunityScoreInput.model_validate(input_data)
            output = stage_08.execute(input_model)
            self._niches.replace_for_run(run.run_id, output.niches)
            summary = f"Scored and ranked {len(output.scores)} researched niches."
        else:
            raise StageNotImplementedError(
                f"Stage {stage.stage_number} ({stage.stage_name}) has no registered handler yet."
            )

        return StageResult(
            input_data=input_model.model_dump(mode="python"),
            output_data=output.model_dump(mode="python"),
            output_summary=summary,
        )
