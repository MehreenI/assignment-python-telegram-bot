"""Entry point: start the Telegram study-buddy bot with `python run.py`."""

from __future__ import annotations

import logging
import os
import sys

from dotenv import load_dotenv

from bot.application import build_application, configure_logging
from bot.config import ConfigError, Settings

LOGGER = logging.getLogger("run")


def main() -> int:
    """Start the bot. Returns a process exit code."""
    load_dotenv()
    configure_logging(os.getenv("LOG_LEVEL", "INFO").upper())

    LOGGER.info(
        "Secrets found: TELEGRAM_BOT_TOKEN=%s GROQ_API_KEY=%s",
        bool(os.getenv("TELEGRAM_BOT_TOKEN")),
        bool(os.getenv("GROQ_API_KEY")),
    )

    try:
        settings = Settings.from_env(load_dotenv_file=False)
    except ConfigError as exc:
        LOGGER.error("Configuration problem: %s", exc)
        return 1

    application = build_application(settings)
    LOGGER.info("Bot is running. Press Ctrl+C to stop.")
    application.run_polling()
    return 0


if __name__ == "__main__":
    sys.exit(main())
