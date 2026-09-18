"""Server-sent events: one stream per signed-in user, one for admins.

A plain FastAPI GET that keeps the response open. The browser clients read it
with `fetch` + a stream reader (not `EventSource`, which cannot send the
`Authorization` header). Every event is also derivable by re-fetching the
REST resource it names -- the stream is a nudge, not a source of truth, so a
client that misses one loses nothing but a moment.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

from app.api.dependencies import StreamAdmin, StreamUser
from app.services.events import ADMIN_CHANNEL, broadcaster, user_channel

router = APIRouter(tags=["events"])

HEADERS = {"Cache-Control": "no-store", "X-Accel-Buffering": "no"}


async def _stream(request: Request, channel: str) -> AsyncIterator[dict[str, str]]:
    yield {"event": "hello", "data": "{}"}
    async for event in broadcaster.subscribe(channel):
        if await request.is_disconnected():
            break
        yield event.sse()


@router.get("/events")
async def my_events(request: Request, user: StreamUser) -> EventSourceResponse:
    return EventSourceResponse(
        _stream(request, user_channel(user.id)), headers=HEADERS, ping=15
    )


@router.get("/admin/events")
async def admin_events(request: Request, admin: StreamAdmin) -> EventSourceResponse:
    return EventSourceResponse(
        _stream(request, ADMIN_CHANNEL), headers=HEADERS, ping=15
    )
