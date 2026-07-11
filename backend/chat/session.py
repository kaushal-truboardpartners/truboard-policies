"""In-memory conversation history store + in-process rate limiter.

Per CLAUDE.md / FRD:
- Session keyed by user ID (UUID). One session per user, in-process dict.
- History is a list of (role, content) turns in chronological order.
- Rate limit: 30 queries per user per rolling 60-minute window (FRD §13).
  Stored as a deque of UTC timestamps per user; old entries evicted lazily.
- On logout (DELETE /api/chat/session): history + rate log cleared.
"""

from __future__ import annotations

import uuid
from collections import deque
from datetime import UTC, datetime, timedelta
from typing import TypeAlias

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

Turn: TypeAlias = tuple[str, str]  # ("user"|"assistant", content)

# ---------------------------------------------------------------------------
# Globals  (process-wide singletons — acceptable for Phase 1 single-process)
# ---------------------------------------------------------------------------

# user_id → list of (role, content) turns
_HISTORY: dict[uuid.UUID, list[Turn]] = {}

# user_id → deque of UTC timestamps for the rolling rate-limit window
_RATE_LOG: dict[uuid.UUID, deque[datetime]] = {}

_RATE_LIMIT_QUERIES = 30
_RATE_LIMIT_WINDOW = timedelta(hours=1)


# ---------------------------------------------------------------------------
# Session / history
# ---------------------------------------------------------------------------


def get_history(user_id: uuid.UUID) -> list[Turn]:
    """Return a shallow copy of the conversation history for ``user_id``."""
    return list(_HISTORY.get(user_id, []))


def append_turn(user_id: uuid.UUID, role: str, content: str) -> None:
    """Append one turn to the user's conversation history."""
    if user_id not in _HISTORY:
        _HISTORY[user_id] = []
    _HISTORY[user_id].append((role, content))


def clear_session(user_id: uuid.UUID) -> None:
    """Clear history and rate-log for ``user_id`` (called on logout / DELETE /session)."""
    _HISTORY.pop(user_id, None)
    _RATE_LOG.pop(user_id, None)


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------


def _evict_old(log: deque[datetime], now: datetime) -> None:
    """Remove timestamps outside the rolling window (in-place)."""
    cutoff = now - _RATE_LIMIT_WINDOW
    while log and log[0] <= cutoff:
        log.popleft()


def check_rate_limit(user_id: uuid.UUID) -> tuple[bool, int]:
    """Check whether ``user_id`` may make a query now.

    Returns ``(allowed, retry_after_seconds)``.
    ``retry_after_seconds`` is 0 when allowed; the seconds until the oldest
    entry expires when denied (FRD FR-RAG-001 / FR-RAG-002).
    """
    now = datetime.now(UTC)
    log = _RATE_LOG.setdefault(user_id, deque())
    _evict_old(log, now)

    if len(log) < _RATE_LIMIT_QUERIES:
        return True, 0

    # Denied — compute Retry-After from the oldest entry in the window.
    oldest = log[0]
    retry_after = int((oldest + _RATE_LIMIT_WINDOW - now).total_seconds()) + 1
    return False, max(retry_after, 1)


def record_query(user_id: uuid.UUID) -> None:
    """Record that ``user_id`` made a query right now. Call AFTER check_rate_limit."""
    now = datetime.now(UTC)
    log = _RATE_LOG.setdefault(user_id, deque())
    _evict_old(log, now)
    log.append(now)
