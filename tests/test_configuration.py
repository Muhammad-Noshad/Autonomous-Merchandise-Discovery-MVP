"""Tests for model-specific OpenAI reasoning and usage-estimate configuration."""

from pathlib import Path

from merchandise_discovery.shared import configuration


def _isolate_environment(monkeypatch) -> None:
    """Prevent developer-local dotenv values from changing configuration expectations."""

    monkeypatch.setattr(configuration, "ENV_FILE", Path("missing-test-env"))
    monkeypatch.setattr(configuration, "load_dotenv", lambda **_: None)
    for name in (
        "OPENAI_REASONING_MODEL",
        "OPENAI_REASONING_EFFORT",
        "OPENAI_INPUT_PRICE_PER_MILLION",
        "OPENAI_OUTPUT_PRICE_PER_MILLION",
    ):
        monkeypatch.delenv(name, raising=False)


def test_gpt6_luna_defaults_to_medium_effort_and_current_token_rates(monkeypatch) -> None:
    """GPT-6 Luna receives its documented effort default and standard token-price defaults."""

    _isolate_environment(monkeypatch)
    monkeypatch.setenv("OPENAI_REASONING_MODEL", "gpt-6-luna")

    settings = configuration.load_settings()

    assert settings.openai_reasoning_model == "gpt-6-luna"
    assert settings.openai_reasoning_effort == "medium"
    assert settings.openai_input_price_per_million == 0.10
    assert settings.openai_output_price_per_million == 0.50


def test_explicit_openai_price_overrides_take_precedence(monkeypatch) -> None:
    """Deliberate custom pricing remains authoritative over model-based defaults."""

    _isolate_environment(monkeypatch)
    monkeypatch.setenv("OPENAI_REASONING_MODEL", "gpt-6-luna")
    monkeypatch.setenv("OPENAI_INPUT_PRICE_PER_MILLION", "0.12")
    monkeypatch.setenv("OPENAI_OUTPUT_PRICE_PER_MILLION", "0.55")
    monkeypatch.setenv("OPENAI_REASONING_EFFORT", "low")

    settings = configuration.load_settings()

    assert settings.openai_reasoning_effort == "low"
    assert settings.openai_input_price_per_million == 0.12
    assert settings.openai_output_price_per_million == 0.55
