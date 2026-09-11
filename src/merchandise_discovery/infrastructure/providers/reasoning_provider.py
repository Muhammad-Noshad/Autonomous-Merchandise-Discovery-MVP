"""Reasoning-model adapter for structured generation and critique.

Stages depend on this boundary rather than importing the OpenAI SDK. The first five stages currently
use deterministic logic, but this adapter is ready for provider-backed hypotheses in a later stage
without changing stage or worker control flow.
"""

from typing import Protocol

from openai import OpenAI, OpenAIError
from pydantic import BaseModel


class ReasoningProviderError(RuntimeError):
    """Raised when a structured reasoning response cannot be produced or parsed."""


class ReasoningProvider(Protocol):
    """Provider contract for typed reasoning requests."""

    def complete_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[BaseModel],
    ) -> BaseModel:
        """Return a validated Pydantic response for one reasoning request."""


class OpenAIReasoningProvider:
    """Use OpenAI structured outputs behind the application provider boundary."""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self._client = OpenAI(api_key=api_key)
        self._model = model

    def complete_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[BaseModel],
    ) -> BaseModel:
        """Submit one typed request and fail with a provider-neutral error when parsing fails."""

        try:
            response = self._client.responses.parse(
                model=self._model,
                input=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                text_format=response_model,
            )
        except (OpenAIError, TypeError, ValueError) as error:
            raise ReasoningProviderError("Structured reasoning request failed.") from error
        if response.output_parsed is None:
            raise ReasoningProviderError("Structured reasoning response was empty or invalid.")
        return response.output_parsed
