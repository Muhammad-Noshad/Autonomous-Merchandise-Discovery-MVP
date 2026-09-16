"""Compact Stage 6: research selected niches and generate evidence-backed concepts.

This variant intentionally combines research, experience synthesis, concept generation, visual
briefing, and prompt compilation into one visible stage for A/B testing. The output keeps source
evidence and intermediate signals in the persisted snapshot while producing the prompt consumed by
the shared artwork-generation implementation.
"""

import json

from pydantic import BaseModel, Field

from merchandise_discovery.domain.models.artifacts import (
    DesignBrief,
    IdentityIntersection,
    MerchandiseConcept,
    Niche,
    ResearchEvidence,
)
from merchandise_discovery.domain.models.usage import UsageMetrics, combine_usage
from merchandise_discovery.domain.stages import stage_06_niche_research as research_stage
from merchandise_discovery.domain.stages import stage_07_experience_mining as experience_stage
from merchandise_discovery.domain.stages import stage_09_concept_generation as concept_stage
from merchandise_discovery.domain.stages import stage_13_design_brief as brief_stage
from merchandise_discovery.domain.stages import stage_14_prompt_compilation as prompt_stage
from merchandise_discovery.infrastructure.providers.reasoning_provider import ReasoningProvider
from merchandise_discovery.infrastructure.providers.research_provider import ResearchProvider


class CompactDevelopmentInput(BaseModel):
    """Selected intersections and the two output budgets for the compact path."""

    intersections: list[IdentityIntersection]
    max_researched_niches: int = Field(ge=1, le=100)
    concepts_per_niche: int = Field(ge=1, le=50)


class CompactNicheSynthesis(BaseModel):
    """Evidence-linked experience synthesis returned alongside merchandise concepts."""

    niche_id: str = Field(min_length=1)
    repeated_language: list[str] = Field(default_factory=list, max_length=8)
    frustrations: list[str] = Field(default_factory=list, max_length=8)
    rituals: list[str] = Field(default_factory=list, max_length=8)
    emotional_signals: list[str] = Field(default_factory=list, max_length=8)
    evidence_ids: list[str] = Field(default_factory=list, max_length=20)
    confidence: float = Field(ge=0, le=1)
    experience_summary: str = Field(min_length=1, max_length=500)


class CompactBriefProposal(BaseModel):
    """AI visual direction keyed by the exact generated merchandise phrase."""

    phrase: str = Field(min_length=1, max_length=200)
    target_audience: str = Field(min_length=1, max_length=500)
    audience_visual_cues: list[str] = Field(min_length=2, max_length=8)
    core_concept: str = Field(min_length=1, max_length=800)
    emotional_idea: str = Field(min_length=1, max_length=800)
    illustration_style: str = Field(min_length=1, max_length=500)
    main_subject: str = Field(min_length=1, max_length=500)
    supporting_elements: list[str] = Field(max_length=20)
    composition: str = Field(min_length=1, max_length=800)
    typography_direction: str = Field(min_length=1, max_length=500)
    palette_direction: str = Field(min_length=1, max_length=500)
    detail_level: str = Field(min_length=1, max_length=100)
    intended_merchandise_type: str = Field(min_length=1, max_length=200)
    visual_constraints: list[str] = Field(max_length=30)
    things_to_avoid: list[str] = Field(max_length=30)


class CompactReasoningOutput(BaseModel):
    """Structured response for one compact research-and-merchandise reasoning call."""

    syntheses: list[CompactNicheSynthesis] = Field(min_length=1, max_length=100)
    concepts: list[concept_stage.ConceptProposal] = Field(min_length=1, max_length=500)
    briefs: list[CompactBriefProposal] = Field(min_length=1, max_length=500)
    summary: str = Field(min_length=1, max_length=500)


class CompactDevelopmentOutput(BaseModel):
    """Persisted snapshot containing every useful output from the combined stage."""

    niches: list[Niche]
    evidence: list[ResearchEvidence]
    signals: list[experience_stage.ExperienceSignal]
    concepts: list[MerchandiseConcept]
    briefs: list[DesignBrief]
    prompts: list[prompt_stage.PromptCompilation]
    summary: str = ""
    model: str = "deterministic"
    usage: UsageMetrics = Field(default_factory=UsageMetrics)


