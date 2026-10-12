"""Small in-process sliding-window limits for a single Render web service."""

from collections import defaultdict, deque
from threading import Lock
from time import monotonic

from fastapi import HTTPException, Request, status

from app.config import (
    INTENT_ACCESS_TOKEN,
    INTENT_RATE_LIMIT_REQUESTS,
    INTENT_RATE_LIMIT_WINDOW_SECONDS,
    IS_PRODUCTION,
    WRITE_RATE_LIMIT_REQUESTS,
    WRITE_RATE_LIMIT_WINDOW_SECONDS,
)


class SlidingWindowLimiter:
    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key: str) -> bool:
        now = monotonic()
        with self._lock:
            events = self._events[key]
            while events and now - events[0] >= self.window_seconds:
                events.popleft()
            if len(events) >= self.max_requests:
                return False
            events.append(now)
            return True


intent_limiter = SlidingWindowLimiter(INTENT_RATE_LIMIT_REQUESTS, INTENT_RATE_LIMIT_WINDOW_SECONDS)
write_limiter = SlidingWindowLimiter(WRITE_RATE_LIMIT_REQUESTS, WRITE_RATE_LIMIT_WINDOW_SECONDS)


def _client_key(request: Request) -> str:
    # Render's proxy headers populate request.client when Uvicorn runs with --proxy-headers.
    return request.client.host if request.client else "unknown"


def _enforce(limiter: SlidingWindowLimiter, request: Request, detail: str) -> None:
    if IS_PRODUCTION and not limiter.allow(_client_key(request)):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=detail)


def require_intent_access(request: Request) -> None:
    """Block anonymous production access before an OpenAI request is attempted."""
    if IS_PRODUCTION:
        import hmac

        supplied = request.headers.get("X-TraceLoom-Intent-Token", "")
        if not INTENT_ACCESS_TOKEN or not hmac.compare_digest(supplied, INTENT_ACCESS_TOKEN):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Intent inference is not available to anonymous demo visitors")
    _enforce(intent_limiter, request, "Intent inference rate limit exceeded. Try again later.")


def limit_demo_writes(request: Request) -> None:
    _enforce(write_limiter, request, "Demo write rate limit exceeded. Try again later.")
