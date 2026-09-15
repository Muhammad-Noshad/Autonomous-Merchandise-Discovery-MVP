"""Reasoning-model adapters for provider-backed structured generation and critique.

Stages depend on this boundary rather than importing the OpenAI SDK. Live provider use is injected
by the application runtime, while fixture or deterministic fallbacks remain available when live mode
is disabled or a provider request fails.
"""

from dataclasses import dataclass
from typing import Protocol

from openai import OpenAI, OpenAIError
from pydantic import BaseModel

from merchandise_discovery.domain.models.usage import UsageMetrics


class ReasoningProviderError(RuntimeError):
    """Raised when a structured reasoning response cannot be produced or parsed."""


@dataclass(frozen=True)
class StructuredResponse:
    """Typed model output plus the usage returned by the provider."""

    output: BaseModel
    usage: UsageMetrics


class ReasoningProvider(Protocol):
    """Provider contract for typed reasoning requests."""

    def complete_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[BaseModel],
        temperature: float = 0.0,
    ) -> StructuredResponse:
        """Return a validated Pydantic response and measured usage for one request."""


class OpenAIReasoningProvider:
    """Use OpenAI structured outputs behind the application provider boundary."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        *,
        input_price_per_million: float = 0.15,
        output_price_per_million: float = 0.60,
    ):
        self._client = OpenAI(api_key=api_key)
        self._model = model
        self._input_price = input_price_per_million
        self._output_price = output_price_per_million

    def complete_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[BaseModel],
        temperature: float = 0.0,
    ) -> StructuredResponse:
        """Submit one typed request and convert provider usage into the application contract."""

        try:
            response = self._client.responses.parse(
                model=self._model,
                input=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                text_format=response_model,
                temperature=temperature,
            )
        except (OpenAIError, TypeError, ValueError) as error:
            raise ReasoningProviderError("Structured reasoning request failed.") from error
        if response.output_parsed is None:
            raise ReasoningProviderError("Structured reasoning response was empty or invalid.")
        provider_usage = response.usage
        input_tokens = int(getattr(provider_usage, "input_tokens", 0) or 0)
        output_tokens = int(getattr(provider_usage, "output_tokens", 0) or 0)
        return StructuredResponse(
            output=response.output_parsed,
            usage=UsageMetrics(
                provider="openai",
                model=self._model,
                request_count=1,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=int(
                    getattr(provider_usage, "total_tokens", input_tokens + output_tokens)
                    or input_tokens + output_tokens
                ),
                estimated_cost_usd=round(
                    input_tokens * self._input_price / 1_000_000
                    + output_tokens * self._output_price / 1_000_000,
                    8,
                ),
                cost_is_estimate=True,
                pricing_note="Estimated from configured OpenAI per-million-token rates.",
            ),
        )