def reasoning_instructions() -> str:
    """Return the compact prompt contract focused on evidence-backed specificity."""

    return (
        "You are executing the compact research-first merchandise stage. Use only the supplied "
        "niche evidence and preserve every niche_id and evidence_id exactly. First synthesize "
        "specific recurring language, frustrations, rituals, emotional signals, and a concise "
        "experience summary for every niche. Then generate merchandise concepts grounded in those "
        "specific moments. Each concept must include a recognizable moment, insider behavior or "
        "language, emotional tension, and distinctive visual hook. The merchandise phrase is the "
        "primary audience-recognition copy printed on the product: write it as an insider statement "
        "or shared truth that makes the target audience think, 'That is literally me.' Prefer first "
        "person or direct audience language and include the specific behavior, constraint, or relief "
        "that defines this niche. Do not return a product category, club name, campaign title, broad "
        "theme, or abstract slogan in place of the phrase. For example, use 'I Garden Between Naps' "
        "rather than 'Nap-Window Garden Club' when the evidence is about interrupted gardening by "
        "new parents. Search findings are inspiration for patterns only: do not copy existing phrases, "
        "artwork, brands, or designs. Confidence "
        "is 0 to 1. Specificity score is 0 to 10, and must be at least 7.0 for a concept that should "
        "pass validation. Return at least one approved concept for every supplied niche. For "
        "every concept, return exactly one visual brief keyed by its exact phrase. The brief must "
        "include 2 to 4 concrete audience_visual_cues that make the target audience recognizable "
        "through objects, setting, ritual, clothing, or insider behavior. These cues must be visible "
        "in the artwork, not merely implied by target_audience. Use non-branded cues: for healthcare "
        "shift workers, examples include a generic scrub silhouette, blank badge clip, shift-change "
        "clock, locker hook, or break-room meal. Do not use hospital logos or identifiable institutions. "
        "Also include style, typography, palette, composition, merchandise type, and constraints."
    )


def build_reasoning_prompt(niches: list[Niche], evidence: list[ResearchEvidence]) -> str:
    """Serialize source-backed inputs into isolated per-niche reasoning blocks.

    A flat list makes opaque evidence IDs easy for a model to mix across niches. Grouping each
    niche with its own evidence and explicit allow-list reduces that risk while the application
    validator remains the final authority on lineage.
    """

    evidence_by_niche: dict[str, list[ResearchEvidence]] = {}
    for item in evidence:
        evidence_by_niche.setdefault(item.niche_id, []).append(item)
    niche_blocks = [
        {
            "niche": niche.model_dump(mode="python"),
            "allowed_evidence_ids": [
                item.evidence_id for item in evidence_by_niche.get(niche.niche_id, [])
            ],
            "evidence": [
                item.model_dump(mode="python")
                for item in evidence_by_niche.get(niche.niche_id, [])
            ],
        }
        for niche in niches
    ]
    return (
        "Each Niche block is isolated. For that block's synthesis, evidence_ids must be copied "
        "only from its allowed_evidence_ids list; never cite an ID from another block.\n\n"
        f"Niche blocks JSON:\n{json.dumps(niche_blocks, default=str)}"
    )


def _briefs_for_concepts(
    concepts: list[MerchandiseConcept],
    proposals: list[CompactBriefProposal] | None = None,
) -> list[DesignBrief]:
    """Materialize briefs through the shared brief validator after local concept IDs exist."""

    selected = [concept.model_copy(update={"selected": True}) for concept in concepts]
    if proposals is None:
        return brief_stage.execute(brief_stage.DesignBriefInput(concepts=selected)).briefs

    proposals_by_phrase = {item.phrase: item for item in proposals}
    if len(proposals_by_phrase) != len(proposals):
        raise ValueError("Compact Stage 6 provider output contains duplicate brief phrases.")
    brief_proposals = []
    for concept in selected:
        proposal = proposals_by_phrase.get(concept.phrase)
        if proposal is None:
            raise ValueError(
                f"Compact Stage 6 provider output is missing a brief for phrase: {concept.phrase}."
            )
        brief_proposals.append(
            brief_stage.DesignBriefProposal(
                concept_id=concept.concept_id,
                target_audience=proposal.target_audience,
                audience_visual_cues=proposal.audience_visual_cues,
                core_concept=proposal.core_concept,
                exact_phrase=concept.phrase,
                emotional_idea=proposal.emotional_idea,
                illustration_style=proposal.illustration_style,
                main_subject=proposal.main_subject,
                supporting_elements=proposal.supporting_elements,
                composition=proposal.composition,
                typography_direction=proposal.typography_direction,
                palette_direction=proposal.palette_direction,
                detail_level=proposal.detail_level,
                intended_merchandise_type=proposal.intended_merchandise_type,
                visual_constraints=proposal.visual_constraints,
                things_to_avoid=proposal.things_to_avoid,
            )
        )
    return brief_stage.execute(
        brief_stage.DesignBriefInput(concepts=selected),
        reasoning_output=brief_stage.Stage13ReasoningOutput(
            briefs=brief_proposals,
            summary="Compact AI visual directions validated from exact concept phrases.",
        ),
    ).briefs


