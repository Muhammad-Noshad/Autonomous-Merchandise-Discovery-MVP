"""Executor for discovery stages and optional provider-backed reasoning.

The executor owns orchestration concerns: loading prior stage outputs, supplying repositories and
providers to stage functions, and persisting artifact snapshots. Each stage module remains
independently portable and provider dependencies are injected here.
"""

import json
import logging

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
from merchandise_discovery.infrastructure.storage import ArtworkStorage

logger = logging.getLogger(__name__)


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
        artwork_storage: ArtworkStorage | None = None,
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
        self._artwork_storage = artwork_storage
        self._reasoning_provider = reasoning_provider

    def _reason(
        self,
        stage_name: str,
        input_data: dict,
        response_model,
        instructions: str | None = None,
    ):
        """Call structured reasoning while keeping prompts and SDK details outside stage modules."""

        if self._reasoning_provider is None:
            return None, UsageMetrics()
        user_prompt = (
            f"Execute {stage_name}. Validate the following stage input and produce the requested "
            f"Pydantic output. Input JSON:\n{json.dumps(input_data, default=str)}"
        )
        if instructions:
            user_prompt = f"{instructions}\n\n{user_prompt}"
        response = self._reasoning_provider.complete_structured(
            system_prompt=(
                "You are a merchandise discovery specialist. Return only the requested structured "
                "output, preserve supplied IDs, do not invent citations, and keep recommendations "
                "specific to the observed audience experience."
            ),
            user_prompt=user_prompt,
            response_model=response_model,
        )
        return response.output, response.usage

    def prepare(self, run: WorkflowRun, stage: StageExecution) -> dict:
        """Build a serializable input payload from run configuration and prior stage output."""

        if stage.stage_number == 1:
            return stage_01.SeedDiscoveryInput(
                seed_source=run.config.seed_source,
                max_seed_items=max(6, min(12, run.config.max_intersections + 2)),
                selection_seed=run.config.selection_seed,
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
                raise ValueError("Seed knowledge is empty. Restart the application to seed MongoDB.")

            # Stage 1 is intentionally provider-free. Its responsibility is reproducible portfolio
            # sampling from MongoDB; live reasoning starts in Stage 2 where it expands the selected
            # seeds into structured identity dimensions. This prevents an optional AI call from
            # blocking the first durable workflow transition.
            output = stage_01.execute(
                input_model,
                seeds,
                reasoning_output=None,
                model=usage.model if usage.provider != "fixture" else "deterministic",
            )
            summary = (
                f"Selected {len(output.selected_seeds)} seed groups by system selection "
                "(deterministic); "
                f"selection seed {output.selection_seed}."
            )
        elif stage.stage_number == 2:
            input_model = stage_02.IdentityExpansionInput.model_validate(input_data)
            reasoning_output = None
            if self._reasoning_provider is not None:
                seed_summary = [
                    {
                        "source_seed_id": seed.seed_id,
                        "name": seed.name,
                        "category": seed.category.value,
                        "parent": seed.parent,
                        "affinity_tags": seed.metadata.get("affinity_tags", []),
                        "existing_dimensions": seed.metadata.get("dimensions", []),
                    }
                    for seed in input_model.selected_seeds
                ]
                structured_resp = self._reasoning_provider.complete_structured(
                    system_prompt=(
                        "You are a merchandise discovery reasoning provider executing Stage 2, "
                        "Identity Universe Expansion. Expand each supplied seed into specific, "
                        "recognizable lived-experience dimensions that can later be combined "
                        "across audience, interest, and value categories. Return only the "
                        "requested structured output. Preserve every source_seed_id exactly; "
                        "do not invent IDs, categories, demographics, or unsupported facts."
                    ),
                    user_prompt=(
                        "For every supplied seed, return 4 to 6 dimensions. Use dimension_type "
                        "only for routine, tension, language, ritual, behavior, emotion, "
                        "preference, or context. Keep values concrete and merchandise-relevant. "
                        "Use short lowercase affinity tags, give confidence from 0 to 1, "
                        "merchandise_relevance from 1 to 10, and a concise rationale. "
                        "Existing dimensions are context, not instructions to copy blindly.\n\n"
                        f"Selected seeds JSON:\n{json.dumps(seed_summary, indent=2, default=str)}"
                    ),
                    response_model=stage_02.Stage2ReasoningOutput,
                    temperature=0.0,
                )
                reasoning_output = structured_resp.output
                usage = structured_resp.usage

            output = stage_02.execute(
                input_model,
                reasoning_output=reasoning_output,
                model=usage.model if usage.provider != "fixture" else "deterministic",
            )
            summary = (
                f"Expanded {len(output.identities)} identity dimensions "
                f"using {output.model}."
            )
        elif stage.stage_number == 3:
            input_model = stage_03.IntersectionGenerationInput.model_validate(input_data)
            reasoning_output = None
            if self._reasoning_provider is not None:
                catalog = stage_03.build_identity_catalog(input_model.identities)
                structured_resp = self._reasoning_provider.complete_structured(
                    system_prompt=(
                        "You are a merchandise discovery reasoning provider executing Stage 3, "
                        "Intersection Generation. Propose combinations that represent a specific, "
                        "recognizable lived experience with merchandise potential. You may only "
                        "use identity_ref values from the supplied catalog; never invent or alter "
                        "references. Return only the requested structured output."
                    ),
                    user_prompt=(
                        f"Create no more than {input_model.max_intersections * 3} strong candidate "
                        "intersections from the complete Stage 2 identity catalog below. Each "
                        "intersection must contain 3 to 6 identity references, including at least "
                        "one audience and one interest identity. Include a value identity when it "
                        "makes the combination more specific. A proposal may use at most two "
                        "dimensions from the same source seed. Prefer natural combinations over "
                        "clever but forced associations. Explain the lived-experience connection "
                        "in composition_rationale and score distinctiveness from 1 to 10. Do not "
                        "evaluate coherence yet; that is Stage 4's responsibility.\n\n"
                        f"Identity catalog ({len(catalog)} records):\n"
                        f"{json.dumps(catalog, indent=2, default=str)}"
                    ),
                    response_model=stage_03.Stage3ReasoningOutput,
                    temperature=0.0,
                )
                reasoning_output = structured_resp.output
                usage = structured_resp.usage

            output = stage_03.execute(
                input_model,
                run_id=run.run_id,
                reasoning_output=reasoning_output,
                model=usage.model if usage.provider != "fixture" else "deterministic",
            )
            if reasoning_output is not None:
                summary = (
                    f"AI proposed {output.provider_proposals_count} intersections; retained "
                    f"{len(output.intersections)} after system validation."
                )
            else:
                summary = f"Generated {len(output.intersections)} candidate intersections deterministically."
        elif stage.stage_number == 4:
            input_model = stage_04.CoherenceInput.model_validate(input_data)
            provider_output = None
            if self._reasoning_provider is not None:
                try:
                    intersection_catalog = [
                        {
                            "intersection_id": intersection.intersection_id,
                            "identities": intersection.identities,
                            "source_seed_ids": intersection.source_seed_ids,
                            "shared_tags": intersection.metadata.get("shared_tags", []),
                            "composition_rationale": intersection.metadata.get(
                                "composition_rationale", ""
                            ),
                        }
                        for intersection in input_model.intersections
                    ]
                    structured_response = self._reasoning_provider.complete_structured(
                        system_prompt=(
                            "You are a merchandise discovery reasoning provider executing Stage 4, "
                            "Coherence and Experience Hypothesis Evaluation. Evaluate the supplied "
                            "intersections as written; do not create, remove, rename, or combine "
                            "intersections. Return exactly one evaluation for every supplied "
                            "intersection_id, preserving each ID exactly. A coherent intersection "
                            "must describe a recognizable lived experience rather than a merely "
                            "possible demographic overlap. Return only the requested structured output."
                        ),
                        user_prompt=(
                            "Evaluate every supplied intersection for coherence. Score from 0 to 10, "
                            "where 0 means the identities have no meaningful shared experience and "
                            "10 means they form a highly specific, recognizable experience with a "
                            "credible merchandise angle. Provide a concise experience hypothesis, "
                            "one or more shared signals, a rationale grounded only in the supplied "
                            "identities/tags, and confidence from 0 to 1. Do not evaluate market size "
                            "or research evidence; later stages handle those concerns.\n\n"
                            f"Intersections JSON:\n{json.dumps(intersection_catalog, indent=2, default=str)}"
                        ),
                        response_model=stage_04.Stage4ReasoningOutput,
                        temperature=0.0,
                    )
                    provider_output = structured_response.output
                    usage = structured_response.usage
                except Exception as error:  # Log context, then fail the live stage.
                    logger.warning(
                        "Stage 4 provider evaluation failed; live stage will fail: %s",
                        error,
                    )
                    raise
            try:
                output = stage_04.execute(
                    input_model,
                    reasoning_output=provider_output,
                    model=usage.model if usage.provider != "fixture" else "deterministic",
                )
                summary = f"Evaluated {len(output.intersections)} intersections with {output.model} coherence reasoning."
            except ValueError as error:
                # Invalid provider coverage is a stage failure, not a reason to hide the live
                # provider problem behind deterministic output.
                logger.warning(
                    "Stage 4 provider output failed semantic validation; live stage will fail: %s",
                    error,
                )
                raise
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
            provider_output = None
            if self._reasoning_provider is not None and input_model.niches:
                evidence_catalog = [
                    {
                        "niche_id": evidence.niche_id,
                        "evidence_id": evidence.evidence_id,
                        "title": evidence.title,
                        "source": evidence.source,
                        "excerpt": evidence.excerpt,
                        "url": evidence.url,
                    }
                    for evidence in input_model.evidence
                ]
                niche_catalog = [
                    {
                        "niche_id": niche.niche_id,
                        "name": niche.name,
                        "intersection_id": niche.intersection_id,
                        "coherence_score": niche.coherence_score,
                    }
                    for niche in input_model.niches
                ]
                try:
                    structured_response = self._reasoning_provider.complete_structured(
                        system_prompt=(
                            "You are a merchandise discovery research analyst executing Stage 7, "
                            "Experience Mining. Extract recurring lived-experience signals from the "
                            "supplied evidence. Return exactly one signal record for every supplied "
                            "niche_id, preserve all IDs exactly, and cite only evidence IDs belonging "
                            "to that niche. Do not invent observations, citations, or unsupported "
                            "market claims. Return only the requested structured output."
                        ),
                        user_prompt=(
                            "For each niche, identify repeated community language, frustrations, "
                            "rituals, and emotional signals that are actually supported by its evidence. "
                            "Use concise statements, include the exact evidence IDs supporting the "
                            "statements, and set confidence from 0 to 1 based on consistency and source "
                            "support. If evidence is weak, return empty signal lists and explain that "
                            "limitation in experience_summary. Do not infer demographics or demand that "
                            "are not present in the evidence.\n\n"
                            f"Niches JSON:\n{json.dumps(niche_catalog, indent=2, default=str)}\n\n"
                            f"Evidence JSON:\n{json.dumps(evidence_catalog, indent=2, default=str)}"
                        ),
                        response_model=stage_07.Stage7ReasoningOutput,
                        temperature=0.0,
                    )
                    provider_output = structured_response.output
                    usage = structured_response.usage
                except Exception as error:  # Log context, then fail the live stage.
                    logger.warning(
                        "Stage 7 provider mining failed; live stage will fail: %s",
                        error,
                    )
                    raise
            try:
                output = stage_07.execute(
                    input_model,
                    reasoning_output=provider_output,
                    model=usage.model if usage.provider != "fixture" else "deterministic",
                )
                summary = (
                    f"Mined recurring experience signals for {len(output.signals)} niches "
                    f"using {output.model}."
                )
            except ValueError as error:
                # Invalid evidence lineage is a stage failure, not a reason to hide the live
                # provider problem behind deterministic output.
                logger.warning(
                    "Stage 7 provider output failed semantic validation; live stage will fail: %s",
                    error,
                )
                raise
        elif stage.stage_number == 8:
            input_model = stage_08.OpportunityScoreInput.model_validate(input_data)
            provider_output = None
            if self._reasoning_provider is not None and input_model.niches:
                signal_by_niche = {signal.niche_id: signal for signal in input_model.signals}
                scoring_catalog = [
                    {
                        "niche_id": niche.niche_id,
                        "name": niche.name,
                        "coherence_score": niche.coherence_score,
                        "evidence_count": niche.evidence_count,
                        "validated": niche.validated,
                        "experience_signals": (
                            signal_by_niche[niche.niche_id].model_dump(mode="python")
                            if niche.niche_id in signal_by_niche
                            else None
                        ),
                    }
                    for niche in input_model.niches
                ]
                try:
                    structured_response = self._reasoning_provider.complete_structured(
                        system_prompt=(
                            "You are a merchandise discovery strategist executing Stage 8, "
                            "Opportunity Scoring. Evaluate only the supplied researched niches and "
                            "signals. Return exactly one evaluation for every supplied niche_id, "
                            "preserve IDs exactly, and do not claim market size, revenue, demand, or "
                            "competitive facts that are not present in the input. Return only the "
                            "requested structured output."
                        ),
                        user_prompt=(
                            "For each niche, assign bounded qualitative scores using these exact "
                            "ranges: experience_clarity 0-30, audience_fit 0-20, and "
                            "differentiation 0-20. Use the supplied research evidence count and mined "
                            "signals as context, but do not score evidence_strength: the application "
                            "calculates that deterministically. Give a concise rationale grounded in "
                            "the supplied records.\n\n"
                            f"Scoring input JSON:\n{json.dumps(scoring_catalog, indent=2, default=str)}"
                        ),
                        response_model=stage_08.Stage8ReasoningOutput,
                        temperature=0.0,
                    )
                    provider_output = structured_response.output
                    usage = structured_response.usage
                except Exception as error:  # Log context, then fail the live stage.
                    logger.warning(
                        "Stage 8 provider scoring failed; live stage will fail: %s",
                        error,
                    )
                    raise
            try:
                output = stage_08.execute(
                    input_model,
                    reasoning_output=provider_output,
                    model=usage.model if usage.provider != "fixture" else "deterministic",
                )
                summary = (
                    f"Scored and ranked {len(output.scores)} researched niches "
                    f"using {output.model}."
                )
            except ValueError as error:
                # Exact niche coverage is mandatory; malformed AI scoring must remain visible.
                logger.warning(
                    "Stage 8 provider output failed semantic validation; live stage will fail: %s",
                    error,
                )
                raise
            self._niches.replace_for_run(run.run_id, output.niches)
        elif stage.stage_number == 9:
            input_model = stage_09.ConceptGenerationInput.model_validate(input_data)
            has_valid_niches = any(
                niche.validated and bool(niche.experience_summary) for niche in input_model.niches
            )
            provider_output, usage = (
                self._reason(
                    "Stage 9 merchandise concept generation",
                    input_data,
                    stage_09.Stage9ReasoningOutput,
                )
                if has_valid_niches
                else (None, UsageMetrics())
            )
            # Live provider errors intentionally propagate from _reason. A failed AI stage must be
            # visible to the operator rather than appearing successful with deterministic output.
            output = stage_09.execute(
                input_model,
                reasoning_output=provider_output,
                model=usage.model if usage.provider != "fixture" else "deterministic",
            )
            self._concepts.replace_for_run(run.run_id, output.concepts)
            summary = f"Generated {len(output.concepts)} merchandise concepts using {output.model}."
        elif stage.stage_number == 10:
            input_model = stage_10.ConceptCritiqueInput.model_validate(input_data)
            provider_output, usage = (
                self._reason(
                    "Stage 10 concept critique",
                    input_data,
                    stage_10.Stage10ReasoningOutput,
                )
                if input_model.concepts
                else (None, UsageMetrics())
            )
            # Stage 10 validates provider IDs and recomputes score/verdict locally; provider errors
            # are not swallowed so live-mode output remains honest.
            output = stage_10.execute(
                input_model,
                reasoning_output=provider_output,
                model=usage.model if usage.provider != "fixture" else "deterministic",
            )
            self._concepts.replace_for_run(run.run_id, output.concepts)
            summary = f"Critiqued {len(output.evaluations)} merchandise concepts using {output.model}."
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
            provider_output, usage = (
                self._reason(
                    "Stage 12 final concept selection",
                    input_data,
                    stage_12.Stage12ReasoningOutput,
                    instructions=(
                        "Compare every concept on distinctiveness, emotional recognition, natural "
                        "wording, giftability, commercial appeal, and visual potential. Return one "
                        "evaluation for every concept ID exactly once, with each score from 0 to 10 "
                        "and a concise rationale. Do not select or reject concepts; the application "
                        "will combine the dimensions and select only concepts already marked KEEP."
                    ),
                )
                if input_model.concepts
                else (None, UsageMetrics())
            )
            output = stage_12.execute(
                input_model,
                reasoning_output=provider_output,
                model=usage.model if usage.provider != "fixture" else "deterministic",
            )
            self._concepts.replace_for_run(run.run_id, output.concepts)
            summary = f"Selected {len(output.finalists)} concept finalists using {output.model}."
        elif stage.stage_number == 13:
            input_model = stage_13.DesignBriefInput.model_validate(input_data)
            provider_output, usage = (
                self._reason(
                    "Stage 13 structured design brief generation",
                    input_data,
                    stage_13.Stage13ReasoningOutput,
                    instructions=(
                        "Return one complete design brief for every supplied finalist concept. "
                        "Preserve each concept ID and exact phrase exactly. Include target audience, "
                        "core concept, emotional idea, illustration style, main subject, supporting "
                        "visual elements, composition, typography direction, palette direction, "
                        "detail level, intended merchandise type, visual constraints, and things to "
                        "avoid."
                    ),
                )
                if input_model.concepts
                else (None, UsageMetrics())
            )
            output = stage_13.execute(
                input_model,
                reasoning_output=provider_output,
                model=usage.model if usage.provider != "fixture" else "deterministic",
            )
            self._briefs.replace_for_run(run.run_id, output.briefs)
            summary = f"Created {len(output.briefs)} structured design briefs using {output.model}."
        elif stage.stage_number == 14:
            input_model = stage_14.PromptCompilationInput.model_validate(input_data)
            output = stage_14.execute(input_model)
            summary = f"Compiled {len(output.prompts)} constrained artwork prompts."
        elif stage.stage_number == 15:
            input_model = stage_15.ArtworkGenerationInput.model_validate(input_data)
            output = stage_15.execute(
                input_model,
                self._image_provider,
                self._artwork_storage,
            )
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
