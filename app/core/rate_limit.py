"""In-memory failed-auth counter. Per-process; fine for Phase 1, swap for Redis later."""
import logging
import time
from collections import defaultdict, deque

from fastapi import HTTPException

logger = logging.getLogger("ccc.auth")

MAX_FAILURES = 5
WINDOW_SECONDS = 600

_failures: dict[str, deque[float]] = defaultdict(deque)


def _prune(key: str, now: float) -> deque[float]:
    q = _failures[key]
    while q and now - q[0] > WINDOW_SECONDS:
        q.popleft()
    return q


def check_allowed(key: str) -> None:
    if len(_prune(key, time.monotonic())) >= MAX_FAILURES:
        logger.warning("auth rate limit hit for %s", key)
        raise HTTPException(status_code=429, detail="Too many failed auth attempts; try again later")


def record_failure(key: str, reason: str) -> None:
    now = time.monotonic()
    q = _prune(key, now)
    q.append(now)
    logger.warning("failed auth attempt from %s (%d in window): %s", key, len(q), reason)


def reset() -> None:
    _failures.clear()
