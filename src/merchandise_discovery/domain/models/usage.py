"""Provider-neutral usage and cost contracts persisted beside each stage result."""

from pydantic import BaseModel, Field


class UsageMetrics(BaseModel):
    """Measured or estimated consumption for one stage execution.

    Text providers expose token counts, while image providers generally expose a per-image price
    instead. ``cost_is_estimate`` makes that distinction visible instead of implying billing data
    came directly from a provider.
    """

    provider: str = "fixture"
    model: str = "fixture"
    request_count: int = Field(default=0, ge=0)
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)
    image_count: int = Field(default=0, ge=0)
    estimated_cost_usd: float = Field(default=0.0, ge=0)
    cost_is_estimate: bool = False
    pricing_note: str | None = None


def combine_usage(*metrics: UsageMetrics) -> UsageMetrics:
    """Aggregate several provider calls made by one stage while preserving pricing transparency."""

    if not metrics:
        return UsageMetrics()
    first = metrics[0]
    return UsageMetrics(
        provider=first.provider,
        model=first.model,
        request_count=sum(item.request_count for item in metrics),
        input_tokens=sum(item.input_tokens for item in metrics),
        output_tokens=sum(item.output_tokens for item in metrics),
        total_tokens=sum(item.total_tokens for item in metrics),
        image_count=sum(item.image_count for item in metrics),
        estimated_cost_usd=round(sum(item.estimated_cost_usd for item in metrics), 8),
        cost_is_estimate=any(item.cost_is_estimate for item in metrics),
        pricing_note=first.pricing_note,
    )
