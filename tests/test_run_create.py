"""Tests for mapping Create Run form values into domain configuration."""

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


def test_render_run_create_unsubmitted(monkeypatch) -> None:
    """When the form is not submitted, render_run_create exits cleanly."""

    from unittest.mock import Mock
    import streamlit as st
    from merchandise_discovery.ui.pages.run_create import render_run_create

    monkeypatch.setattr(st, "form_submit_button", lambda *args, **kwargs: False)
    runtime = Mock()
    render_run_create(runtime)
    runtime.discovery_service.create_run.assert_not_called()

