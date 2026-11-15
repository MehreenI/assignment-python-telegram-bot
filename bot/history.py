"""Per-chat conversation history with trimming and atomic JSON persistence."""

from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path
from typing import Dict, List

LOGGER = logging.getLogger(__name__)

Message = Dict[str, str]


class ConversationStore:
    """Conversation history for many chats, keyed by Telegram chat id.

    Only the conversation turns are stored on disk. The system prompt is added
    on the way out, and a turn is recorded only after the model answered, so a
    failed request leaves no dangling user message.
    """

    def __init__(self, path: Path, *, system_prompt: str, max_messages: int) -> None:
        if max_messages <= 0:
            raise ValueError("max_messages must be greater than 0")
        self._path = Path(path)
        self._system_prompt = system_prompt
        self._max_messages = max_messages
        self._lock = threading.Lock()
        self._histories: Dict[str, List[Message]] = self._load()

    @property
    def path(self) -> Path:
        """Where the history JSON file lives."""
        return self._path

    @property
    def chat_count(self) -> int:
        """How many chats currently have stored history."""
        return len(self._histories)

    def stored_messages(self, chat_id: int) -> List[Message]:
        """Return a copy of the turns stored for one chat, without the system prompt."""
        return [dict(message) for message in self._histories.get(_key(chat_id), [])]

    def messages_for(self, chat_id: int, user_text: str) -> List[Message]:
        """Build the message list to send: system prompt, recent turns, new question."""
        recent = self._histories.get(_key(chat_id), [])[-self._max_messages :]
        return [
            {"role": "system", "content": self._system_prompt},
            *(dict(message) for message in recent),
            {"role": "user", "content": user_text},
        ]

    def record_exchange(self, chat_id: int, user_text: str, assistant_text: str) -> None:
        """Append one completed question/answer pair for this chat and persist it."""
        key = _key(chat_id)
        with self._lock:
            history = self._histories.setdefault(key, [])
            history.append({"role": "user", "content": user_text})
            history.append({"role": "assistant", "content": assistant_text})
            del history[: max(0, len(history) - self._max_messages)]
            self._save()

    def reset(self, chat_id: int) -> bool:
        """Forget one chat's history. Returns True if there was anything to forget."""
        key = _key(chat_id)
        with self._lock:
            existed = self._histories.pop(key, None) is not None
            self._save()
        return existed

    def _load(self) -> Dict[str, List[Message]]:
        """Read the history file, tolerating a missing or corrupted file."""
        if not self._path.exists():
            return {}
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            LOGGER.exception("Could not read %s; starting with empty history", self._path)
            return {}
        if not isinstance(raw, dict):
            LOGGER.warning("%s did not contain an object; starting with empty history", self._path)
            return {}
        return {str(key): list(value) for key, value in raw.items() if isinstance(value, list)}

    def _save(self) -> None:
        """Write every chat's history to a temporary file, then move it into place."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self._path.with_name(self._path.name + ".tmp")
        payload = json.dumps(self._histories, ensure_ascii=False, indent=2)
        try:
            temp_path.write_text(payload, encoding="utf-8")
            os.replace(temp_path, self._path)
        except OSError:
            LOGGER.exception("Could not save history to %s", self._path)
            temp_path.unlink(missing_ok=True)


def _key(chat_id: int) -> str:
    """JSON object keys are strings, so chat ids are stored as strings."""
    return str(chat_id)
