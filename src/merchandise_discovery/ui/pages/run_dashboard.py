"""UI composition root for the fixture-backed discovery workspace."""

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


def render_run_dashboard(runtime: ApplicationRuntime | None = None) -> None:
    """Route the shell to live MongoDB pages or an explicit fixture fallback."""

    apply_theme()
    run = get_demo_run()
    selected_page = render_sidebar(run)

    if selected_page == PAGE_RUNS:
        if runtime is None:
            render_run_list()
        else:
            try:
                render_run_list(runtime.discovery_service.list_runs())
            except (PyMongoError, RepositoryError):
                st.error("Run history could not be loaded from MongoDB.")
    elif selected_page == PAGE_CREATE_RUN:
        render_run_create(runtime.discovery_service if runtime else None)
    elif selected_page == PAGE_RUN_DETAIL:
        render_run_detail_with_polling(
            st.session_state.get("selected_run_id", run.run_id),
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
