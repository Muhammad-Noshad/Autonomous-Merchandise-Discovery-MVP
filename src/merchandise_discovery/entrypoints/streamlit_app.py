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
def _initialize_configured_runtime(
    mongodb_uri: str,
    mongodb_database: str,
    openai_api_key: str | None = None,
    xai_api_key: str | None = None,
    xai_image_model: str = "grok-imagine-image",
    max_stage_attempts: int = 3,
    openai_reasoning_model: str = "gpt-4o-mini",
    openai_input_price_per_million: float = 0.15,
    openai_output_price_per_million: float = 0.60,
    xai_image_price: float = 0.02,
    provider_mode: str = "fixture",
    stop_after_stage: int = 17,
) -> ApplicationRuntime:
    """Cache one application runtime per configuration."""

    settings = Settings(
        mongodb_uri=mongodb_uri,
        mongodb_database=mongodb_database,
        openai_api_key=openai_api_key,
        xai_api_key=xai_api_key,
        xai_image_model=xai_image_model,
        max_stage_attempts=max_stage_attempts,
        openai_reasoning_model=openai_reasoning_model,
        openai_input_price_per_million=openai_input_price_per_million,
        openai_output_price_per_million=openai_output_price_per_million,
        xai_image_price=xai_image_price,
        provider_mode=provider_mode,
        stop_after_stage=stop_after_stage,
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
                openai_api_key=settings.openai_api_key,
                xai_api_key=settings.xai_api_key,
                xai_image_model=settings.xai_image_model,
                max_stage_attempts=settings.max_stage_attempts,
                openai_reasoning_model=settings.openai_reasoning_model,
                openai_input_price_per_million=settings.openai_input_price_per_million,
                openai_output_price_per_million=settings.openai_output_price_per_million,
                xai_image_price=settings.xai_image_price,
                provider_mode=settings.provider_mode,
                stop_after_stage=settings.stop_after_stage,
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
