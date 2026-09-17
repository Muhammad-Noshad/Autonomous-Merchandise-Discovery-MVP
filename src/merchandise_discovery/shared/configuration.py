"""Application configuration loading and environment-variable validation.

Configuration is read at process boundaries so importing domain modules never requires credentials.
This keeps tests deterministic and prevents secrets from leaking into UI code.
"""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from merchandise_discovery.shared.errors import ConfigurationError

ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


@dataclass(frozen=True)
class Settings:
    """Runtime settings shared by the Streamlit process and workflow worker."""

    mongodb_uri: str | None
    mongodb_database: str
    openai_api_key: str | None
    xai_api_key: str | None
    xai_image_model: str
    artwork_storage_dir: str = ".artifacts"
    max_stage_attempts: int = 3
    openai_reasoning_model: str = "gpt-4o-mini"
    openai_reasoning_timeout_seconds: float = 420.0
    openai_input_price_per_million: float = 0.15
    openai_output_price_per_million: float = 0.60
    openai_web_search_price_per_call: float = 0.01
    xai_image_price: float = 0.02
    provider_mode: str = "fixture"
    # The current MVP intentionally evaluates only Stage 1 until the client approves expanding
    # the funnel. This is a demo boundary, not a claim that later stages are complete.
    stop_after_stage: int = 1


def load_settings() -> Settings:
    """Load environment variables without requiring optional provider credentials at import time."""

    if ENV_FILE.is_file():
        load_dotenv(dotenv_path=ENV_FILE, override=False)
    else:
        load_dotenv(override=False)
    return Settings(
        mongodb_uri=os.getenv("MONGODB_URI"),
        mongodb_database=os.getenv("MONGODB_DATABASE", "merchandise_discovery"),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        xai_api_key=os.getenv("XAI_API_KEY"),
        xai_image_model=os.getenv("XAI_IMAGE_MODEL", "grok-imagine-image"),
        artwork_storage_dir=os.getenv("ARTWORK_STORAGE_DIR", ".artifacts"),
        max_stage_attempts=max(1, int(os.getenv("MVP_MAX_STAGE_ATTEMPTS", "3"))),
        openai_reasoning_model=os.getenv("OPENAI_REASONING_MODEL", "gpt-4o-mini"),
        openai_reasoning_timeout_seconds=max(
            1.0, float(os.getenv("OPENAI_REASONING_TIMEOUT_SECONDS", "420"))
        ),
        openai_input_price_per_million=float(os.getenv("OPENAI_INPUT_PRICE_PER_MILLION", "0.15")),
        openai_output_price_per_million=float(os.getenv("OPENAI_OUTPUT_PRICE_PER_MILLION", "0.60")),
        openai_web_search_price_per_call=float(
            os.getenv("OPENAI_WEB_SEARCH_PRICE_PER_CALL", "0.01")
        ),
        xai_image_price=float(os.getenv("XAI_IMAGE_PRICE", "0.02")),
        provider_mode=os.getenv("MVP_PROVIDER_MODE", "fixture").strip().lower(),
        stop_after_stage=max(1, min(17, int(os.getenv("MVP_STOP_AFTER_STAGE", "1")))),
    )


def require_mongodb_uri(settings: Settings) -> str:
    """Return the MongoDB URI or fail with an actionable configuration error."""

    if not settings.mongodb_uri:
        raise ConfigurationError("MONGODB_URI is required for database-backed execution.")
    return settings.mongodb_uri
