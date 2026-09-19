"""The admin portal's API: queue, audit, events, tickets, release switch."""

import json
import threading
import time

import httpx
import pytest

from tests.conftest import bearer

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


def test_signup_appears_in_the_pending_queue_and_stats(client, admin):
    client.post(
        "/api/v1/auth/signup",
        json={"email": "queue@example.com", "password": "correct horse battery"},
    )
    pending = client.get("/api/v1/admin/users?status=pending", headers=admin).json()
    assert [u["email"] for u in pending] == ["queue@example.com"]
    assert pending[0]["key"] is None
    stats = client.get("/api/v1/admin/stats", headers=admin).json()
    assert stats["pending"] == 1 and stats["approved"] == 1  # the admin


def test_user_detail_carries_key_payments_tickets_sessions(
    client, admin, pending_user, login
):
    token = bearer(login(pending_user.email))
    client.post(
        "/api/v1/tickets",
        json={"category": "install", "subject": "Help", "body": "It broke"},
        headers=token,
    )
    client.post(f"/api/v1/admin/users/{pending_user.id}/approve", headers=admin)
    r = client.get(f"/api/v1/admin/users/{pending_user.id}", headers=admin)
    assert r.status_code == 200
    body = r.json()
    assert body["key"]["prefix"].startswith("vh_live_")
    assert body["tickets"][0]["subject"] == "Help"
    assert len(body["sessions"]) == 1
    assert body["open_tickets"] == 1


def test_every_admin_mutation_lands_in_the_audit_log(client, admin, pending_user):
    client.post(f"/api/v1/admin/users/{pending_user.id}/approve", headers=admin)
    client.post(
        f"/api/v1/admin/users/{pending_user.id}/note",
        json={"note": "paid in USDT"},
        headers=admin,
    )
    client.post("/api/v1/site/release", json={"is_public": True}, headers=admin)
    log = client.get("/api/v1/admin/audit", headers=admin).json()
    actions = [a["action"] for a in log]
    assert actions[:3] == ["release.set", "user.note", "user.approve"]
    assert log[2]["detail"]["minted"] is True
    assert log[0]["actor"] == "admin@example.com"


def test_admin_cannot_suspend_or_demote_themselves(client, admin):
    me = client.get("/api/v1/auth/me", headers=admin).json()
    assert (
        client.post(
            f"/api/v1/admin/users/{me['id']}/suspend", headers=admin
        ).status_code
        == 409
    )
    assert (
        client.post(
            f"/api/v1/admin/users/{me['id']}/role", json={"role": "user"}, headers=admin
        ).status_code
        == 409
    )


def test_promote_by_email(client, admin, pending_user, login):
    r = client.post(
        "/api/v1/admin/promote", json={"email": pending_user.email}, headers=admin
    )
    assert (
        r.status_code == 200
        and r.json()["role"] == "admin"
        and r.json()["status"] == "approved"
    )
    # The promoted account can now read the queue.
    assert (
        client.get(
            "/api/v1/admin/users", headers=bearer(login(pending_user.email))
        ).status_code
        == 200
    )


def test_release_switch_and_preview(client, admin, pending_user, login):
    assert client.get("/api/v1/site/release").json() == {
        "is_public": False,
        "can_preview": False,
    }
    r = client.get("/api/v1/site/release", headers=bearer(login(pending_user.email)))
    assert r.json() == {"is_public": False, "can_preview": True}
    client.post("/api/v1/site/release", json={"is_public": True}, headers=admin)
    assert client.get("/api/v1/site/release").json()["is_public"] is True


def test_ticket_thread_reply_and_close(client, admin, pending_user, login):
    token = bearer(login(pending_user.email))
    t = client.post(
        "/api/v1/tickets",
        json={"category": "billing", "subject": "Q", "body": "?"},
        headers=token,
    ).json()
    assert t["ref"].startswith("VH-") and t["status"] == "open"
    r = client.post(
        f"/api/v1/admin/tickets/{t['id']}/reply",
        json={"body": "Answer."},
        headers=admin,
    )
    assert r.json()["status"] == "answered"
    assert r.json()["replies"][0]["from_staff"] is True
    mine = client.get("/api/v1/tickets/mine", headers=token).json()
    assert mine[0]["replies"][0]["body"] == "Answer."
    assert (
        client.post(f"/api/v1/admin/tickets/{t['id']}/close", headers=admin).json()[
            "status"
        ]
        == "closed"
    )


def test_anonymous_ticket_needs_an_email(client):
    assert (
        client.post(
            "/api/v1/tickets", json={"category": "x", "subject": "y", "body": "z"}
        ).status_code
        == 422
    )
    r = client.post(
        "/api/v1/tickets",
        json={
            "email": "anon@x.example.com",
            "category": "x",
            "subject": "y",
            "body": "z",
        },
    )
    assert r.status_code == 201


