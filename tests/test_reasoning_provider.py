"""Tests for the OpenAI adapter's model-specific request boundary.

The provider owns SDK compatibility so domain stages remain unchanged when the configured
reasoning model changes. These tests verify both supported and unsupported request shapes without
making a paid network call.
"""

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from pydantic import BaseModel

from merchandise_discovery.infrastructure.providers.reasoning_provider import (
    OpenAIReasoningProvider,
    ReasoningProviderError,
)


class ExampleOutput(BaseModel):
    value: str


def _provider(model: str) -> OpenAIReasoningProvider:
    """Construct an adapter with a mocked SDK client and no network access."""

    with patch("merchandise_discovery.infrastructure.providers.reasoning_provider.OpenAI") as client:
        provider = OpenAIReasoningProvider(api_key="test-key", model=model)
    provider._client = client.return_value
    provider._client.responses.parse.return_value = SimpleNamespace(
        output_parsed=ExampleOutput(value="ok"),
        usage=SimpleNamespace(input_tokens=2, output_tokens=3, total_tokens=5),
    )
    return provider


def test_reasoning_models_omit_temperature() -> None:
    """GPT-5.6 Luna must not receive a sampling parameter rejected by reasoning models."""

    provider = _provider("gpt-5.6-luna")

    provider.complete_structured(
        system_prompt="system",
        user_prompt="user",
        response_model=ExampleOutput,
        temperature=0.0,
    )

    kwargs = provider._client.responses.parse.call_args.kwargs
    assert "temperature" not in kwargs
    assert kwargs["model"] == "gpt-5.6-luna"


def test_chat_models_keep_temperature() -> None:
    """Existing GPT-4o-mini runs retain their deterministic temperature setting."""

    provider = _provider("gpt-4o-mini")

    provider.complete_structured(
        system_prompt="system",
        user_prompt="user",
        response_model=ExampleOutput,
        temperature=0.0,
    )

    assert provider._client.responses.parse.call_args.kwargs["temperature"] == 0.0


def test_direct_provider_uses_environment_timeout(monkeypatch) -> None:
    """Direct adapter construction follows the same timeout contract as application runtimes."""

    monkeypatch.setenv("OPENAI_REASONING_TIMEOUT_SECONDS", "123")

    with patch("merchandise_discovery.infrastructure.providers.reasoning_provider.OpenAI") as client:
        OpenAIReasoningProvider(api_key="test-key")

    client.assert_called_once_with(api_key="test-key", timeout=123.0)


def test_provider_error_includes_safe_provider_detail() -> None:
    """Stage logs should identify the upstream rejection instead of hiding it completely."""

    provider = _provider("gpt-5.6-luna")
    provider._client.responses.parse.side_effect = ValueError("temperature is unsupported")

    with pytest.raises(ReasoningProviderError, match="temperature is unsupported"):
        provider.complete_structured(
            system_prompt="system",
            user_prompt="user",
            response_model=ExampleOutput,
        )
