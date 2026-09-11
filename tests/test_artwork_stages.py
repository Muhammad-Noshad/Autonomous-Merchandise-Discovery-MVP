"""Tests for design briefs, prompts, artwork generation, and artwork QA."""

from merchandise_discovery.domain.models.artifacts import Artwork, MerchandiseConcept
from merchandise_discovery.domain.models.common import ArtworkDecision, ConceptVerdict
from merchandise_discovery.domain.stages.stage_13_design_brief import DesignBriefInput
from merchandise_discovery.domain.stages.stage_13_design_brief import execute as execute_brief
from merchandise_discovery.domain.stages.stage_14_prompt_compilation import PromptCompilationInput
from merchandise_discovery.domain.stages.stage_14_prompt_compilation import (
    execute as execute_prompt,
)
from merchandise_discovery.domain.stages.stage_15_artwork_generation import ArtworkGenerationInput
from merchandise_discovery.domain.stages.stage_15_artwork_generation import (
    execute as execute_generation,
)
from merchandise_discovery.domain.stages.stage_16_artwork_critique import ArtworkCritiqueInput
from merchandise_discovery.domain.stages.stage_16_artwork_critique import (
    execute as execute_critique,
)
from merchandise_discovery.infrastructure.providers.image_provider import FixtureImageProvider


def _concept(*, selected: bool = True) -> MerchandiseConcept:
    """Return one concept with the state required by Stage 13."""

    return MerchandiseConcept(
        concept_id="concept-1",
        run_id="run-test",
        niche_id="niche-1",
        phrase="Reset Mode",
        description="An experience-led phrase about making room to decompress.",
        overall_score=8.4,
        verdict=ConceptVerdict.KEEP,
        selected=selected,
        rank=1 if selected else None,
    )


def test_design_brief_and_prompt_preserve_exact_phrase_and_constraints() -> None:
    """The visual pipeline keeps the selected concept phrase and brief constraints intact."""

    briefs = execute_brief(DesignBriefInput(concepts=[_concept()]))
    prompts = execute_prompt(PromptCompilationInput(briefs=briefs.briefs))

    assert len(briefs.briefs) == 1
    assert briefs.briefs[0].exact_phrase == "Reset Mode"
    assert 'Exact text: "Reset Mode"' in prompts.prompts[0].prompt
    assert "No logos or existing brand marks" in prompts.prompts[0].prompt


def test_artwork_generation_only_consumes_finalists() -> None:
    """Non-finalists are excluded before the image provider is invoked."""

    briefs = execute_brief(DesignBriefInput(concepts=[_concept(), _concept(selected=False)]))
    prompts = execute_prompt(PromptCompilationInput(briefs=briefs.briefs))
    result = execute_generation(
        ArtworkGenerationInput(prompts=prompts.prompts, artwork_variants_per_concept=2),
        FixtureImageProvider(),
    )

    assert len(briefs.briefs) == 1
    assert len(result.artworks) == 2
    assert all(artwork.mime_type == "image/png" for artwork in result.artworks)
    assert all(artwork.width == artwork.height == 1024 for artwork in result.artworks)


def test_artwork_qa_accepts_valid_fixture_metadata() -> None:
    """The fixture provider produces metadata satisfying the configured MVP checks."""

    briefs = execute_brief(DesignBriefInput(concepts=[_concept()]))
    prompts = execute_prompt(PromptCompilationInput(briefs=briefs.briefs))
    generated = execute_generation(
        ArtworkGenerationInput(prompts=prompts.prompts, artwork_variants_per_concept=1),
        FixtureImageProvider(),
    )
    result = execute_critique(ArtworkCritiqueInput(artworks=generated.artworks))

    assert result.evaluations[0].decision == ArtworkDecision.ACCEPT
    assert result.artworks[0].decision == ArtworkDecision.ACCEPT
    assert result.evaluations[0].issues == []


def test_artwork_qa_requests_regeneration_for_invalid_metadata() -> None:
    """A failed file or prompt check must never be reported as accepted artwork."""

    artwork = Artwork(
        artwork_id="artwork-invalid",
        run_id="run-test",
        concept_id="concept-1",
        brief_id="brief-1",
        prompt="Create an image with text.",
        mime_type="text/plain",
        width=100,
        height=200,
        file_size_bytes=50,
    )

    result = execute_critique(ArtworkCritiqueInput(artworks=[artwork]))

    assert result.evaluations[0].decision == ArtworkDecision.REGENERATE
    assert "supported mime type" in [issue.lower() for issue in result.evaluations[0].issues]