def test_waitlist_is_idempotent_and_listed(client, admin):
    assert (
        client.post("/api/v1/waitlist", json={"email": "W@x.example.com"}).status_code
        == 204
    )
    assert (
        client.post("/api/v1/waitlist", json={"email": "w@x.example.com"}).status_code
        == 204
    )
    assert [
        w["email"] for w in client.get("/api/v1/admin/waitlist", headers=admin).json()
    ] == ["w@x.example.com"]


def test_payment_proof_is_served_to_owner_and_admin_only(
    client, admin, pending_user, login, make_user
):
    token = bearer(login(pending_user.email))
    r = client.post(
        "/api/v1/payments",
        data={
            "plan": "core",
            "method": "upi",
            "amount": "3499",
            "currency": "inr",
            "reference": "UPI123",
        },
        files={"proof": ("shot.png", PNG, "image/png")},
        headers=token,
    )
    assert r.status_code == 201, r.text
    p = r.json()
    assert p["proof_url"] == f"/api/v1/payments/{p['id']}/proof"
    assert client.get(p["proof_url"], headers=token).content == PNG
    assert client.get(p["proof_url"], headers=admin).status_code == 200
    make_user("other@example.com")
    assert (
        client.get(
            p["proof_url"], headers=bearer(login("other@example.com"))
        ).status_code
        == 404
    )
    assert client.get(p["proof_url"]).status_code == 401
    assert (
        client.get("/api/v1/admin/payments", headers=admin).json()[0]["email"]
        == pending_user.email
    )


def test_bad_proof_types_are_refused(client, pending_user, login):
    r = client.post(
        "/api/v1/payments",
        data={
            "plan": "core",
            "method": "upi",
            "amount": "1",
            "currency": "usd",
            "reference": "x",
        },
        files={"proof": ("evil.html", b"<script>", "text/html")},
        headers=bearer(login(pending_user.email)),
    )
    assert r.status_code == 415


@pytest.fixture
def live_server(client):
    """A real uvicorn server on a free port, sharing the test's app (and so its
    dependency overrides and transaction). `TestClient` buffers whole bodies,
    which an endless event stream never has -- so the stream is read over
    real HTTP instead."""
    import socket

    import uvicorn

    from app.main import app

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    config = uvicorn.Config(
        app, host="127.0.0.1", port=port, log_level="warning", lifespan="on"
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 10
    while not server.started and time.time() < deadline:
        time.sleep(0.05)
    assert server.started
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(5)


def _read_events(base, path, headers, wanted, out, ready):
    with httpx.stream("GET", base + path, headers=headers, timeout=10) as r:
        assert r.status_code == 200, r.text
        assert r.headers["content-type"].startswith("text/event-stream")
        event = None
        for line in r.iter_lines():
            if line.startswith("event:"):
                event = line.split(":", 1)[1].strip()
                if event == "hello":
                    ready.set()
            elif line.startswith("data:") and event == wanted:
                out.append(json.loads(line.split(":", 1)[1]))
                return


def test_sse_delivers_approval_to_the_user_and_the_admin(
    live_server, admin, pending_user, login
):
    user_headers = bearer(login(pending_user.email))
    got_user, got_admin = [], []
    ready_user, ready_admin = threading.Event(), threading.Event()
    t1 = threading.Thread(
        target=_read_events,
        args=(
            live_server,
            "/api/v1/events",
            user_headers,
            "user.approved",
            got_user,
            ready_user,
        ),
    )
    t2 = threading.Thread(
        target=_read_events,
        args=(
            live_server,
            "/api/v1/admin/events",
            admin,
            "user.approved",
            got_admin,
            ready_admin,
        ),
    )
    # One at a time: the test shares a single database connection, and two
    # streams authenticating at once would open two savepoints on it.
    t1.start()
    assert ready_user.wait(5)
    t2.start()
    assert ready_admin.wait(5)

    r = httpx.post(
        f"{live_server}/api/v1/admin/users/{pending_user.id}/approve",
        headers=admin,
        timeout=10,
    )
    assert r.status_code == 200, r.text

    t1.join(5)
    t2.join(5)
    assert (
        got_user
        and got_user[0]["status"] == "approved"
        and got_user[0]["prefix"].startswith("vh_live_")
    )
    assert got_admin and got_admin[0]["email"] == pending_user.email


def test_events_need_a_token_and_admin_events_need_an_admin(
    client, pending_user, login
):
    assert client.get("/api/v1/events").status_code == 401
    assert (
        client.get(
            "/api/v1/admin/events", headers=bearer(login(pending_user.email))
        ).status_code
        == 403
    )
