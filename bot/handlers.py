"""Telegram handlers for /start, /reset and plain text messages."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from typing import AsyncIterator

from telegram import Bot, Update
from telegram.constants import ChatAction
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from .history import ConversationStore
from .llm import LlmError, StudyBuddyLlm

LOGGER = logging.getLogger(__name__)

WELCOME_TEXT = (
    "Hi! I'm your study buddy \N{GRADUATION CAP}\n\n"
    "Ask me anything about programming and I'll keep the answers short.\n"
    "I remember our conversation, so you can ask follow-up questions.\n\n"
    "Commands:\n"
    "/start - show this message\n"
    "/reset - forget our conversation and start fresh"
)
RESET_TEXT = "Done, I've forgotten our conversation. Ask me something new!"
RESET_NOTHING_TEXT = "There was nothing to forget yet. Ask me something!"
FAILURE_TEXT = (
    "Sorry, I couldn't reach my brain just now \N{DISAPPOINTED FACE}\n"
    "Please try again in a moment."
)

MAX_TELEGRAM_MESSAGE_LENGTH = 4096
TYPING_REFRESH_SECONDS = 4.0


class BotHandlers:
    """Holds the shared store and LLM client used by every handler."""

    def __init__(self, llm: StudyBuddyLlm, store: ConversationStore) -> None:
        self._llm = llm
        self._store = store

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Greet the user and list the available commands."""
        if update.message is None:
            return
        LOGGER.info("/start from chat %s", update.effective_chat.id)
        await update.message.reply_text(WELCOME_TEXT)

    async def reset(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Clear this chat's history only, and confirm it to the user."""
        if update.message is None:
            return
        chat_id = update.effective_chat.id
        existed = self._store.reset(chat_id)
        LOGGER.info("/reset for chat %s (had history: %s)", chat_id, existed)
        await update.message.reply_text(RESET_TEXT if existed else RESET_NOTHING_TEXT)

    async def on_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Answer a plain text message with the LLM, using this chat's own history."""
        if update.message is None or not update.message.text:
            return

        chat_id = update.effective_chat.id
        user_text = update.message.text
        messages = self._store.messages_for(chat_id, user_text)

        try:
            async with typing_indicator(context.bot, chat_id):
                reply = await asyncio.to_thread(self._llm.complete, messages)
        except LlmError:
            LOGGER.exception("LLM call failed for chat %s", chat_id)
            await update.message.reply_text(FAILURE_TEXT)
            return

        self._store.record_exchange(chat_id, user_text, reply.text)
        LOGGER.info(
            "chat=%s tokens_in=%d tokens_out=%d total=%d est_cost_usd=%.6f",
            chat_id,
            reply.prompt_tokens,
            reply.completion_tokens,
            reply.total_tokens,
            reply.cost_usd,
        )
        await update.message.reply_text(reply.text[:MAX_TELEGRAM_MESSAGE_LENGTH])

    async def on_error(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Log anything a handler did not catch."""
        LOGGER.error("Unhandled error while processing an update", exc_info=context.error)


@asynccontextmanager
async def typing_indicator(bot: Bot, chat_id: int) -> AsyncIterator[None]:
    """Show Telegram's typing indicator for as long as the block runs.

    The action expires after about five seconds, so it is re-sent while waiting.
    """

    async def keep_typing() -> None:
        while True:
            try:
                await bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
            except TelegramError:
                LOGGER.debug("Could not send typing action to chat %s", chat_id, exc_info=True)
                return
            await asyncio.sleep(TYPING_REFRESH_SECONDS)

    task = asyncio.create_task(keep_typing())
    try:
        yield
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
