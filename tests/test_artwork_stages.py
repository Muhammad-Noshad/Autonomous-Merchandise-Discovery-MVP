"""Tests for design briefs, prompts, artwork generation, and artwork QA."""

from unittest.mock import MagicMock, patch

from merchandise_discovery.domain.models.artifacts import Artwork, MerchandiseConcept
from merchandise_discovery.domain.models.common import ArtworkDecision, ConceptVerdict
from merchandise_discovery.domain.stages.stage_13_design_brief import (
    DesignBriefInput,
    DesignBriefProposal,
    Stage13ReasoningOutput,
)
from merchandise_discovery.domain.stages.stage_13_design_brief import execute as execute_brief
from merchandise_discovery.domain.stages.stage_14_prompt_compilation import PromptCompilationInput
from merchandise_discovery.domain.stages.stage_14_prompt_compilation import (
    execute as execute_prompt,
)
from merchandise_discovery.domain.stages.stage_15_artwork_generation import ArtworkGenerationInput
from merchandise_discovery.domain.stages.stage_15_artwork_generation import (
    execute as execute_generation,
)
from merchandise_discovery.domain.stages.stage_16_artwork_critique import (
    ArtworkCritiqueInput,
    ArtworkCritiqueProposal,
)
from merchandise_discovery.domain.stages.stage_16_artwork_critique import (
    execute as execute_critique,
)
from merchandise_discovery.domain.stages.stage_17_artwork_revision import ArtworkRevisionInput
from merchandise_discovery.domain.stages.stage_17_artwork_revision import (
    execute as execute_revision,
)
from merchandise_discovery.infrastructure.providers.image_provider import (
    FixtureImageProvider,
    ImageEditRequest,
    XAIImageProvider,
)


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
    assert 'Exact text: "Reset Mode" (primary audience-recognition copy)' in prompts.prompts[0].prompt
    assert "Mandatory audience recognition cues" in prompts.prompts[0].prompt
    assert "Render the exact text prominently while preserving its original audience voice" in prompts.prompts[0].prompt
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


def test_luna_review_preserves_edit_instruction_for_flagged_artwork() -> None:
    """The structured critique contract carries a targeted Grok instruction into Stage 17."""

    artwork = Artwork(
        artwork_id="artwork-review",
        run_id="run-test",
        concept_id="concept-1",
        brief_id="brief-1",
        prompt='Exact text: "Reset Mode".',
        combination_name="Night-shift nurses + Coffee rituals",
        source_url="https://example.com/artwork.png",
        width=1024,
        height=1024,
        mime_type="image/png",
        file_size_bytes=10_000,
    )
    result = execute_critique(
        ArtworkCritiqueInput(artworks=[artwork]),
        reasoning_outputs=[
            ArtworkCritiqueProposal(
                artwork_id=artwork.artwork_id,
                audience_relevance_score=4,
                niche_specificity_score=5,
                text_quality_score=8,
                composition_score=7,
                print_suitability_score=8,
                strengths=["Readable type"],
                issues=["The image does not identify the night-shift nurse context."],
                rationale="The phrase is readable, but the visual is generic for the stated audience.",
                outcome="regenerate",
                edit_prompt="Keep the existing typography and add a subtle medication-cart handoff cue.",
            )
        ],
        model="gpt-5.6-luna",
    )

    evaluation = result.evaluations[0]
    assert evaluation.decision == ArtworkDecision.REGENERATE
    assert evaluation.edit_prompt.startswith("Keep the existing")
    assert result.artworks[0].critique["review_model"] == "gpt-5.6-luna"


def test_artwork_revision_edits_only_flagged_candidates() -> None:
    """Grok is called only for flagged candidates and the edited result is marked unverified."""

    artwork = Artwork(
        artwork_id="artwork-edit",
        run_id="run-test",
        concept_id="concept-1",
        brief_id="brief-1",
        prompt='Exact text: "Reset Mode".',
        source_url="https://example.com/artwork.png",
        width=1024,
        height=1024,
        mime_type="image/png",
        file_size_bytes=10_000,
    )
    evaluation = ArtworkCritiqueProposal(
        artwork_id=artwork.artwork_id,
        audience_relevance_score=4,
        niche_specificity_score=5,
        text_quality_score=8,
        composition_score=7,
        print_suitability_score=8,
        visual_quality_score=7,
        rationale="Needs a more specific audience cue.",
        outcome="regenerate",
        edit_prompt="Add a subtle medication-cart handoff cue.",
    )
    critique = execute_critique(
        ArtworkCritiqueInput(artworks=[artwork]),
        reasoning_outputs=[evaluation],
    )

    revised = execute_revision(
        ArtworkRevisionInput(
            artworks=critique.artworks,
            evaluations=critique.evaluations,
        ),
        FixtureImageProvider(),
    )

    assert revised.revisions[0].revised is True
    assert revised.artworks[0].revision_number == 1
    assert revised.artworks[0].revision_prompt == evaluation.edit_prompt
    assert revised.artworks[0].decision is None
    assert revised.artworks[0].critique["revision_status"] == "edited_without_reverification"
    assert revised.revisions[0].original_source_url == artwork.source_url
    assert revised.revisions[0].original_storage_key == artwork.storage_key


