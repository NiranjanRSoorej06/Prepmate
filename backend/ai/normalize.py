"""Output normalisation.

A 4B model returns plausible-looking values in the wrong shape: scores as
"8/10", lists as newline strings, questions wrapped in greetings. Every value
that reaches the frontend goes through these helpers first, so the UI can rely
on the types it is given.
"""

from __future__ import annotations

import re
from typing import Any

MIN_SCORE = 1
MAX_SCORE = 10

_GREETING_PREFIXES = (
    "Okay,",
    "Ok,",
    "Alright,",
    "Great question,",
    "Great,",
    "Sure,",
    "Here's my question:",
    "Here is my question:",
    "Question:",
    "Here's a follow-up:",
    "Here is the follow-up:",
    "Follow-up:",
    "Follow up:",
)


def clamp_score(value: Any, default: int = 5) -> int:
    """Coerce anything into an integer score within 1-10."""
    if isinstance(value, bool):
        return default

    if isinstance(value, str):
        # Handles "8", "8/10", "8 out of 10", "score: 8". Only the first
        # number is the score — "8/10" must not become 810.
        match = re.search(r"\d+(?:\.\d+)?", value)

        if not match:
            return default

        value = match.group()

    try:
        score = float(value)
    except (TypeError, ValueError):
        return default

    if score != score:  # NaN
        return default

    # Accept a 0-1 normalised score from a confused model.
    if 0 < score <= 1:
        score *= MAX_SCORE

    return max(MIN_SCORE, min(MAX_SCORE, int(round(score))))


def as_list(value: Any) -> list[str]:
    """Coerce a model response into a clean list of non-empty strings."""
    if value is None:
        return []

    if isinstance(value, str):
        parts = value.replace(";", "\n").split("\n")
    elif isinstance(value, dict):
        return [f"{key}: {item}" for key, item in value.items() if item]
    elif isinstance(value, (list, tuple, set)):
        parts = [str(item) for item in value]
    else:
        parts = [str(value)]

    items = [part.strip(" -•\t*").strip() for part in parts]

    return [item for item in items if item]


def as_text(value: Any, default: str = "") -> str:
    """Coerce a model response into a single trimmed line of text."""
    if value is None:
        return default

    if isinstance(value, (list, tuple)):
        value = " ".join(str(item) for item in value)

    text = str(value).strip().strip('"').strip()

    return text or default


def strip_chatty_prefix(text: str) -> str:
    """Remove the greetings and labels a small model keeps adding."""
    cleaned = text.strip()

    changed = True

    while changed:
        changed = False

        for prefix in _GREETING_PREFIXES:
            if cleaned.lower().startswith(prefix.lower()):
                cleaned = cleaned[len(prefix) :].strip()
                changed = True

    return cleaned.strip('"').strip()