def execute(
    input_data: CompactDevelopmentInput,
    *,
    research_provider: ResearchProvider,
    reasoning_provider: ReasoningProvider | None,
    run_id: str,
) -> CompactDevelopmentOutput:
    """Research targets, synthesize evidence, and produce validated concepts in one stage."""

    research_output = research_stage.execute(
        research_stage.NicheResearchInput(
            intersections=input_data.intersections,
            max_researched_niches=input_data.max_researched_niches,
        ),
        research_provider,
        run_id=run_id,
    )
    if not research_output.niches:
        raise ValueError("Compact Stage 6 found no research targets.")

    if reasoning_provider is None:
        mined = experience_stage.execute(
            experience_stage.ExperienceMiningInput(
                niches=research_output.niches,
                evidence=research_output.evidence,
            )
        )
        niches = [
            niche.model_copy(
                update={
                    "experience_summary": next(
                        signal.experience_summary
                        for signal in mined.signals
                        if signal.niche_id == niche.niche_id
                    )
                }
            )
            for niche in research_output.niches
        ]
        concepts = concept_stage.execute(
            concept_stage.ConceptGenerationInput(
                niches=niches,
                experience_signals=mined.signals,
                concepts_per_niche=input_data.concepts_per_niche,
            )
        )
        concept_records = [concept.model_copy(update={"selected": True}) for concept in concepts.concepts]
        briefs = _briefs_for_concepts(concept_records)
        prompts = prompt_stage.execute(prompt_stage.PromptCompilationInput(briefs=briefs))
        return CompactDevelopmentOutput(
            niches=niches,
            evidence=research_output.evidence,
            signals=mined.signals,
            concepts=concept_records,
            briefs=briefs,
            prompts=prompts.prompts,
            summary=f"Researched {len(niches)} niches and generated concepts deterministically.",
            model="deterministic",
            usage=research_output.usage,
        )

    response = reasoning_provider.complete_structured(
        system_prompt=(
            "Return only the requested structured compact-stage output. Do not invent IDs, "
            "citations, demographics, or market claims."
        ),
        user_prompt=(
            f"{reasoning_instructions()}\n\n"
            f"{build_reasoning_prompt(research_output.niches, research_output.evidence)}"
        ),
        response_model=CompactReasoningOutput,
    )
    synthesis_by_id = {item.niche_id: item for item in response.output.syntheses}
    expected_ids = {niche.niche_id for niche in research_output.niches}
    if set(synthesis_by_id) != expected_ids:
        raise ValueError("Compact Stage 6 provider output must contain exactly one synthesis per niche.")
    signals = experience_stage.execute(
        experience_stage.ExperienceMiningInput(
            niches=research_output.niches,
            evidence=research_output.evidence,
        ),
        reasoning_output=experience_stage.Stage7ReasoningOutput(
            signals=[item.model_dump(mode="python") for item in response.output.syntheses],
            summary=response.output.summary,
        ),
        model=response.usage.model,
        validation_label="Compact Stage 6 experience synthesis",
    )
    niches = [
        niche.model_copy(
            update={
                "experience_summary": next(
                    signal.experience_summary
                    for signal in signals.signals
                    if signal.niche_id == niche.niche_id
                )
            }
        )
        for niche in research_output.niches
    ]
    concepts = concept_stage.execute(
        concept_stage.ConceptGenerationInput(
            niches=niches,
            experience_signals=signals.signals,
            concepts_per_niche=input_data.concepts_per_niche,
        ),
        reasoning_output=concept_stage.Stage9ReasoningOutput(
            concepts=response.output.concepts,
            summary=response.output.summary,
        ),
        model=response.usage.model,
    )
    concept_records = [concept.model_copy(update={"selected": True}) for concept in concepts.concepts]
    briefs = _briefs_for_concepts(concept_records, response.output.briefs)
    prompts = prompt_stage.execute(prompt_stage.PromptCompilationInput(briefs=briefs))
    return CompactDevelopmentOutput(
        niches=niches,
        evidence=research_output.evidence,
        signals=signals.signals,
        concepts=concept_records,
        briefs=briefs,
        prompts=prompts.prompts,
        summary=response.output.summary,
        model=response.usage.model,
        usage=combine_usage(research_output.usage, response.usage),
    )
