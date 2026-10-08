"""Tests for mapping Create Run form values into domain configuration."""

from merchandise_discovery.domain.models.common import (
    IdentityType,
    PipelineVariant,
    identity_type_guidance,
)
from merchandise_discovery.ui.adapters import pipeline_display_name
from merchandise_discovery.ui.pages.run_create import build_run_config


def test_build_run_config_normalizes_form_values() -> None:
    """The page passes a typed, normalized config to the application service."""

    config = build_run_config("MVP seed library", 4, 2, 3, 1, True)

    assert config.seed_source == "mvp_seed_library"
    assert config.max_intersections == 4
    assert config.max_researched_niches == 2
    assert config.concepts_per_niche == 3
    assert config.artwork_variants_per_concept == 1
    assert config.enable_similarity_ip_check is True
    assert config.pipeline_variant is PipelineVariant.SOCIAL_IDENTITY_V2


def test_build_run_config_accepts_behavior_first_identity_variant() -> None:
    config = build_run_config(
        "Social behavior",
        4,
        2,
        3,
        1,
        pipeline_variant=PipelineVariant.SOCIAL_BEHAVIOR_IDENTITY,
        social_identity="bedside nurses",
        social_identity_type=IdentityType.OCCUPATION,
        social_query="documenting difficult patient encounters",
    )

    assert config.pipeline_variant is PipelineVariant.SOCIAL_BEHAVIOR_IDENTITY


def test_build_run_config_persists_manual_social_artwork_review_choice() -> None:
    config = build_run_config(
        "Social behavior",
        4,
        2,
        3,
        1,
        pipeline_variant=PipelineVariant.SOCIAL_IDENTITY_V2,
        social_manual_artwork_selection=True,
    )

    assert config.social_manual_artwork_selection is True
    assert config.social_selected_candidate_indices == []


def test_social_pipeline_labels_explain_their_ordering() -> None:
    assert pipeline_display_name(PipelineVariant.SOCIAL_BEHAVIOR_TEXT) == (
        "Behavior-led — find behavior, then create merchandise"
    )
    assert pipeline_display_name(PipelineVariant.SOCIAL_BEHAVIOR_IDENTITY) == (
        "Behavior → audience — find the behavior, then identify who relates"
    )
    assert pipeline_display_name(PipelineVariant.SOCIAL_IDENTITY_V2) == (
        "Audience → behavior — start with an identity, then find its behavior"
    )


def test_identity_taxonomy_includes_life_stage_relationship_interest_and_place() -> None:
    assert IdentityType.LIFE_STAGE.display_name == "Life stage"
    assert IdentityType.RELATIONSHIP.display_name == "Relationship / family role"
    assert IdentityType.INTEREST.display_name == "Interest / hobby"
    assert IdentityType.PLACE_BASED.display_name == "Place-based identity"
    guidance = identity_type_guidance()
    assert "life_stage: a period or transition" in guidance
    assert "relationship: an identity shaped by a relationship" in guidance
    assert "interest: a sustained hobby or interest" in guidance
    assert "place_based: a shared connection to a place" in guidance


def test_render_run_create_unsubmitted(monkeypatch) -> None:
    """When the form is not submitted, render_run_create exits cleanly."""

    from unittest.mock import Mock

    import streamlit as st

    from merchandise_discovery.ui.pages.run_create import render_run_create

    monkeypatch.setattr(st, "form_submit_button", lambda *args, **kwargs: False)
    runtime = Mock()
    render_run_create(runtime)
    runtime.discovery_service.create_run.assert_not_called()

