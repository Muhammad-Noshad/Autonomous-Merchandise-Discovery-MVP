"""Model-family checks shared by OpenAI provider adapters."""

_REASONING_MODEL_PREFIXES = ("gpt-5", "gpt-6", "o1", "o3", "o4")


def is_reasoning_model(model: str) -> bool:
    """Return whether the configured model uses reasoning-specific request controls."""

    return model.casefold().startswith(_REASONING_MODEL_PREFIXES)
