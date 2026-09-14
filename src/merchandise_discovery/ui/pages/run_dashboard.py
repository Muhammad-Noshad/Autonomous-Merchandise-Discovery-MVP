"""UI composition root for the MongoDB-backed discovery workspace."""

import logging

import streamlit as st
from pymongo.errors import PyMongoError

from merchandise_discovery.application.runtime import ApplicationRuntime
from merchandise_discovery.shared.errors import RepositoryError
from merchandise_discovery.ui.components.layout import (
    PAGE_ARTWORK_REVIEW,
    PAGE_CONCEPTS,
    PAGE_CREATE_RUN,
    PAGE_NICHES,
    PAGE_RUN_DETAIL,
    PAGE_RUNS,
    render_sidebar,
)
from merchandise_discovery.ui.fixtures import get_demo_run
from merchandise_discovery.ui.pages.artwork_review import render_artwork_review
from merchandise_discovery.ui.pages.concepts import render_concepts
from merchandise_discovery.ui.pages.niches import render_niches
from merchandise_discovery.ui.pages.run_create import render_run_create
from merchandise_discovery.ui.pages.run_detail import render_run_detail_with_polling
from merchandise_discovery.ui.pages.run_list import render_run_list
from merchandise_discovery.ui.theme import apply_theme

logger = logging.getLogger(__name__)


def render_run_dashboard(runtime: ApplicationRuntime | None = None) -> None:
    """Route the shell to live MongoDB pages or an explicit fixture fallback."""

    apply_theme()

    if runtime is None:
        runtime = st.session_state.get("application_runtime")
    live_runs = None
    default_run_id = ""

    if runtime is not None:
        try:
            live_runs = runtime.discovery_service.list_runs()
            if live_runs:
                default_run_id = live_runs[0].run_id
        except (PyMongoError, RepositoryError) as error:
            logger.warning("Could not load live runs (%s).", type(error).__name__)
            live_runs = []

    demo_run = get_demo_run() if runtime is None else None
    selected_page = render_sidebar(
        run=demo_run,
        provider_modes=runtime.provider_modes if runtime else None,
        recent_runs=live_runs,
    )

    if selected_page == PAGE_RUNS:
        if runtime is None:
            render_run_list()
        else:
            render_run_list(live_runs or [])
    elif selected_page == PAGE_CREATE_RUN:
        render_run_create(runtime if runtime else None)
    elif selected_page == PAGE_RUN_DETAIL:
        active_id = st.session_state.get("selected_run_id") or default_run_id
        if not active_id and runtime is None:
            active_id = "017"
        render_run_detail_with_polling(
            active_id,
            runtime.discovery_service if runtime else None,
        )
    elif selected_page == PAGE_NICHES:
        render_niches(runtime.discovery_service if runtime else None)
    elif selected_page == PAGE_CONCEPTS:
        render_concepts(runtime.discovery_service if runtime else None)
    elif selected_page == PAGE_ARTWORK_REVIEW:
        render_artwork_review(
            runtime.discovery_service if runtime else None,
            runtime.review_service if runtime else None,
        )
