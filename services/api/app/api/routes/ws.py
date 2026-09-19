"""The socket: one connection per installed client, authenticated by its licence key.

WHY A WEBSOCKET WHEN THE PORTAL USES SSE. The portal is a signed-in page with
a JWT; `events.py` streams to it over a `fetch` with an `Authorization`
header. An installed client -- the desktop app, the browser extension -- has
no user and no JWT, only a `vh_live_` key, and a browser `WebSocket` cannot
send a header at all. So the key travels in the FIRST FRAME, and the server
answers `hello` or closes. A second reason, specific to the extension: Chrome
keeps a Manifest V3 service worker alive while it holds an open WebSocket,
and does not for a streaming fetch.

THE FRAMES are `packages/contracts/alerts.ts`'s `SocketOut`/`SocketIn` and
nothing else. Anything unrecognised is `error bad_message` and the socket
stays open; anything that fails authentication is an `error` and a close in
the 4000s, and the close code says which.

ORIGIN. CORS does not apply to WebSockets -- the browser sends `Origin` and
the server has to check it itself. `origin_allowed` is the same list the
refresh route uses; a native client sends no `Origin` and is allowed.

REPLAY. None. The broadcaster fans out live; a client that reconnects asks
`GET /alerts?since=` for what it missed, then listens.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Awaitable
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.api import dependencies
from app.core.origins import origin_allowed
from app.core.ratelimit import client_ip, validate_bucket
from app.services import keys
from app.services.events import ALERTS_CHANNEL, Event, broadcaster, user_channel

router = APIRouter(tags=["alerts"])

# Application close codes. `packages/contracts/alerts.ts` `SOCKET_CLOSE`.
KEY_INVALID = 4401
ORIGIN = 4403
AUTH_TIMEOUT = 4408
RATE_LIMITED = 4429

# How long the first frame may take. A module constant so a test can shorten it.
AUTH_TIMEOUT_S = 10.0
# The key is re-checked on this cadence while the socket is open, so a revoke
# that somehow missed the event still lands. Same six hours as the clients'.
RECHECK_S = 6 * 60 * 60

# User-channel events after which this socket's key cannot still be valid.
CLOSES = {
    "key.rotated": "rotated",
    "key.revoked": "revoked",
    "user.rejected": "revoked",
    "user.suspended": "revoked",
}


def _send(ws: WebSocket, frame: dict[str, Any]) -> Awaitable[None]:
    return ws.send_text(json.dumps(frame))


async def _fan_in(*channels: str) -> AsyncIterator[Event]:
    """Merge several broadcaster channels into one async stream of events."""
    q: asyncio.Queue[Event] = asyncio.Queue()

    async def pump(channel: str) -> None:
        async for e in broadcaster.subscribe(channel):
            await q.put(e)

    tasks = [asyncio.create_task(pump(c)) for c in channels]
    try:
        while True:
            yield await q.get()
    finally:
        for t in tasks:
            t.cancel()


def _resolve(plain: str) -> tuple[int, str, str | None] | str:
    """`(user_id, tier, expires_at)` for a good key, else S3's reason.

    A short session, closed before the socket is served -- the `stream_user`
    pattern: a session held for the life of the connection pins a pooled
    connection per subscriber.
    """
    # Looked up at call time: the test suite points `open_session` at its
    # transaction, and a name bound at import would miss that.
    db = dependencies.open_session()
    try:
        row, reason = keys.resolve(db, plain)
        if row is None:
            return reason or "unknown"
        return (
            row.user_id,
            row.tier,
            row.expires_at.isoformat() if row.expires_at else None,
        )
    finally:
        db.close()


@router.websocket("/ws")
async def socket(ws: WebSocket) -> None:
    if not origin_allowed(ws.headers.get("origin")):
        await ws.close(code=ORIGIN)
        return
    await ws.accept()

    # --- the first frame is the key -------------------------------------
    try:
        raw = await asyncio.wait_for(ws.receive_text(), timeout=AUTH_TIMEOUT_S)
    except TimeoutError:
        await _send(ws, {"type": "error", "reason": "unauthenticated"})
        await ws.close(code=AUTH_TIMEOUT)
        return
    except WebSocketDisconnect:
        return

    frame = _parse(raw)
    if frame is None or frame.get("type") != "auth" or not isinstance(frame.get("key"), str):
        await _send(ws, {"type": "error", "reason": "unauthenticated"})
        await ws.close(code=KEY_INVALID)
        return

    # The same per-address budget as `/keys/validate`: a socket that accepts
    # one auth attempt per frame is otherwise a faster oracle than the route.
    if validate_bucket.take(f"validate:ip:{client_ip(ws)}") > 0:
        await _send(ws, {"type": "error", "reason": "rate_limited"})
        await ws.close(code=RATE_LIMITED)
        return

    key: str = frame["key"]
    resolved = await asyncio.to_thread(_resolve, key)
    if isinstance(resolved, str):
        await _send(ws, {"type": "error", "reason": "invalid_key"})
        await ws.close(code=KEY_INVALID)
        return
    user_id, tier, expires_at = resolved
    await _send(
        ws,
        {
            "type": "hello",
            "tier": tier,
            "expires_at": expires_at,
            "server_time": datetime.now(UTC).isoformat(),
        },
    )

    # --- then two things at once: the client's pings, and the fan-out ------
    async def inbound() -> None:
        while True:
            frame = _parse(await ws.receive_text())
            if frame is None or frame.get("type") != "ping":
                await _send(ws, {"type": "error", "reason": "bad_message"})
                continue
            await _send(ws, {"type": "pong"})

    async def outbound() -> None:
        async for e in _fan_in(ALERTS_CHANNEL, user_channel(user_id)):
            if e.type == "alert":
                await _send(ws, {"type": "alert", "alert": e.data})
            elif e.type in CLOSES:
                # The key this socket was opened with is no longer good -- a
                # rotate, a revoke, or the account behind it losing approval.
                await _send(ws, {"type": "key", "event": CLOSES[e.type]})
                await ws.close(code=KEY_INVALID)
                return

    async def recheck() -> None:
        while True:
            await asyncio.sleep(RECHECK_S)
            if isinstance(await asyncio.to_thread(_resolve, key), str):
                await _send(ws, {"type": "key", "event": "revoked"})
                await ws.close(code=KEY_INVALID)
                return

    tasks = [
        asyncio.create_task(inbound()),
        asyncio.create_task(outbound()),
        asyncio.create_task(recheck()),
    ]
    try:
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for t in done:
            exc = t.exception()
            if exc is not None and not isinstance(exc, WebSocketDisconnect | RuntimeError):
                raise exc
    finally:
        for t in tasks:
            t.cancel()


def _parse(raw: str) -> dict[str, Any] | None:
    try:
        v = json.loads(raw)
    except ValueError:
        return None
    return v if isinstance(v, dict) else None
