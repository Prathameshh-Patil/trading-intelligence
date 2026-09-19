"""A token bucket per key, in memory.

Good for one process, which is what runs today. If a second instance ever
appears, the buckets diverge and the limit becomes "N per instance" -- move
the counters to Redis at that point, not before.

WHOSE ADDRESS. `X-Forwarded-For` is a request header and anyone can send one.
It is only the client's address when a proxy this service trusts wrote it,
and nothing runs in front of the API today -- so by default the socket peer
is the client, and the header is ignored. `TRUSTED_PROXY=true` says a proxy
is there and its first hop is authoritative. Read the header without that
and every per-IP limit is one header away from a fresh bucket, and
`audit_log.ip` records whatever the attacker typed.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable

from fastapi import HTTPException, Request
from starlette.requests import HTTPConnection

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


def _per_minute(n: int) -> TokenBucket:
    return TokenBucket(capacity=n, refill_per_second=n / 60)


# The shared bucket for signup, login, waitlist and anything else that keys
# on the address. Scopes with their own budget are listed in `BUCKETS`.
auth_bucket = _per_minute(settings.rate_limit_auth_per_minute)

# Refresh is keyed on the session cookie, not the address -- see `limit`.
# A 15-minute access token across a few tabs refreshes often enough that
# sharing the auth budget with signup locked out everyone behind one NAT.
refresh_bucket = _per_minute(settings.rate_limit_refresh_per_minute)

# The desktop validates on launch and six-hourly; an office of them behind
# one address must not read as an attack.
validate_bucket = _per_minute(settings.rate_limit_validate_per_minute)

# Uploads are 8 MB each and any approved account may send them.
upload_bucket = _per_minute(settings.rate_limit_upload_per_minute)

BUCKETS: dict[str, TokenBucket] = {
    "refresh": refresh_bucket,
    "validate": validate_bucket,
    "payments": upload_bucket,
}


def reset_all() -> None:
    auth_bucket.reset()
    for b in BUCKETS.values():
        b.reset()


def client_ip(request: HTTPConnection) -> str:
    """An HTTP request or a WebSocket -- both carry a peer and headers."""
    peer = request.client.host if request.client else "unknown"
    if not settings.trusted_proxy:
        return peer
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip() or peer
    return peer


def limit(
    scope: str,
    extra: Callable[[Request], str] | None = None,
    *,
    key: Callable[[Request], str | None] | None = None,
) -> Callable[[Request], None]:
    """A dependency: `Depends(limit("login"))`.

    Keys on the client address, and on `extra` (an email, say) when given, so
    one address cannot burn everyone's budget and one email cannot be hammered
    from many addresses. `key` replaces the address with something the caller
    already holds -- refresh uses the session cookie -- and falls back to the
    address when it returns None. The bucket is `BUCKETS[scope]` if the scope
    has its own budget, else the shared auth bucket.
    """
    bucket = BUCKETS.get(scope, auth_bucket)

    def dependency(request: Request) -> None:
        subject = (key(request) if key else None) or f"ip:{client_ip(request)}"
        keys = [f"{scope}:{subject}"]
        if extra:
            keys.append(f"{scope}:{extra(request)}")
        for k in keys:
            wait = bucket.take(k)
            if wait > 0:
                raise HTTPException(
                    status_code=429,
                    detail={"error": "too many attempts, slow down"},
                    headers={"Retry-After": str(max(1, int(wait) + 1))},
                )

    return dependency
