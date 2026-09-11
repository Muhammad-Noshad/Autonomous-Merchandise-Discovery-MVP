"""Niche validation page entrypoint."""

from merchandise_discovery.ui.pages.placeholder import render_placeholder_page


def render_niches() -> None:
    """Render the future research and opportunity-validation workspace."""

    render_placeholder_page(
        "Niches",
        "Compare researched opportunities and trace each signal back to public evidence.",
        [
            ("Validated niches", "Research-backed niches will be ranked here."),
            ("Evidence", "Citations, excerpts, and retrieval timestamps will appear here."),
            ("Opportunity scores", "Reproducible score breakdowns will appear here."),
        ],
    )

