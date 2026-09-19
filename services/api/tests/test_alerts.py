"""Alerts and the socket that delivers them to a licensed client."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

import app.api.routes.ws as ws_module
from app.core.ratelimit import validate_bucket
from app.models import AuditLog

ORIGIN = {"Origin": "chrome-extension://" + "a" * 32}


def approve(client, admin, user) -> str:
    r = client.post(f"/api/v1/admin/users/{user.id}/approve", headers=admin)
    assert r.status_code == 200, r.text
    return r.json()["key"]["key"]


def publish(client, admin, tier="signal", **extra):
    body = {"tier": tier, "title": f"a {tier}", "body": "the body", **extra}
    r = client.post("/api/v1/admin/alerts", json=body, headers=admin)
    assert r.status_code == 201, r.text
    return r.json()


# --- the routes ---------------------------------------------------------


def test_publish_stores_audits_and_is_readable_by_key(client, admin, pending_user, db):
    key = approve(client, admin, pending_user)
    out = publish(client, admin, "breaking", symbol="XAUUSD")
    assert out["tier"] == "breaking" and out["symbol"] == "XAUUSD"

    row = db.scalar(select(AuditLog).where(AuditLog.action == "alert.publish"))
    assert row is not None and row.target_id == str(out["id"])

    r = client.get("/api/v1/alerts?since=0", headers={"X-API-Key": key})
    assert r.status_code == 200
    assert [a["id"] for a in r.json()] == [out["id"]]


def test_catch_up_is_newer_than_since_and_unexpired_oldest_first(client, admin, pending_user):
    key = approve(client, admin, pending_user)
    first = publish(client, admin, "analysis")
    second = publish(client, admin, "signal")
    gone = publish(
        client, admin, "breaking",
        expires_at=(datetime.now(UTC) - timedelta(minutes=1)).isoformat(),
    )
    live = publish(
        client, admin, "breaking",
        expires_at=(datetime.now(UTC) + timedelta(hours=1)).isoformat(),
    )
    ids = [a["id"] for a in client.get(
        f"/api/v1/alerts?since={first['id']}", headers={"X-API-Key": key}).json()]
    assert ids == [second["id"], live["id"]]
    assert gone["id"] not in ids


def test_catch_up_refuses_a_bad_key_with_s3s_reason(client, admin, pending_user):
    key = approve(client, admin, pending_user)
    r = client.get("/api/v1/alerts", headers={"X-API-Key": "vh_live_" + "x" * 32})
    assert r.status_code == 401 and r.json()["detail"]["error"] == "unknown"
    client.post(f"/api/v1/admin/users/{pending_user.id}/suspend", headers=admin)
    r = client.get("/api/v1/alerts", headers={"X-API-Key": key})
    assert r.status_code == 401 and r.json()["detail"]["error"] == "revoked"
    assert client.get("/api/v1/alerts").status_code == 422


def test_publish_validates_the_tier_and_admin_history_pages(client, admin):
    r = client.post(
        "/api/v1/admin/alerts",
        json={"tier": "rumour", "title": "t", "body": "b"},
        headers=admin,
    )
    assert r.status_code == 422
    for tier in ("breaking", "signal", "analysis"):
        publish(client, admin, tier)
    page = client.get("/api/v1/admin/alerts?limit=2", headers=admin).json()
    assert [a["tier"] for a in page] == ["analysis", "signal"]


def test_only_an_admin_publishes(client, pending_user, login):
    r = client.post(
        "/api/v1/admin/alerts",
        json={"tier": "signal", "title": "t", "body": "b"},
        headers={"Authorization": f"Bearer {login(pending_user.email)}"},
    )
    assert r.status_code == 403


# --- the socket ---------------------------------------------------------


def recv(ws) -> dict:
    return json.loads(ws.receive_text())


def test_socket_says_hello_to_a_good_key_and_pushes_alerts(client, admin, pending_user):
    key = approve(client, admin, pending_user)
    with client.websocket_connect("/api/v1/ws", headers=ORIGIN) as ws:
        ws.send_text(json.dumps({"type": "auth", "key": key}))
        hello = recv(ws)
        assert hello["type"] == "hello" and hello["tier"] == "core"

        ws.send_text(json.dumps({"type": "ping"}))
        assert recv(ws) == {"type": "pong"}

        ws.send_text(json.dumps({"type": "shout"}))
        assert recv(ws) == {"type": "error", "reason": "bad_message"}

        for tier in ("breaking", "signal", "analysis"):
            out = publish(client, admin, tier)
            frame = recv(ws)
            assert frame["type"] == "alert"
            assert frame["alert"]["id"] == out["id"] and frame["alert"]["tier"] == tier


def test_socket_refuses_an_unknown_key(client):
    with client.websocket_connect("/api/v1/ws", headers=ORIGIN) as ws:
        ws.send_text(json.dumps({"type": "auth", "key": "vh_live_" + "x" * 32}))
        assert recv(ws) == {"type": "error", "reason": "invalid_key"}
        with pytest.raises(Exception) as closed:
            ws.receive_text()
        assert _close_code(closed.value) == ws_module.KEY_INVALID


def test_socket_refuses_a_first_frame_that_is_not_auth(client):
    with client.websocket_connect("/api/v1/ws", headers=ORIGIN) as ws:
        ws.send_text(json.dumps({"type": "ping"}))
        assert recv(ws) == {"type": "error", "reason": "unauthenticated"}
        with pytest.raises(Exception) as closed:
            ws.receive_text()
        assert _close_code(closed.value) == ws_module.KEY_INVALID


def test_socket_times_out_a_silent_client(client, monkeypatch):
    monkeypatch.setattr(ws_module, "AUTH_TIMEOUT_S", 0.05)
    with client.websocket_connect("/api/v1/ws", headers=ORIGIN) as ws:
        assert recv(ws) == {"type": "error", "reason": "unauthenticated"}
        with pytest.raises(Exception) as closed:
            ws.receive_text()
        assert _close_code(closed.value) == ws_module.AUTH_TIMEOUT


def test_socket_refuses_a_foreign_origin_before_accepting(client):
    with (
        pytest.raises(Exception) as closed,
        client.websocket_connect("/api/v1/ws", headers={"Origin": "https://evil.example"}),
    ):
        pass
    assert _close_code(closed.value) == ws_module.ORIGIN


def test_socket_closes_when_the_key_is_revoked(client, admin, pending_user, db):
    key = approve(client, admin, pending_user)
    with client.websocket_connect("/api/v1/ws", headers=ORIGIN) as ws:
        ws.send_text(json.dumps({"type": "auth", "key": key}))
        assert recv(ws)["type"] == "hello"
        client.post(f"/api/v1/admin/users/{pending_user.id}/keys/rotate", headers=admin)
        assert recv(ws) == {"type": "key", "event": "rotated"}
        with pytest.raises(Exception) as closed:
            ws.receive_text()
        assert _close_code(closed.value) == ws_module.KEY_INVALID


def test_socket_auth_spends_the_validate_budget(client, monkeypatch):
    original = validate_bucket.capacity
    validate_bucket.capacity = 1
    validate_bucket.reset()
    try:
        with client.websocket_connect("/api/v1/ws", headers=ORIGIN) as ws:
            ws.send_text(json.dumps({"type": "auth", "key": "vh_live_" + "x" * 32}))
            assert recv(ws)["reason"] == "invalid_key"
        with client.websocket_connect("/api/v1/ws", headers=ORIGIN) as ws:
            ws.send_text(json.dumps({"type": "auth", "key": "vh_live_" + "x" * 32}))
            assert recv(ws) == {"type": "error", "reason": "rate_limited"}
    finally:
        validate_bucket.capacity = original
        validate_bucket.reset()


def _close_code(exc: BaseException) -> int | None:
    # Starlette's TestClient raises WebSocketDisconnect(code=...).
    return getattr(exc, "code", None)
