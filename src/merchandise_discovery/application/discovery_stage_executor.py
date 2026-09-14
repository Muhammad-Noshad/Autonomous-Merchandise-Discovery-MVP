"""Executor for discovery stages and optional provider-backed reasoning.

The executor owns orchestration concerns: loading prior stage outputs, supplying repositories and
providers to stage functions, and persisting artifact snapshots. Each stage module remains
independently portable and provider dependencies are injected here.
"""

import json
import logging
from datetime import datetime
from pathlib import Path

from merchandise_discovery.application.stage_executor import StageNotImplementedError, StageResult
from merchandise_discovery.domain.models.common import StageStatus
from merchandise_discovery.domain.models.usage import UsageMetrics
from merchandise_discovery.domain.models.workflow import StageExecution, WorkflowRun
from merchandise_discovery.domain.stages import stage_01_seed_discovery as stage_01
from merchandise_discovery.domain.stages import stage_02_identity_expansion as stage_02
from merchandise_discovery.domain.stages import stage_03_intersection_generation as stage_03
from merchandise_discovery.domain.stages import stage_04_coherence_hypothesis as stage_04
from merchandise_discovery.domain.stages import stage_05_pre_research_filter as stage_05
from merchandise_discovery.domain.stages import stage_06_niche_research as stage_06
from merchandise_discovery.domain.stages import stage_07_experience_mining as stage_07
from merchandise_discovery.domain.stages import stage_08_opportunity_scoring as stage_08
from merchandise_discovery.domain.stages import stage_09_concept_generation as stage_09
from merchandise_discovery.domain.stages import stage_10_concept_critique as stage_10
from merchandise_discovery.domain.stages import stage_11_similarity_ip_check as stage_11
from merchandise_discovery.domain.stages import stage_12_final_selection as stage_12
from merchandise_discovery.domain.stages import stage_13_design_brief as stage_13
from merchandise_discovery.domain.stages import stage_14_prompt_compilation as stage_14
from merchandise_discovery.domain.stages import stage_15_artwork_generation as stage_15
from merchandise_discovery.domain.stages import stage_16_artwork_critique as stage_16
from merchandise_discovery.infrastructure.mongo.repositories.artwork_repository import (
    ArtworkRepository,
)
from merchandise_discovery.infrastructure.mongo.repositories.brief_repository import BriefRepository
from merchandise_discovery.infrastructure.mongo.repositories.concept_repository import (
    ConceptRepository,
)
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
from merchandise_discovery.infrastructure.providers.image_provider import ImageProvider
from merchandise_discovery.infrastructure.providers.reasoning_provider import ReasoningProvider
from merchandise_discovery.infrastructure.providers.research_provider import ResearchProvider
from merchandise_discovery.shared.seed_loader import load_seed_fixture


logger = logging.getLogger(__name__)


