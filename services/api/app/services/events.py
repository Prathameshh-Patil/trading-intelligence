"""In-process fan-out for server-sent events.

Route handlers here are sync `def`s (they run in Starlette's threadpool so
the SQLAlchemy session can block), while the SSE generators are async and
live on the event loop. `publish` therefore hands the event to the loop with
`call_soon_threadsafe` rather than touching the queues directly.

One process, one loop -- which is the deployment today. The day there are
two API instances, an approval on one must reach a browser attached to the
other, and this becomes a thin wrapper over Postgres LISTEN/NOTIFY with the
same `publish`/`subscribe` signatures.
"""

from __future__ import annotations

import asyncio
import itertools
import json
import threading
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Event:
    id: int
    type: str
    data: dict[str, Any]

    def sse(self) -> dict[str, str]:
        return {"id": str(self.id), "event": self.type, "data": json.dumps(self.data)}


@dataclass
class Broadcaster:
    _loop: asyncio.AbstractEventLoop | None = None
    _subs: dict[str, set[asyncio.Queue[Event]]] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _ids: itertools.count[int] = field(default_factory=lambda: itertools.count(1))
    # What tests read, and what an operator can dump. Bounded.
    recent: list[Event] = field(default_factory=list)

    def bind(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def publish(self, channel: str, type_: str, data: dict[str, Any]) -> Event:
        event = Event(next(self._ids), type_, data)
        with self._lock:
            self.recent.append(event)
            del self.recent[:-200]
            queues = list(self._subs.get(channel, ()))
        loop = self._loop
        if loop is None or loop.is_closed():
            return event
        for q in queues:
            loop.call_soon_threadsafe(q.put_nowait, event)
        return event

    async def subscribe(self, channel: str) -> AsyncIterator[Event]:
        q: asyncio.Queue[Event] = asyncio.Queue()
        with self._lock:
            self._subs.setdefault(channel, set()).add(q)
        try:
            while True:
                yield await q.get()
        finally:
            with self._lock:
                self._subs.get(channel, set()).discard(q)

    def subscriber_count(self, channel: str) -> int:
        with self._lock:
            return len(self._subs.get(channel, ()))


broadcaster = Broadcaster()

ADMIN_CHANNEL = "admin"
# Every licensed client, no matter whose. What the socket in `routes/ws.py` fans out.
ALERTS_CHANNEL = "alerts"


def user_channel(user_id: int) -> str:
    return f"user:{user_id}"
