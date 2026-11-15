"""Sends a conversation to Groq through the OpenAI SDK and reports usage."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional, Sequence

from openai import OpenAI, OpenAIError

from .config import Settings
from .history import Message

LOGGER = logging.getLogger(__name__)

_TOKENS_PER_MILLION = 1_000_000


class LlmError(RuntimeError):
    """Raised when the model could not be reached or returned nothing usable."""


@dataclass(frozen=True)
class LlmReply:
    """A model reply together with what it cost to produce."""

    text: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float

    @property
    def total_tokens(self) -> int:
        """Tokens in plus tokens out."""
        return self.prompt_tokens + self.completion_tokens


class StudyBuddyLlm:
    """Sends a conversation to the model and reports the reply and token usage."""

    def __init__(self, settings: Settings, client: Optional[OpenAI] = None) -> None:
        self._settings = settings
        self._client = client or OpenAI(
            api_key=settings.groq_api_key,
            base_url=settings.base_url,
            timeout=settings.request_timeout_seconds,
        )

    def complete(self, messages: Sequence[Message]) -> LlmReply:
        """Return the model's answer for these messages, or raise LlmError.

        This call blocks, so handlers run it in a worker thread.
        """
        try:
            response = self._client.chat.completions.create(
                model=self._settings.model,
                messages=list(messages),
            )
        except OpenAIError as exc:
            raise LlmError(f"The model request failed: {exc}") from exc

        text = (response.choices[0].message.content or "").strip() if response.choices else ""
        if not text:
            raise LlmError("The model returned an empty reply.")

        usage = getattr(response, "usage", None)
        prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
        completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)

        return LlmReply(
            text=text,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=self.estimate_cost(prompt_tokens, completion_tokens),
        )

    def estimate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        """Estimate the USD cost of one reply from the per-million prices in .env."""
        settings = self._settings
        return (
            prompt_tokens * settings.input_price_per_million
            + completion_tokens * settings.output_price_per_million
        ) / _TOKENS_PER_MILLION
