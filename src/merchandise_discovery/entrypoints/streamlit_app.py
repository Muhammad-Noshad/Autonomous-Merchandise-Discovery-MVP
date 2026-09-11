"""Streamlit dashboard composition and optional persistence initialization.

The dashboard owns presentation and user actions only. Durable workflow state belongs in the
application services and repositories, which keeps reruns and future UI replacements predictable.
MongoDB initialization is limited to the infrastructure startup boundary; the dashboard remains
fixture-backed until the live-run UI is connected in a later chunk.
"""

import logging

import streamlit as st
from pymongo.errors import PyMongoError

from merchandise_discovery.application.runtime import ApplicationRuntime, build_runtime
from merchandise_discovery.shared.configuration import Settings, load_settings
from merchandise_discovery.shared.errors import ConfigurationError
from merchandise_discovery.ui.pages.run_dashboard import render_run_dashboard

logger = logging.getLogger(__name__)


@st.cache_resource(show_spinner=False)
def _initialize_configured_runtime(mongodb_uri: str, mongodb_database: str) -> ApplicationRuntime:
    """Cache one application runtime per database configuration without caching provider secrets."""

    settings = Settings(
        mongodb_uri=mongodb_uri,
        mongodb_database=mongodb_database,
        openai_api_key=None,
        xai_api_key=None,
        xai_image_model="grok-imagine-image",
        max_stage_attempts=3,
    )
    return build_runtime(settings)


def render_database_status() -> ApplicationRuntime | None:
    """Initialize configured MongoDB and show only a safe failure status in the sidebar.

    Missing MongoDB configuration is valid for the visual MVP, so the app stays usable in fixture
    mode. A configured but unavailable database is surfaced explicitly while avoiding credentials
    or the full connection URI in the browser.
    """

    settings = load_settings()
    with st.sidebar:
        if not settings.mongodb_uri:
            st.error("MongoDB not configured — showing fixture data.")
            return None

        try:
            runtime = _initialize_configured_runtime(
                settings.mongodb_uri,
                settings.mongodb_database,
            )
        except (ConfigurationError, PyMongoError) as error:
            # Keep fixture mode available for demos, but leave an operator-visible server log with
            # the exception class. The URI itself is deliberately excluded from the browser.
            logger.warning("MongoDB initialization failed: %s", type(error).__name__)
            st.error("MongoDB unavailable — showing fixture data.")
            return None

        # A successful connection is intentionally silent; the dashboard only needs to interrupt
        # the demo when persistence is unavailable.
        return runtime


def main() -> None:
    """Render the MVP shell after checking the optional persistence configuration."""

    st.set_page_config(
        page_title="Autonomous Merchandise Discovery",
        page_icon="🛍️",
        layout="wide",
    )
    runtime = render_database_status()
    render_run_dashboard(runtime)
