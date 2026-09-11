"""Shared shell components for navigation, headers, and progress summaries."""

import streamlit as st

from merchandise_discovery.ui.fixtures import RunFixture


def render_sidebar(run: RunFixture) -> None:
    """Render navigation and recent-run context without owning workflow state."""

    with st.sidebar:
        st.markdown("## ◈ Discovery")
        st.caption("Internal merchandise intelligence")
        st.divider()

        for label in ["Runs", "Niches", "Concepts", "Artwork Review"]:
            is_active = label == "Runs"
            color = "#C4B5FD" if is_active else "rgba(255,255,255,0.60)"
            st.markdown(
                f'<div style="color:{color}; padding:0.48rem 0; font-weight:{650 if is_active else 450};">'
                f'{"◉" if is_active else "○"}&nbsp;&nbsp;{label}</div>',
                unsafe_allow_html=True,
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


def render_run_header(run: RunFixture) -> None:
    """Render the run identity, status, and high-level completion summary."""

    st.markdown('<div class="opus-breadcrumb">Runs &nbsp;›&nbsp; #017</div>', unsafe_allow_html=True)
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

