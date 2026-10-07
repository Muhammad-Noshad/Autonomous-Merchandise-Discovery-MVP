"""Tests for mapping Create Run form values into domain configuration."""

from merchandise_discovery.domain.models.common import IdentityType, PipelineVariant
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


def test_render_run_create_unsubmitted(monkeypatch) -> None:
    """When the form is not submitted, render_run_create exits cleanly."""

    from unittest.mock import Mock

    import streamlit as st

    from merchandise_discovery.ui.pages.run_create import render_run_create

    monkeypatch.setattr(st, "form_submit_button", lambda *args, **kwargs: False)
    runtime = Mock()
    render_run_create(runtime)
    runtime.discovery_service.create_run.assert_not_called()