def test_rejected_artwork_is_retained_for_final_comparison() -> None:
    """A rejected image remains visible in the final gallery and never incurs an edit call."""

    artwork = Artwork(
        artwork_id="artwork-rejected",
        run_id="run-test",
        concept_id="concept-1",
        brief_id="brief-1",
        prompt='Exact text: "Reset Mode".',
        source_url="https://example.com/rejected.png",
        width=1024,
        height=1024,
        mime_type="image/png",
        file_size_bytes=10_000,
    )
    critique = execute_critique(
        ArtworkCritiqueInput(artworks=[artwork]),
        reasoning_outputs=[
            ArtworkCritiqueProposal(
                artwork_id=artwork.artwork_id,
                audience_relevance_score=2,
                niche_specificity_score=2,
                text_quality_score=5,
                composition_score=4,
                print_suitability_score=4,
                rationale="The image is too generic for the stated niche and should not continue.",
                outcome="rejected",
            )
        ],
    )

    final = execute_revision(
        ArtworkRevisionInput(artworks=critique.artworks, evaluations=critique.evaluations),
        FixtureImageProvider(),
    )

    assert final.artworks[0].decision == ArtworkDecision.REJECT
    assert final.revisions[0].status == "rejected"
    assert final.revisions[0].revised is False


def test_xai_edit_uses_json_endpoint_and_records_provider_cost() -> None:
    """The xAI adapter sends the source URL and converts returned cost ticks to dollars."""

    response = MagicMock()
    response.json.return_value = {
        "data": [{"url": "https://example.com/edited.jpeg", "mime_type": "image/jpeg"}],
        "usage": {"cost_in_usd_ticks": 220_000_000},
    }
    with patch("merchandise_discovery.infrastructure.providers.image_provider.httpx.Client") as client:
        client.return_value.__enter__.return_value.post.return_value = response
        provider = XAIImageProvider("test-key", "grok-imagine-image", 0.02, 0.022)
        result = provider.edit(
            ImageEditRequest(
                artwork_id="artwork-1",
                source_url="https://example.com/original.png",
                prompt="Add a specific night-shift nurse cue.",
            )
        )

    request = client.return_value.__enter__.return_value.post.call_args
    assert request.args[0] == "https://api.x.ai/v1/images/edits"
    assert request.kwargs["json"]["image"]["url"] == "https://example.com/original.png"
    assert result.usage.estimated_cost_usd == 0.022


def test_provider_brief_is_complete_and_exact_phrase_is_application_owned() -> None:
    """Stage 13 materializes a local brief while refusing provider phrase drift."""

    result = execute_brief(
        DesignBriefInput(concepts=[_concept()]),
        reasoning_output=Stage13ReasoningOutput(
            briefs=[
                DesignBriefProposal(
                    concept_id="concept-1",
                    target_audience="People who need a small reset",
                    audience_visual_cues=["quiet decompression ritual", "pause icon held between tasks"],
                    core_concept="A visible reminder to pause before continuing.",
                    exact_phrase="Reset Mode",
                    emotional_idea="Permission to decompress without guilt.",
                    illustration_style="Minimal editorial illustration",
                    main_subject="A softly glowing pause icon",
                    supporting_elements=["small motion marks"],
                    composition="Centered icon above the phrase",
                    typography_direction="Bold readable sans-serif",
                    palette_direction="Deep neutral with restrained violet",
                    detail_level="Moderate",
                    intended_merchandise_type="T-shirt print",
                    visual_constraints=["High contrast"],
                    things_to_avoid=["Busy background"],
                )
            ],
            summary="One complete brief.",
        ),
        model="gpt-4o-mini",
    )

    assert result.briefs[0].brief_id
    assert result.briefs[0].exact_phrase == "Reset Mode"
    assert result.briefs[0].core_concept.startswith("A visible")
    assert result.model == "gpt-4o-mini"


def test_live_artwork_storage_is_not_used_by_fixture_reference() -> None:
    """Fixture runs remain offline even though Stage 15 now has a storage boundary."""

    from merchandise_discovery.infrastructure.storage import LocalArtworkStorage

    stored = LocalArtworkStorage().persist(
        source_url="https://fixture.local/artwork/test/1.png",
        storage_key="fixture-artwork/test/variant-1.png",
        reported_size_bytes=128_000,
    )

    assert stored.storage_key == "fixture-artwork/test/variant-1.png"
    assert stored.file_size_bytes == 128_000
