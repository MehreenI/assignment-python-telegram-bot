"""Tests for settings validation and the cost estimate."""

from __future__ import annotations

from pathlib import Path

import pytest

from bot.config import ConfigError, Settings
from bot.llm import StudyBuddyLlm


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Start every test from an environment with no bot variables set."""
    for name in (
        "TELEGRAM_BOT_TOKEN",
        "GROQ_API_KEY",
        "GROQ_MODEL",
        "MAX_HISTORY_MESSAGES",
        "INPUT_PRICE_PER_MILLION_TOKENS",
        "OUTPUT_PRICE_PER_MILLION_TOKENS",
    ):
        monkeypatch.delenv(name, raising=False)


def test_missing_token_is_reported_clearly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "test-key")

    with pytest.raises(ConfigError, match="TELEGRAM_BOT_TOKEN"):
        Settings.from_env(load_dotenv_file=False)


def test_missing_api_key_is_reported_clearly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")

    with pytest.raises(ConfigError, match="GROQ_API_KEY"):
        Settings.from_env(load_dotenv_file=False)


def test_defaults_are_applied(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("GROQ_API_KEY", "test-key")

    settings = Settings.from_env(load_dotenv_file=False)

    assert settings.max_history_messages == 12
    assert settings.history_file == Path("data/telegram_histories.json")
    assert settings.base_url.startswith("https://api.groq.com")


def test_a_bad_number_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setenv("MAX_HISTORY_MESSAGES", "twelve")

    with pytest.raises(ConfigError, match="MAX_HISTORY_MESSAGES"):
        Settings.from_env(load_dotenv_file=False)


def test_cost_estimate_uses_the_prices_from_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setenv("INPUT_PRICE_PER_MILLION_TOKENS", "1.00")
    monkeypatch.setenv("OUTPUT_PRICE_PER_MILLION_TOKENS", "2.00")
    settings = Settings.from_env(load_dotenv_file=False)

    llm = StudyBuddyLlm(settings, client=object())  # type: ignore[arg-type]

    assert llm.estimate_cost(1_000_000, 500_000) == pytest.approx(2.0)
    assert llm.estimate_cost(0, 0) == 0.0
