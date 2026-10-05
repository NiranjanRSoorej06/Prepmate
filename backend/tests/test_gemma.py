"""Model transport and JSON recovery.

A 4B model returns messy output. These tests pin the messy cases that actually
occur in practice, because a crash here breaks every interview feature.
"""

from __future__ import annotations

import pytest

from ai import gemma
from ai.gemma import (
    InvalidModelOutputError,
    ModelTimeoutError,
    ModelUnavailableError,
    ask_gemma,
    ask_gemma_json,
    extract_json,
)


class TestExtractJson:
    def test_plain_object(self):
        assert extract_json('{"a": 1}') == {"a": 1}

    def test_markdown_fenced(self):
        assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}

    def test_fenced_without_language(self):
        assert extract_json('```\n{"a": 1}\n```') == {"a": 1}

    def test_embedded_in_prose(self):
        raw = 'Here is the JSON you asked for:\n{"question": "Why?"}\nHope that helps!'
        assert extract_json(raw) == {"question": "Why?"}

    def test_leading_and_trailing_whitespace(self):
        assert extract_json('\n\n  {"a": 1}  \n') == {"a": 1}

    def test_python_literals(self):
        assert extract_json("{'a': True, 'b': None}") == {"a": True, "b": None}

    def test_trailing_comma(self):
        assert extract_json('{"a": 1, "b": 2,}') == {"a": 1, "b": 2}

    def test_top_level_array(self):
        assert extract_json("[1, 2]") == [1, 2]

    def test_empty_raises(self):
        with pytest.raises(InvalidModelOutputError):
            extract_json("")

    def test_prose_only_raises(self):
        with pytest.raises(InvalidModelOutputError):
            extract_json("I am not able to produce JSON for this request.")


class TestAskGemma:
    def test_returns_content(self, monkeypatch):
        class Message:
            content = "  hello  "

        class Response:
            message = Message()

        captured = {}

        def fake_chat(**kwargs):
            captured.update(kwargs)
            return Response()

        monkeypatch.setattr(gemma.ollama, "chat", fake_chat)

        assert ask_gemma("system", "user") == "hello"
        assert captured["model"] == gemma.MODEL
        assert captured["messages"][0]["role"] == "system"
        assert captured["messages"][1]["content"] == "user"

    def test_json_mode_sets_format(self, monkeypatch):
        captured = {}

        class Message:
            content = "{}"

        class Response:
            message = Message()

        monkeypatch.setattr(gemma.ollama, "chat", lambda **kw: captured.update(kw) or Response())

        ask_gemma("s", "u", json_mode=True)

        assert captured["format"] == "json"

    def test_long_prompt_is_truncated(self, monkeypatch):
        captured = {}

        class Message:
            content = "ok"

        class Response:
            message = Message()

        monkeypatch.setattr(gemma.ollama, "chat", lambda **kw: captured.update(kw) or Response())

        ask_gemma("s", "x" * (gemma.MAX_CONTEXT_CHARS + 500))

        assert len(captured["messages"][1]["content"]) < len("x" * (gemma.MAX_CONTEXT_CHARS + 500))

    def test_transport_failure_becomes_model_unavailable(self, monkeypatch):
        def boom(**_):
            raise ConnectionError("connection refused")

        monkeypatch.setattr(gemma.ollama, "chat", boom)

        with pytest.raises(ModelUnavailableError):
            ask_gemma("s", "u")

    def test_timeout_is_recognised(self, monkeypatch):
        def slow(**_):
            raise RuntimeError("request timed out after 600s")

        monkeypatch.setattr(gemma.ollama, "chat", slow)

        with pytest.raises(ModelTimeoutError):
            ask_gemma("s", "u")

    def test_empty_response_raises(self, monkeypatch):
        class Message:
            content = "   "

        class Response:
            message = Message()

        monkeypatch.setattr(gemma.ollama, "chat", lambda **kw: Response())

        with pytest.raises(InvalidModelOutputError):
            ask_gemma("s", "u")

    def test_model_unavailable_message_names_the_fix(self):
        error = ModelUnavailableError()

        assert "ollama" in str(error).lower()
        assert gemma.MODEL in str(error)


class TestAskGemmaJson:
    """gemma3:4b intermittently answers a literal `{}` in json_mode."""

    @staticmethod
    def _replies(*contents):
        class Message:
            def __init__(self, content):
                self.content = content

        class Response:
            def __init__(self, content):
                self.message = Message(content)

        calls = []

        def fake_chat(**kwargs):
            calls.append(kwargs["messages"][1]["content"])
            return Response(contents[min(len(calls) - 1, len(contents) - 1)])

        return fake_chat, calls

    def test_empty_object_is_retried_then_recovers(self, monkeypatch):
        # Observed live: the first reply is `{}`, the retry returns real JSON.
        fake_chat, calls = self._replies("{}", '{"technical_accuracy": 7}')

        monkeypatch.setattr(gemma.ollama, "chat", fake_chat)

        assert ask_gemma_json("s", "u") == {"technical_accuracy": 7}
        assert len(calls) == 2

    def test_retry_appends_a_nudge(self, monkeypatch):
        fake_chat, calls = self._replies("{}", "{}")

        monkeypatch.setattr(gemma.ollama, "chat", fake_chat)

        result = ask_gemma_json("s", "original prompt")

        assert result == {}
        assert len(calls) == 2
        assert "empty object" in calls[1]

    def test_a_real_answer_is_not_retried(self, monkeypatch):
        fake_chat, calls = self._replies('{"topic": "Indexes"}')

        monkeypatch.setattr(gemma.ollama, "chat", fake_chat)

        assert ask_gemma_json("s", "u") == {"topic": "Indexes"}
        assert len(calls) == 1

    def test_retries_can_be_disabled(self, monkeypatch):
        fake_chat, calls = self._replies("{}", '{"a": 1}')

        monkeypatch.setattr(gemma.ollama, "chat", fake_chat)

        assert ask_gemma_json("s", "u", attempts=1) == {}
        assert len(calls) == 1
