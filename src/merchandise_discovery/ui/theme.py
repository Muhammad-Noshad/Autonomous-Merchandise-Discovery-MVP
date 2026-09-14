"""Planet Opus-inspired visual tokens for the Streamlit prototype.

The palette is kept in one place so the UI can evolve without scattering color decisions across
components. Semantic colors remain reserved for success, warning, and danger states.
"""

import streamlit as st


def apply_theme() -> None:
    """Inject the dashboard's dark black/violet visual system into Streamlit."""

    st.markdown(
        """
        <style>
        :root {
            --opus-background: #000000;
            --opus-foreground: #FFFFFF;
            --opus-muted: rgba(255, 255, 255, 0.60);
            --opus-primary: #8B5CF6;
            --opus-primary-soft: rgba(139, 92, 246, 0.16);
            --opus-primary-glass: rgba(138, 92, 246, 0.25);
            --opus-glass: rgba(255, 255, 255, 0.04);
            --opus-border: rgba(255, 255, 255, 0.10);
            --opus-success: #22C55E;
            --opus-warning: #F59E0B;
            --opus-danger: #EF4444;
        }

        .stApp {
            background: var(--opus-background);
            color: var(--opus-foreground);
        }

        [data-testid="stSidebar"] {
            background: #050505;
            border-right: 1px solid var(--opus-border);
        }

        [data-testid="stHeader"] {
            background: rgba(0, 0, 0, 0.82);
        }

        [data-testid="stMetric"] {
            background: var(--opus-glass);
            border: 1px solid var(--opus-border);
            border-radius: 10px;
            padding: 12px;
        }

        [data-testid="stExpander"] {
            background: rgba(255, 255, 255, 0.025);
            border: 1px solid var(--opus-border);
            border-radius: 10px;
            margin-bottom: 8px;
        }

        [data-testid="stExpander"] details[open] {
            border-color: var(--opus-primary);
            box-shadow: 0 0 0 1px rgba(139, 92, 246, 0.18);
        }

        /* Keep long stage payloads inside their own card so the pipeline remains scannable. The
           same shared rule also protects nested audit/log expanders from taking over the page. */
        [data-testid="stExpander"] details[open] > div {
            max-height: 34rem;
            overflow-y: auto;
            overscroll-behavior: contain;
            padding-right: 0.35rem;
        }

        [data-testid="stExpander"] details[open] > div::-webkit-scrollbar {
            width: 0.45rem;
        }

        [data-testid="stExpander"] details[open] > div::-webkit-scrollbar-thumb {
            background: rgba(196, 181, 253, 0.35);
            border-radius: 999px;
        }

        .opus-muted { color: var(--opus-muted); }
        .opus-primary { color: var(--opus-primary); }
        .opus-success { color: var(--opus-success); }
        .opus-warning { color: var(--opus-warning); }
        .opus-danger { color: var(--opus-danger); }

        .opus-breadcrumb {
            color: var(--opus-muted);
            font-size: 0.82rem;
            margin-bottom: 0.35rem;
        }

        .opus-status {
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
            padding: 0.25rem 0.6rem;
            border: 1px solid rgba(139, 92, 246, 0.55);
            border-radius: 999px;
            background: var(--opus-primary-soft);
            color: #C4B5FD;
            font-size: 0.78rem;
            font-weight: 600;
        }

        .opus-panel-title {
            font-size: 1.05rem;
            font-weight: 650;
            margin-bottom: 0.25rem;
        }

        .opus-panel-subtitle {
            color: var(--opus-muted);
            font-size: 0.82rem;
            margin-bottom: 0.8rem;
        }

        .opus-evidence {
            border-left: 2px solid var(--opus-primary);
            padding: 0.35rem 0 0.35rem 0.75rem;
            margin: 0.5rem 0;
        }

        .opus-artifact {
            background: var(--opus-glass);
            border: 1px solid var(--opus-border);
            border-radius: 8px;
            padding: 0.5rem 0.7rem;
            margin: 0.4rem 0;
            font-family: monospace;
            font-size: 0.78rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
