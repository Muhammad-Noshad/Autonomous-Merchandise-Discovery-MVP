"""Reasoning-model adapters for provider-backed structured generation and critique.

Stages depend on this boundary rather than importing the OpenAI SDK. Live provider use is injected
by the application runtime, while fixture or deterministic paths remain available when live mode is
disabled or no live provider is configured. Provider failures are propagated to stage handling.
"""

import os
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
        timeout_seconds: float | None = None,
    ):
        # Composition roots normally pass the validated Settings value. The environment fallback
        # keeps direct adapter construction consistent for scripts and isolated integrations.
        if timeout_seconds is None:
            try:
                timeout_seconds = max(
                    1.0, float(os.getenv("OPENAI_REASONING_TIMEOUT_SECONDS", "420"))
                )
            except ValueError:
                timeout_seconds = 420.0
        # A bounded timeout prevents a failed live provider from holding a background stage open
        # indefinitely. The stage runner records the resulting provider error as a failure.
        self._client = OpenAI(api_key=api_key, timeout=timeout_seconds)
        self._model = model
        self._input_price = input_price_per_million
        self._output_price = output_price_per_million

    def _supports_temperature(self) -> bool:
        """Return whether this model family accepts the legacy sampling parameter.

        The stage contract keeps ``temperature`` so callers do not need to know provider
        quirks. Newer reasoning families (including GPT-5.x and the o-series) control
        generation through reasoning settings and reject ``temperature`` in many modes,
        so the adapter must omit it at the provider boundary.
        """

        model = self._model.casefold()
        return not model.startswith(("gpt-5", "o1", "o3", "o4"))

    def complete_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[BaseModel],
        temperature: float = 0.0,
    ) -> StructuredResponse:
        """Submit one typed request and convert provider usage into the application contract."""

        # Keep model-specific request shaping here. Stages can request deterministic behavior
        # without coupling themselves to the parameter rules of whichever reasoning model is
        # configured for the run.
        request_kwargs: dict[str, object] = {
            "model": self._model,
            "input": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "text_format": response_model,
        }
        if self._supports_temperature():
            request_kwargs["temperature"] = temperature

        try:
            response = self._client.responses.parse(**request_kwargs)
        except (OpenAIError, TypeError, ValueError) as error:
            # Preserve the provider's actionable reason while keeping the application-facing
            # exception stable enough for stage logging and UI rendering.
            detail = str(error).strip() or type(error).__name__
            raise ReasoningProviderError(
                f"Structured reasoning request failed: {detail[:500]}"
            ) from error
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
