"""In-memory session store.

PrepMate's session of record lives in the browser's localStorage — that is the
privacy promise, and it is what survives a refresh. The server keeps a
*transient* copy for one reason only: the report endpoint needs the raw resume
text that was never sent to the browser, so Resume Attack Mode can challenge
claims against the original wording instead of a model-generated summary.

Nothing here is persisted, nothing is shared between users, and everything is
gone when the process restarts.
"""

from __future__ import annotations

import threading
import time
import uuid
from typing import Any

#: Sessions are disposable; two hours is long enough for a real interview and
#: short enough that an abandoned session does not linger.
SESSION_TTL_SECONDS = 2 * 60 * 60

#: Guard against unbounded growth if the app is left running.
MAX_SESSIONS = 50


class Session:
    """One candidate's uploaded resume text and lightweight metadata."""

    __slots__ = ("id", "filename", "resume_text", "profile", "created_at")

    def __init__(
        self,
        session_id: str,
        filename: str,
        resume_text: str,
        profile: dict[str, Any],
    ) -> None:
        self.id = session_id
        self.filename = filename
        self.resume_text = resume_text
        self.profile = profile
        self.created_at = time.time()

    def age(self) -> float:
        return time.time() - self.created_at

    def public_dict(self) -> dict[str, Any]:
        """Deliberately excludes resume text — that stays on the server."""
        return {
            "id": self.id,
            "filename": self.filename,
            "characters": len(self.resume_text),
            "created_at": self.created_at,
        }


class SessionStore:
    """A tiny thread-safe TTL map of sessions."""

    def __init__(self, ttl: float = SESSION_TTL_SECONDS) -> None:
        self._sessions: dict[str, Session] = {}
        self._lock = threading.Lock()
        self._ttl = ttl

    def create(self, filename: str, resume_text: str, profile: dict[str, Any]) -> Session:
        session = Session(uuid.uuid4().hex, filename, resume_text, profile)

        with self._lock:
            self._prune_locked()
            self._sessions[session.id] = session

            if len(self._sessions) > MAX_SESSIONS:
                oldest = min(self._sessions.values(), key=lambda item: item.created_at)
                self._sessions.pop(oldest.id, None)

        return session

    def get(self, session_id: str) -> Session | None:
        if not session_id:
            return None

        with self._lock:
            self._prune_locked()

            return self._sessions.get(session_id)

    def delete(self, session_id: str) -> bool:
        with self._lock:
            return self._sessions.pop(session_id, None) is not None

    def clear(self) -> int:
        with self._lock:
            count = len(self._sessions)
            self._sessions.clear()

            return count

    def _prune_locked(self) -> None:
        expired = [
            session_id
            for session_id, session in self._sessions.items()
            if session.age() > self._ttl
        ]

        for session_id in expired:
            self._sessions.pop(session_id, None)


#: Process-wide store. Single-process dev/demo server by design.
store = SessionStore()
