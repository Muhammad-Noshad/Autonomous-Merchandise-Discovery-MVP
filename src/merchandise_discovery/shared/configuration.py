"""Application configuration loading and environment-variable validation.

Configuration is read at process boundaries so importing domain modules never requires credentials.
This keeps tests deterministic and prevents secrets from leaking into UI code.
"""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

from merchandise_discovery.shared.errors import ConfigurationError


@dataclass(frozen=True)
class Settings:
    """Runtime settings shared by the Streamlit process and workflow worker."""

    mongodb_uri: str | None
    mongodb_database: str
    openai_api_key: str | None
    xai_api_key: str | None
    xai_image_model: str
    max_stage_attempts: int = 3
    openai_reasoning_model: str = "gpt-4o-mini"
    openai_input_price_per_million: float = 0.15
    openai_output_price_per_million: float = 0.60
    xai_image_price: float = 0.02
    provider_mode: str = "fixture"


def load_settings() -> Settings:
    """Load environment variables without requiring optional provider credentials at import time."""

    load_dotenv()
    return Settings(
        mongodb_uri=os.getenv("MONGODB_URI"),
        mongodb_database=os.getenv("MONGODB_DATABASE", "merchandise_discovery"),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        xai_api_key=os.getenv("XAI_API_KEY"),
        xai_image_model=os.getenv("XAI_IMAGE_MODEL", "grok-imagine-image"),
        max_stage_attempts=max(1, int(os.getenv("MVP_MAX_STAGE_ATTEMPTS", "3"))),
        openai_reasoning_model=os.getenv("OPENAI_REASONING_MODEL", "gpt-4o-mini"),
        openai_input_price_per_million=float(
            os.getenv("OPENAI_INPUT_PRICE_PER_MILLION", "0.15")
        ),
        openai_output_price_per_million=float(
            os.getenv("OPENAI_OUTPUT_PRICE_PER_MILLION", "0.60")
        ),
        xai_image_price=float(os.getenv("XAI_IMAGE_PRICE", "0.02")),
        provider_mode=os.getenv("MVP_PROVIDER_MODE", "fixture").strip().lower(),
    )


def require_mongodb_uri(settings: Settings) -> str:
    """Return the MongoDB URI or fail with an actionable configuration error."""

    if not settings.mongodb_uri:
        raise ConfigurationError("MONGODB_URI is required for database-backed execution.")
    return settings.mongodb_uri
