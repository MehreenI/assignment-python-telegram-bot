"""Settings read from environment variables (or a .env file) and validated at startup."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

DEFAULT_SYSTEM_PROMPT = (
    "You are a friendly study buddy for software students. "
    "Keep answers short, concrete and encouraging. "
    "If you are unsure about something, say so instead of guessing."
)
DEFAULT_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_MODEL = "openai/gpt-oss-20b"


class ConfigError(RuntimeError):
    """Raised when a required setting is missing or cannot be parsed."""


@dataclass(frozen=True)
class Settings:
    """Immutable, validated configuration for one run of the bot."""

    telegram_bot_token: str
    groq_api_key: str
    base_url: str
    model: str
    system_prompt: str
    history_file: Path
    max_history_messages: int
    input_price_per_million: float
    output_price_per_million: float
    request_timeout_seconds: float
    log_level: str

    @classmethod
    def from_env(cls, *, load_dotenv_file: bool = True) -> "Settings":
        """Build settings from the environment, raising ConfigError if invalid."""
        if load_dotenv_file:
            load_dotenv()

        return cls(
            telegram_bot_token=_required("TELEGRAM_BOT_TOKEN"),
            groq_api_key=_required("GROQ_API_KEY"),
            base_url=os.getenv("GROQ_BASE_URL", DEFAULT_BASE_URL),
            model=os.getenv("GROQ_MODEL", DEFAULT_MODEL),
            system_prompt=os.getenv("SYSTEM_PROMPT", DEFAULT_SYSTEM_PROMPT),
            history_file=Path(os.getenv("HISTORY_FILE", "data/telegram_histories.json")),
            max_history_messages=_positive_int("MAX_HISTORY_MESSAGES", 12),
            input_price_per_million=_non_negative_float("INPUT_PRICE_PER_MILLION_TOKENS", 0.075),
            output_price_per_million=_non_negative_float("OUTPUT_PRICE_PER_MILLION_TOKENS", 0.30),
            request_timeout_seconds=_non_negative_float("REQUEST_TIMEOUT_SECONDS", 60.0),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        )


def _required(name: str) -> str:
    """Return a non-empty environment variable, or say which one is missing."""
    value = (os.getenv(name) or "").strip()
    if not value:
        raise ConfigError(
            f"{name} is missing. Copy .env.example to .env and fill it in "
            "(the file is gitignored, so your keys stay private)."
        )
    return value


def _positive_int(name: str, default: int) -> int:
    """Read an integer greater than 0, falling back to default when unset."""
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be a whole number, got {raw!r}.") from exc
    if value <= 0:
        raise ConfigError(f"{name} must be greater than 0, got {value}.")
    return value


def _non_negative_float(name: str, default: float) -> float:
    """Read a float of 0 or more, falling back to default when unset."""
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be a number, got {raw!r}.") from exc
    if value < 0:
        raise ConfigError(f"{name} cannot be negative, got {value}.")
    return value
