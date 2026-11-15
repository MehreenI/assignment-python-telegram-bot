"""Tests for the conversation store - the part that must never leak between chats."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bot.history import ConversationStore

SYSTEM_PROMPT = "You are a test buddy."


def make_store(tmp_path: Path, max_messages: int = 4) -> ConversationStore:
    """A store writing to a throwaway file inside the test's temp folder."""
    return ConversationStore(
        tmp_path / "histories.json",
        system_prompt=SYSTEM_PROMPT,
        max_messages=max_messages,
    )


def test_messages_for_starts_with_the_system_prompt(tmp_path: Path) -> None:
    store = make_store(tmp_path)

    messages = store.messages_for(111, "hello")

    assert messages[0] == {"role": "system", "content": SYSTEM_PROMPT}
    assert messages[-1] == {"role": "user", "content": "hello"}


def test_each_chat_has_its_own_history(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store.record_exchange(111, "my name is Ana", "Nice to meet you, Ana!")
    store.record_exchange(222, "my name is Omar", "Nice to meet you, Omar!")

    chat_one = store.messages_for(111, "what is my name?")
    chat_two = store.messages_for(222, "what is my name?")

    assert "Ana" in chat_one[1]["content"]
    assert all("Omar" not in message["content"] for message in chat_one)
    assert "Omar" in chat_two[1]["content"]
    assert all("Ana" not in message["content"] for message in chat_two)


def test_history_is_trimmed_to_the_last_n_messages(tmp_path: Path) -> None:
    store = make_store(tmp_path, max_messages=4)
    for turn in range(5):
        store.record_exchange(111, f"question {turn}", f"answer {turn}")

    stored = store.stored_messages(111)
    sent = store.messages_for(111, "next question")

    assert len(stored) == 4
    assert stored[0]["content"] == "question 3"
    assert len(sent) == 6
    assert sent[0]["role"] == "system"


def test_reset_clears_only_the_target_chat(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store.record_exchange(111, "hi", "hello")
    store.record_exchange(222, "hi", "hello")

    assert store.reset(111) is True
    assert store.stored_messages(111) == []
    assert len(store.stored_messages(222)) == 2
    assert store.reset(111) is False, "resetting an empty chat reports nothing to clear"


def test_history_survives_a_restart_including_non_ascii(tmp_path: Path) -> None:
    urdu = "Assalam o alaikum, mujhe Python seekhna hai کیسے?"
    store = make_store(tmp_path)
    store.record_exchange(111, urdu, "Bilkul! Chaliye shuru karein.")

    reopened = make_store(tmp_path)

    assert reopened.stored_messages(111)[0]["content"] == urdu
    assert urdu in (tmp_path / "histories.json").read_text(encoding="utf-8")


def test_saved_file_is_valid_json_keyed_by_chat_id(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store.record_exchange(111, "hi", "hello")

    data = json.loads((tmp_path / "histories.json").read_text(encoding="utf-8"))

    assert list(data) == ["111"]
    assert data["111"][0]["role"] == "user"
    assert not list(tmp_path.glob("*.tmp")), "the temp file is moved into place, not left behind"


def test_a_corrupted_history_file_does_not_crash_the_bot(tmp_path: Path) -> None:
    (tmp_path / "histories.json").write_text("{ not json", encoding="utf-8")

    store = make_store(tmp_path)

    assert store.chat_count == 0
    store.record_exchange(111, "hi", "hello")
    assert len(store.stored_messages(111)) == 2


def test_max_messages_must_be_positive(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        make_store(tmp_path, max_messages=0)
