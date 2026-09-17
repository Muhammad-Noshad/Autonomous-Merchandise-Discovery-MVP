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
PAGE_OPTIONS = [
    PAGE_RUNS,
    PAGE_CREATE_RUN,
    PAGE_NICHES,
    PAGE_CONCEPTS,
]


def navigate_to(page: str, run_id: str | None = None) -> None:
    """Queue a route change for the next rerun, avoiding writes to an active widget state."""

    st.session_state["pending_page"] = page
    if page != PAGE_RUN_DETAIL:
        # Run Detail is an internal route. Explicit navigation away from it must clear the route
        # so the next full rerun can return to the sidebar-selected workspace page.
        st.session_state.pop("internal_page", None)
    if run_id is not None:
        st.session_state["pending_run_id"] = run_id
    st.rerun()


def render_sidebar(
    run: RunFixture | None = None,
    provider_modes: dict[str, str] | None = None,
    recent_runs: list | None = None,
) -> str:
    """Render navigation and recent-run context, returning the selected page key."""

    # Button callbacks can happen after the radio widget has been instantiated. Apply queued route
    # changes before creating that widget on the next run so Streamlit accepts the state update.
    pending_page = st.session_state.pop("pending_page", None)
    if pending_page == PAGE_RUN_DETAIL:
        # Run Detail is deliberately absent from the sidebar radio. Keep it as a one-rerun
        # internal route so an Open button can navigate there without exposing a direct toggle.
        # Persisting it matters when a terminal live-run transition requests a full app rerun.
        st.session_state["internal_page"] = PAGE_RUN_DETAIL
        st.session_state["active_page"] = PAGE_RUNS
    elif pending_page is not None:
        st.session_state["active_page"] = pending_page
    internal_page = st.session_state.get("internal_page")
    pending_run_id = st.session_state.pop("pending_run_id", None)
    if pending_run_id is not None:
        st.session_state["selected_run_id"] = pending_run_id

    with st.sidebar:
        st.markdown("## Discovery")
        st.caption("Internal merchandise intelligence")
        st.divider()

        # The create action sits above the radio widget so its click can safely update the widget's
        # session-state value before Streamlit instantiates it during the rerun.
        if st.button("+ New run", width="stretch"):
            navigate_to(PAGE_CREATE_RUN)

        selected_page = st.radio(
            "Workspace",
            PAGE_OPTIONS,
            key="active_page",
            label_visibility="collapsed",
        )

        st.divider()
        st.markdown("**Recent runs**")
        if recent_runs is not None:
            if not recent_runs:
                st.caption("No runs yet. Click '+ New run' above.")
            else:
                status_color_map = {
                    "completed": "#22C55E",
                    "running": "#8B5CF6",
                    "paused": "#F59E0B",
                    "failed": "#EF4444",
                    "pending": "rgba(255,255,255,0.50)",
                }
                for item in recent_runs[:5]:
                    r_id = getattr(item, "run_id", str(item))
                    r_status = getattr(item, "status", None)
                    status_str = r_status.value.title() if hasattr(r_status, "value") else str(r_status or "Active")
                    color = status_color_map.get(status_str.lower(), "#8B5CF6")
                    short_id = f"#{r_id[:8]}" if len(r_id) > 8 else f"#{r_id}"

                    st.markdown(
                        f'<span style="font-size:0.8rem;"><span style="color:{color};">●</span> '
                        f'<strong>{short_id}</strong> · {status_str}</span>',
                        unsafe_allow_html=True,
                    )
        else:
            fallback_runs = [
                ("#017", "In progress", "12m ago", "#8B5CF6"),
                ("#016", "Completed", "2h ago", "#22C55E"),
                ("#015", "Completed", "1d ago", "#22C55E"),
                ("#014", "Failed", "2d ago", "#EF4444"),
            ]
            for run_id, status, age, color in fallback_runs:
                st.markdown(
                    f'<div style="display:flex; justify-content:space-between; gap:0.4rem; '
                    f'margin:0.55rem 0; font-size:0.78rem;">'
                    f'<span><span style="color:{color};">●</span>&nbsp; {run_id}&nbsp; '
                    f'<span style="color:{color};">{status}</span></span>'
                    f'<span class="opus-muted">{age}</span></div>',
                    unsafe_allow_html=True,
                )

        st.divider()
        if provider_modes and any(value != "fixture" for value in provider_modes.values()):
            active = " · ".join(
                f"{name}: {provider}"
                for name, provider in provider_modes.items()
                if provider != "fixture"
            )
            st.caption(f"Live providers · {active}")
        else:
            st.caption("MVP fixture providers")
        # Selecting another sidebar page is the explicit way to leave the internal detail route.
        if internal_page == PAGE_RUN_DETAIL and selected_page != PAGE_RUNS:
            st.session_state.pop("internal_page", None)
            return selected_page
        return internal_page or selected_page


def render_run_header(run: RunFixture) -> None:
    """Render the run identity, status, and high-level completion summary."""

    status_color = {
        "completed": "#22C55E",
        "running": "#8B5CF6",
        "paused": "#F59E0B",
        "failed": "#EF4444",
        "pending": "rgba(255,255,255,0.50)",
        "cancelled": "rgba(255,255,255,0.50)",
    }[run.status.value]
    st.markdown(
        f'<div class="opus-breadcrumb">Runs &nbsp;›&nbsp; #{run.run_id}</div>',
        unsafe_allow_html=True,
    )
    header_left, header_right = st.columns([0.74, 0.26])
    with header_left:
        st.title(f"Run #{run.run_id}")
        st.caption(
            f"{run.title}  ·  Started {run.started}  ·  Triggered by {run.triggered_by}  ·  "
            f"Selection seed: {run.selection_seed if run.selection_seed is not None else 'not recorded'}  ·  "
            f"Pipeline: {run.pipeline_variant.replace('_', ' ').title()}  ·  {run.version}"
        )
    with header_right:
        st.markdown(
            '<div style="text-align:right; padding-top:0.9rem;">'
            f'<span class="opus-status" style="border-color:{status_color}; color:{status_color};">'
            f'●&nbsp; {run.status.value.title()}</span></div>',
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
            f'{run.estimated_remaining} remaining</div>',
            unsafe_allow_html=True,
        )
    usage_left, usage_right = st.columns(2)
    with usage_left:
        st.metric("Tokens consumed", f"{run.total_tokens:,}")
    with usage_right:
        suffix = " (est.)" if run.cost_is_estimate else ""
        st.metric("Estimated API cost", f"${run.estimated_cost_usd:.6f}{suffix}")
    if run.last_error:
        st.error(run.last_error)
