"""Shared shell components for navigation, headers, and progress summaries.

Navigation state is intentionally limited to Streamlit session state. It controls which fixture
page is visible, while actual workflow state will continue to belong to application services and
MongoDB repositories.
"""

import streamlit as st

from merchandise_discovery.ui.fixtures import RunFixture

PAGE_RUNS = "Runs"
PAGE_CREATE_RUN = "Create Run"
PAGE_RUN_DETAIL = "Run Detail"
PAGE_NICHES = "Niches"
PAGE_CONCEPTS = "Concepts"
PAGE_ARTWORK_REVIEW = "Artwork Review"
PAGE_OPTIONS = [
    PAGE_RUNS,
    PAGE_CREATE_RUN,
    PAGE_RUN_DETAIL,
    PAGE_NICHES,
    PAGE_CONCEPTS,
    PAGE_ARTWORK_REVIEW,
]


def navigate_to(page: str, run_id: str | None = None) -> None:
    """Queue a route change for the next rerun, avoiding writes to an active widget state."""

    st.session_state["pending_page"] = page
    if run_id is not None:
        st.session_state["pending_run_id"] = run_id
    st.rerun()


def render_sidebar(run: RunFixture) -> str:
    """Render navigation and recent-run context, returning the selected page key."""

    # Button callbacks can happen after the radio widget has been instantiated. Apply queued route
    # changes before creating that widget on the next run so Streamlit accepts the state update.
    pending_page = st.session_state.pop("pending_page", None)
    if pending_page is not None:
        st.session_state["active_page"] = pending_page
    pending_run_id = st.session_state.pop("pending_run_id", None)
    if pending_run_id is not None:
        st.session_state["selected_run_id"] = pending_run_id

    with st.sidebar:
        st.markdown("## Discovery")
        st.caption("Internal merchandise intelligence")
        st.divider()

        # The create action sits above the radio widget so its click can safely update the widget's
        # session-state value before Streamlit instantiates it during the rerun.
        if st.button("+ New run", use_container_width=True):
            navigate_to(PAGE_CREATE_RUN)

        selected_page = st.radio(
            "Workspace",
            PAGE_OPTIONS,
            key="active_page",
            label_visibility="collapsed",
        )

        st.divider()
        st.markdown("**Recent runs**")
        recent_runs = [
            ("#017", "In progress", "12m ago", "#8B5CF6"),
            ("#016", "Completed", "2h ago", "#22C55E"),
            ("#015", "Completed", "1d ago", "#22C55E"),
            ("#014", "Failed", "2d ago", "#EF4444"),
        ]
        for run_id, status, age, color in recent_runs:
            st.markdown(
                f'<div style="display:flex; justify-content:space-between; gap:0.4rem; '
                f'margin:0.55rem 0; font-size:0.78rem;">'
                f'<span><span style="color:{color};">●</span>&nbsp; {run_id}&nbsp; '
                f'<span style="color:{color};">{status}</span></span>'
                f'<span class="opus-muted">{age}</span></div>',
                unsafe_allow_html=True,
            )

        st.divider()
        st.caption("MVP fixture mode")
        return selected_page


def render_run_header(run: RunFixture) -> None:
    """Render the run identity, status, and high-level completion summary."""

    st.markdown(f'<div class="opus-breadcrumb">Runs &nbsp;›&nbsp; #{run.run_id}</div>', unsafe_allow_html=True)
    header_left, header_right = st.columns([0.74, 0.26])
    with header_left:
        st.title(f"Run #{run.run_id}")
        st.caption(
            f"{run.title}  ·  Started {run.started}  ·  Triggered by {run.triggered_by}  ·  {run.version}"
        )
    with header_right:
        st.markdown(
            '<div style="text-align:right; padding-top:0.9rem;">'
            '<span class="opus-status">●&nbsp; In progress</span></div>',
            unsafe_allow_html=True,
        )

    progress_left, progress_right = st.columns([0.76, 0.24])
    with progress_left:
        st.progress(
            run.completion_ratio,
            text=f"{run.completed_stages} / {run.total_stages} stages completed",
        )
    with progress_right:
        st.markdown(
            f'<div style="text-align:right; color:rgba(255,255,255,0.60); padding-top:0.25rem;">'
            f'Est. {run.estimated_remaining} remaining</div>',
            unsafe_allow_html=True,
        )
