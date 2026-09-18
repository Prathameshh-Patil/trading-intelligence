"""A token bucket per key, in memory.

Good for one process, which is what runs today. If a second instance ever
appears, the buckets diverge and the limit becomes "N per instance" -- move
the counters to Redis at that point, not before.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable

from fastapi import HTTPException, Request

from app.config import settings


class TokenBucket:
    def __init__(self, capacity: int, refill_per_second: float) -> None:
        self.capacity = capacity
        self.refill = refill_per_second
        self._state: dict[str, tuple[float, float]] = {}
        self._lock = threading.Lock()

    def take(self, key: str, now: float | None = None) -> float:
        """Take one token. Returns 0 on success, else seconds until one exists."""
        now = time.monotonic() if now is None else now
        with self._lock:
            tokens, last = self._state.get(key, (float(self.capacity), now))
            tokens = min(self.capacity, tokens + (now - last) * self.refill)
            if tokens >= 1:
                self._state[key] = (tokens - 1, now)
                return 0.0
            self._state[key] = (tokens, now)
            return (1 - tokens) / self.refill

    def reset(self) -> None:
        with self._lock:
            self._state.clear()


auth_bucket = TokenBucket(
    capacity=settings.rate_limit_auth_per_minute,
    refill_per_second=settings.rate_limit_auth_per_minute / 60,
)


def client_ip(request: Request) -> str:
    # Behind Railway/Fly the socket peer is the proxy; the first hop in
    # X-Forwarded-For is the client. Locally there is no header.
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def limit(
    scope: str, extra: Callable[[Request], str] | None = None
) -> Callable[[Request], None]:
    """A dependency: `Depends(limit("login"))`. Keys on IP, and on `extra`
    (an email, say) when given, so one address cannot burn everyone's budget
    and one email cannot be hammered from many addresses."""

    def dependency(request: Request) -> None:
        keys = [f"{scope}:ip:{client_ip(request)}"]
        if extra:
            keys.append(f"{scope}:{extra(request)}")
        for key in keys:
            wait = auth_bucket.take(key)
            if wait > 0:
                raise HTTPException(
                    status_code=429,
                    detail={"error": "too many attempts, slow down"},
                    headers={"Retry-After": str(max(1, int(wait) + 1))},
                )

    return dependency