def _log_stage_01_results(
    run: WorkflowRun,
    output: stage_01.SeedDiscoveryOutput,
    usage: UsageMetrics,
) -> None:
    """Log Stage 1 OpenAI execution results to console and persisted text log files."""

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    header = (
        f"\n{'='*80}\n"
        f"🎯 STAGE 1: AUTONOMOUS SEED DISCOVERY EXECUTION\n"
        f"Timestamp: {timestamp}\n"
        f"Run ID: #{run.run_id} · '{run.title}'\n"
        f"Provider: {usage.provider} · Model: {usage.model}\n"
        f"Tokens: Input={usage.input_tokens}, Output={usage.output_tokens}, Total={usage.total_tokens}\n"
        f"Estimated Cost: ${usage.estimated_cost_usd:.6f} USD\n"
        f"Selected Seeds Count: {len(output.selected_seeds)}\n"
        f"{'-'*80}\n"
        f"EXECUTIVE SUMMARY:\n{output.executive_summary or 'Deterministic baseline selection.'}\n"
        f"{'-'*80}\n"
        f"SELECTED SEEDS & STRATEGIC REASONING:\n"
    )
    seed_lines = []
    eval_by_id = {e.get("seed_id"): e for e in output.evaluations if isinstance(e, dict)}
    for i, seed in enumerate(output.selected_seeds, 1):
        reason = output.selection_reasons.get(seed.seed_id, "N/A")
        eval_item = eval_by_id.get(seed.seed_id)
        potential = eval_item.get("merchandise_potential", "") if eval_item else ""
        appeal = eval_item.get("target_audience_appeal", "") if eval_item else ""

        entry = (
            f"  {i:02d}. [{seed.category.upper()}] {seed.name} (Priority: {seed.metadata.get('priority', 0)})\n"
            f"      Seed ID: {seed.seed_id}\n"
            f"      Strategic Rationale: {reason}\n"
        )
        if potential:
            entry += f"      Merchandise Potential: {potential}\n"
        if appeal:
            entry += f"      Target Audience Appeal: {appeal}\n"
        seed_lines.append(entry)

    footer = f"{'='*80}\n"
    full_report = header + "\n".join(seed_lines) + "\n" + footer

    # 1. Print directly to console for real-time validation
    print(full_report, flush=True)

    # 2. Write to log files in the project workspace
    for log_path in ["stage_01_results.txt", "logs/stage_01_results.txt"]:
        try:
            path = Path(log_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as file:
                file.write(full_report)
        except Exception as log_err:
            logger.warning("Could not append to %s: %s", log_path, log_err)


class DiscoveryStageExecutor:
    """Load, run, and persist Stages 1-16 without coupling domain code to MongoDB."""

    def __init__(
        self,
        seed_repository: SeedRepository,
        intersection_repository: IntersectionRepository,
        stage_repository: StageExecutionRepository,
        niche_repository: NicheRepository,
        evidence_repository: EvidenceRepository,
        research_provider: ResearchProvider,
        concept_repository: ConceptRepository,
        brief_repository: BriefRepository,
        artwork_repository: ArtworkRepository,
        image_provider: ImageProvider,
        reasoning_provider: ReasoningProvider | None = None,
    ):
        self._seeds = seed_repository
        self._intersections = intersection_repository
        self._stage_repository = stage_repository
        self._niches = niche_repository
        self._evidence = evidence_repository
        self._research_provider = research_provider
        self._concepts = concept_repository
        self._briefs = brief_repository
        self._artworks = artwork_repository
        self._image_provider = image_provider
        self._reasoning_provider = reasoning_provider

    def _reason(self, stage_name: str, input_data: dict, response_model):
        """Call structured reasoning while keeping prompts and SDK details outside stage modules."""

        if self._reasoning_provider is None:
            return None, UsageMetrics()
        response = self._reasoning_provider.complete_structured(
            system_prompt=(
                "You are a merchandise discovery specialist. Return only the requested structured "
                "output, preserve supplied IDs, do not invent citations, and keep recommendations "
                "specific to the observed audience experience."
            ),
            user_prompt=(
                f"Execute {stage_name}. Validate the following stage input and produce the requested "
                f"Pydantic output. Input JSON:\n{json.dumps(input_data, default=str)}"
            ),
            response_model=response_model,
        )
        return response.output, response.usage

    def prepare(self, run: WorkflowRun, stage: StageExecution) -> dict:
        """Build a serializable input payload from run configuration and prior stage output."""

        if stage.stage_number == 1:
            return stage_01.SeedDiscoveryInput(
                seed_source=run.config.seed_source,
                max_seed_items=max(6, min(12, run.config.max_intersections + 2)),
            ).model_dump(mode="python")

        previous = self._stage_repository.get_latest(run.run_id, stage.stage_number - 1)
        # Stage 11 is optional. When disabled, Stage 12 consumes the Stage 10 critique output.
        if stage.stage_number == 12 and (
            previous is None
            or previous.status == StageStatus.SKIPPED
            or not previous.output_data
        ):
            previous = self._stage_repository.get_latest(run.run_id, 10)
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
        if stage.stage_number == 9:
            prior = stage_08.OpportunityScoringOutput.model_validate(previous.output_data)
            return stage_09.ConceptGenerationInput(
                niches=prior.niches,
                concepts_per_niche=run.config.concepts_per_niche,
            ).model_dump(mode="python")
        if stage.stage_number == 10:
            prior = stage_09.ConceptGenerationOutput.model_validate(previous.output_data)
            return stage_10.ConceptCritiqueInput(concepts=prior.concepts).model_dump(mode="python")
        if stage.stage_number == 11:
            prior = stage_10.ConceptCritiqueOutput.model_validate(previous.output_data)
            return stage_11.SimilarityCheckInput(concepts=prior.concepts).model_dump(mode="python")
        if stage.stage_number == 12:
            if previous.stage_number == 11 and previous.output_data:
                prior = stage_11.SimilarityCheckOutput.model_validate(previous.output_data)
                concepts = prior.survivors
            else:
                prior = stage_10.ConceptCritiqueOutput.model_validate(previous.output_data)
                concepts = prior.concepts
            return stage_12.FinalSelectionInput(
                concepts=concepts,
                max_finalists=max(1, run.config.max_researched_niches),
            ).model_dump(mode="python")
        if stage.stage_number == 13:
            prior = stage_12.FinalSelectionOutput.model_validate(previous.output_data)
            return stage_13.DesignBriefInput(concepts=prior.finalists).model_dump(mode="python")
        if stage.stage_number == 14:
            prior = stage_13.DesignBriefOutput.model_validate(previous.output_data)
            return stage_14.PromptCompilationInput(briefs=prior.briefs).model_dump(mode="python")
        if stage.stage_number == 15:
            prior = stage_14.PromptCompilationOutput.model_validate(previous.output_data)
            return stage_15.ArtworkGenerationInput(
                prompts=prior.prompts,
                artwork_variants_per_concept=run.config.artwork_variants_per_concept,
            ).model_dump(mode="python")
        if stage.stage_number == 16:
            prior = stage_15.ArtworkGenerationOutput.model_validate(previous.output_data)
            return stage_16.ArtworkCritiqueInput(artworks=prior.artworks).model_dump(mode="python")
        raise StageNotImplementedError(
            f"Stage {stage.stage_number} ({stage.stage_name}) has no registered handler yet."
        )

    def execute(self, run: WorkflowRun, stage: StageExecution, input_data: dict) -> StageResult:
        """Run one supported stage and retain exact input/output payloads for auditability."""

        usage = UsageMetrics()
        if stage.stage_number == 1:
            input_model = stage_01.SeedDiscoveryInput.model_validate(input_data)
            seeds = self._seeds.list_all()
            if not seeds:
                seeds = load_seed_fixture()
                self._seeds.replace_all(seeds)

            candidates = stage_01.select_candidate_seeds(input_model, seeds)
            reasoning_output = None

            if self._reasoning_provider is not None:
                candidate_summary = [
                    {
                        "seed_id": s.seed_id,
                        "seed_name": s.name,
                        "category": s.category,
                        "priority": s.metadata.get("priority", 0),
                        "dimensions": s.metadata.get("dimensions", []),
                        "affinity_tags": s.metadata.get("affinity_tags", []),
                    }
                    for s in candidates
                ]
                system_prompt = (
                    "You are an expert merchandise discovery analyst and creative strategist. "
                    "Evaluate the candidate seed groups deterministically based on commercial merchandise "
                    "viability, emotional audience resonance, print-on-demand appeal, and cultural relevance. "
                    "Maintain strict factual consistency, evaluate every candidate seed, and return valid structured output."
                )
                user_prompt = (
                    f"Deterministically evaluate the following {len(candidates)} candidate seed groups for "
                    f"autonomous merchandise discovery in run '{run.title}' (ID: {run.run_id}).\n\n"
                    f"Candidate seeds JSON:\n{json.dumps(candidate_summary, indent=2)}\n\n"
                    "For each candidate seed, provide:\n"
                    "1. An insightful evaluation of merchandise potential (apparel, accessories, home goods, gifts).\n"
                    "2. Target audience emotional resonance and cultural tension.\n"
                    "3. A concise, strategic selection reason for why this seed was prioritized.\n"
                    "Also provide a high-level executive summary of the entire seed portfolio."
                )
                try:
                    structured_resp = self._reasoning_provider.complete_structured(
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        response_model=stage_01.Stage1ReasoningOutput,
                        temperature=0.0,
                    )
                    reasoning_output = structured_resp.output
                    usage = structured_resp.usage
                except Exception as err:
                    logger.warning("Stage 1 OpenAI evaluation failed; falling back to deterministic baseline: %s", err)

            output = stage_01.execute(
                input_model,
                seeds,
                reasoning_output=reasoning_output,
                model=usage.model if usage.provider != "fixture" else "deterministic",
            )
            summary = (
                f"Selected {len(output.selected_seeds)} seed groups with "
                f"{'OpenAI ' + usage.model if usage.provider != 'fixture' else 'deterministic'} reasoning."
            )
            _log_stage_01_results(run, output, usage)
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
            usage = output.usage
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
        elif stage.stage_number == 9:
            input_model = stage_09.ConceptGenerationInput.model_validate(input_data)
            provider_output, usage = self._reason(
                "Stage 9 merchandise concept generation",
                input_data,
                stage_09.ConceptGenerationOutput,
            )
            output = provider_output or stage_09.execute(input_model)
            if provider_output:
                allowed_niches = {niche.niche_id for niche in input_model.niches}
                output = output.model_copy(
                    update={
                        "concepts": [
                            concept.model_copy(update={"run_id": run.run_id})
                            for concept in output.concepts
                            if concept.niche_id in allowed_niches
                        ]
                    }
                )
                if not output.concepts:
                    raise ValueError("OpenAI concept generation returned no valid niche-linked concepts.")
            self._concepts.replace_for_run(run.run_id, output.concepts)
            summary = f"Generated {len(output.concepts)} merchandise concepts."
        elif stage.stage_number == 10:
            input_model = stage_10.ConceptCritiqueInput.model_validate(input_data)
            provider_output, usage = self._reason(
                "Stage 10 concept critique",
                input_data,
                stage_10.ConceptCritiqueOutput,
            )
            output = provider_output or stage_10.execute(input_model)
            self._concepts.replace_for_run(run.run_id, output.concepts)
            summary = f"Critiqued {len(output.evaluations)} merchandise concepts."
        elif stage.stage_number == 11:
            input_model = stage_11.SimilarityCheckInput.model_validate(input_data)
            output = stage_11.execute(input_model)
            self._concepts.replace_for_run(run.run_id, output.concepts)
            summary = (
                f"Screened {len(output.checks)} concepts; "
                f"{len(output.survivors)} survived the optional duplicate check."
            )
        elif stage.stage_number == 12:
            input_model = stage_12.FinalSelectionInput.model_validate(input_data)
            output = stage_12.execute(input_model)
            self._concepts.replace_for_run(run.run_id, output.concepts)
            summary = f"Selected {len(output.finalists)} concept finalists."
        elif stage.stage_number == 13:
            input_model = stage_13.DesignBriefInput.model_validate(input_data)
            provider_output, usage = self._reason(
                "Stage 13 structured design brief generation",
                input_data,
                stage_13.DesignBriefOutput,
            )
            output = provider_output or stage_13.execute(input_model)
            self._briefs.replace_for_run(run.run_id, output.briefs)
            summary = f"Created {len(output.briefs)} structured design briefs."
        elif stage.stage_number == 14:
            input_model = stage_14.PromptCompilationInput.model_validate(input_data)
            output = stage_14.execute(input_model)
            summary = f"Compiled {len(output.prompts)} constrained artwork prompts."
        elif stage.stage_number == 15:
            input_model = stage_15.ArtworkGenerationInput.model_validate(input_data)
            output = stage_15.execute(input_model, self._image_provider)
            usage = output.usage
            self._artworks.replace_for_run(run.run_id, output.artworks)
            summary = f"Generated {len(output.artworks)} artwork candidates."
        elif stage.stage_number == 16:
            input_model = stage_16.ArtworkCritiqueInput.model_validate(input_data)
            output = stage_16.execute(input_model)
            self._artworks.replace_for_run(run.run_id, output.artworks)
            accepted = sum(item.decision.value == "accept" for item in output.artworks)
            summary = f"QA checked {len(output.evaluations)} artworks; {accepted} passed."
        else:
            raise StageNotImplementedError(
                f"Stage {stage.stage_number} ({stage.stage_name}) has no registered handler yet."
            )

        return StageResult(
            input_data=input_model.model_dump(mode="python"),
            output_data=output.model_dump(mode="python"),
            output_summary=summary,
            usage=usage,
        )
