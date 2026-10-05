"""Thin, defensive wrapper around a locally running Ollama model.

Everything in PrepMate flows through this module: resume profiling, question
generation, answer evaluation, resume-attack questions, claim credibility and
the final report.

Two rules drive the design here:

1. Small models produce messy output. Never trust the raw string.
2. The model runs on the user's own machine, so "model not available" is an
   expected, recoverable situation — not a crash.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

import ollama

MODEL = os.getenv("PREPMATE_MODEL", "gemma3:4b")

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")

#: Generation timeout in seconds. A 4B model on CPU can be slow, but a
#: multi-minute hang is a failure, not slowness.
DEFAULT_TIMEOUT = float(os.getenv("PREPMATE_TIMEOUT", "600"))

#: Upper bound on tokens we ever request. Interview questions are short and
#: an unbounded response is the most common cause of a "frozen" UI.
MAX_TOKENS = 900

#: Guard against a runaway prompt (a huge resume pasted into every request).
MAX_CONTEXT_CHARS = 12000


class PrepMateError(Exception):
    """Base class for every error PrepMate raises on purpose."""


class ModelUnavailableError(PrepMateError):
    """Ollama is not running, or the configured model is not pulled."""

    def __init__(self, detail: str | None = None) -> None:
        super().__init__(
            detail
            or (
                "PrepMate cannot reach the local Gemma model. "
                "Make sure Ollama is running and the model is installed "
                f"(ollama pull {MODEL})."
            )
        )


class ModelTimeoutError(PrepMateError):
    """Gemma took too long to answer."""

    def __init__(self, seconds: float) -> None:
        super().__init__(
            f"Gemma took longer than {int(seconds)}s to respond. "
            "The local model may be under heavy load. Try again."
        )
        self.seconds = seconds


class InvalidModelOutputError(PrepMateError):
    """Gemma replied, but not with the JSON we asked for."""

    def __init__(self, raw: str) -> None:
        super().__init__(
            "PrepMate could not understand Gemma's response. "
            "This usually happens when the model is too small or overloaded. "
            "Try again."
        )
        self.raw = raw


def is_available() -> bool:
    """Return True when Ollama answers and the configured model is present."""
    try:
        models = ollama.list()
    except Exception:
        return False

    names = set()

    for entry in models.get("models", []) or []:
        name = (entry or {}).get("name") or (entry or {}).get("model")
        if name:
            names.add(name)

    if MODEL in names:
        return True

    # `gemma3:4b` is stored locally as `gemma3:4b` but users often type
    # `gemma3` — accept a tag-less match so the app is forgiving.
    base = MODEL.split(":")[0]

    return any(name == base or name.startswith(f"{base}:") for name in names)


def health() -> dict[str, Any]:
    """Describe the local runtime for the frontend's privacy/status banner."""
    reachable = is_available()

    return {
        "model": MODEL,
        "runtime": "ollama",
        "host": OLLAMA_HOST,
        "available": reachable,
        "local_only": True,
    }


def _truncate(text: str, limit: int = MAX_CONTEXT_CHARS) -> str:
    if len(text) <= limit:
        return text

    return text[:limit] + "\n\n[...truncated...]"


def ask_gemma(
    system_prompt: str,
    user_prompt: str,
    *,
    temperature: float = 0.4,
    json_mode: bool = False,
    max_tokens: int = MAX_TOKENS,
    schema: dict[str, Any] | None = None,
    timeout: float | None = None,
) -> str:
    """Send one prompt to the local model and return its raw text output.

    Pass `schema` to have Ollama constrain decoding to that JSON schema.
    Constrained decoding is far more reliable than plain json mode with a
    small model: gemma3:4b routinely answers a literal `{}` when only asked
    for "some JSON", but honours an explicit schema every time.
    """
    limit = timeout or DEFAULT_TIMEOUT

    messages = [
        {"role": "system", "content": system_prompt.strip()},
        {"role": "user", "content": _truncate(user_prompt.strip())},
    ]

    options: dict[str, Any] = {
        "temperature": temperature,
        "num_predict": max_tokens,
    }

    try:
        response = ollama.chat(
            model=MODEL,
            messages=messages,
            format=schema if schema else ("json" if json_mode else None),
            options=options,
        )
    except Exception as error:  # noqa: BLE001 - normalise every transport failure
        message = str(error)

        if "timed out" in message.lower() or "timeout" in message.lower():
            raise ModelTimeoutError(limit) from error

        raise ModelUnavailableError() from error

    content = (getattr(response.message, "content", "") or "").strip()

    if not content:
        raise InvalidModelOutputError("")

    return content


# --------------------------------------------------------------------------
# JSON helpers
# --------------------------------------------------------------------------

_FENCE = re.compile(r"```(?:json|JSON)?\s*(.*?)```", re.DOTALL)


def extract_json(raw: str) -> dict[str, Any] | list[Any]:
    """Parse JSON out of a small model's reply, tolerating common noise.

    Handles: markdown code fences, a bare object embedded in prose,
    single-quoted keys, and trailing commas.
    """
    text = (raw or "").strip()

    if not text:
        raise InvalidModelOutputError(raw)

    fenced = _FENCE.search(text)

    if fenced:
        text = fenced.group(1).strip()

    candidates = [text]

    # Model sometimes prefixes "Here is the JSON:" — take the first { or [.
    for opener, closer in (("{", "}"), ("[", "]")):
        start = text.find(opener)

        if start != -1:
            end = text.rfind(closer)

            if end > start:
                candidates.append(text[start : end + 1])

    for candidate in candidates:
        parsed = _try_parse(candidate)

        if parsed is not None:
            return parsed

    raise InvalidModelOutputError(raw)


def _try_parse(candidate: str) -> dict[str, Any] | list[Any] | None:
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass

    repaired = (
        candidate.replace("'", '"')
        .replace("True", "true")
        .replace("False", "false")
        .replace("None", "null")
    )
    repaired = re.sub(r",\s*([}\]])", r"\1", repaired)

    try:
        return json.loads(repaired)
    except json.JSONDecodeError:
        return None


EMPTY_JSON_NUDGE = (
    "\n\nIMPORTANT: your previous reply was an empty object. "
    "Answer with the complete JSON object now, filling in every key. "
    "Do not return {}."
)


def ask_gemma_json(
    system_prompt: str,
    user_prompt: str,
    *,
    temperature: float = 0.2,
    timeout: float | None = None,
    schema: dict[str, Any] | None = None,
    attempts: int = 2,
) -> dict[str, Any]:
    """Ask Gemma for JSON and return a dict, whatever noise came with it.

    Pass `schema` to constrain decoding; that is what keeps a small model from
    collapsing to `{}`. The retry below is the second line of defence for the
    cases where even a constrained reply comes back empty.
    """
    user = user_prompt
    last: dict[str, Any] = {}

    for _attempt in range(max(1, attempts)):
        raw = ask_gemma(
            system_prompt,
            user,
            temperature=temperature,
            json_mode=True,
            schema=schema,
            timeout=timeout,
        )

        parsed = extract_json(raw)

        if isinstance(parsed, list):
            # A list where an object was requested: wrap single-element lists,
            # otherwise there is no sensible mapping to the expected shape.
            parsed = {"items": parsed}

        if not isinstance(parsed, dict):  # pragma: no cover - defensive
            raise InvalidModelOutputError(raw)

        if parsed:
            return parsed

        last = parsed
        user = user_prompt + EMPTY_JSON_NUDGE

    return last
