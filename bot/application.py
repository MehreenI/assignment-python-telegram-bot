"""Builds the Telegram application: settings in, ready-to-run bot out."""

from __future__ import annotations

import logging

from telegram.ext import Application, CommandHandler, MessageHandler, filters

from .config import Settings
from .handlers import BotHandlers
from .history import ConversationStore
from .llm import StudyBuddyLlm

LOGGER = logging.getLogger(__name__)


def configure_logging(level: str = "INFO") -> None:
    """Send readable logs to the console and quiet down the HTTP libraries."""
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s %(levelname)-8s %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )
    for noisy in ("httpx", "httpcore", "telegram.ext.Updater", "openai"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def build_application(settings: Settings) -> Application:
    """Create the store, the LLM client and the handlers, and register them."""
    store = ConversationStore(
        settings.history_file,
        system_prompt=settings.system_prompt,
        max_messages=settings.max_history_messages,
    )
    handlers = BotHandlers(llm=StudyBuddyLlm(settings), store=store)

    application = Application.builder().token(settings.telegram_bot_token).build()
    application.add_handler(CommandHandler("start", handlers.start))
    application.add_handler(CommandHandler("reset", handlers.reset))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.on_text))
    application.add_error_handler(handlers.on_error)

    LOGGER.info(
        "Bot configured: model=%s history_file=%s max_history_messages=%d known_chats=%d",
        settings.model,
        store.path,
        settings.max_history_messages,
        store.chat_count,
    )
    return application
