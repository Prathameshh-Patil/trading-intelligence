"""Approval mints the key; S3's validate branches; rotation and revocation."""

import re

import pytest

from app.core.security import KEY_PREFIX
from tests.conftest import bearer

KEY_RE = re.compile(rf"^{KEY_PREFIX}[a-z0-9]{{32}}$")


def validate(client, key):
    return client.post("/api/v1/keys/validate", headers={"X-API-Key": key})


def test_mine_is_404_until_approved(client, pending_user, login):
    r = client.get("/api/v1/keys/mine", headers=bearer(login(pending_user.email)))
    assert r.status_code == 404
    assert r.json()["detail"]["reason"] == "pending"


def test_approve_mints_a_key_the_user_can_then_see(client, admin, pending_user, login):
    r = client.post(f"/api/v1/admin/users/{pending_user.id}/approve", headers=admin)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["minted"] is True
    assert body["user"]["status"] == "approved"
    assert KEY_RE.match(body["key"]["key"])
    assert body["key"]["tier"] == "core"

    mine = client.get("/api/v1/keys/mine", headers=bearer(login(pending_user.email)))
    assert mine.status_code == 200
    assert mine.json()["key"] == body["key"]["key"]


def test_double_approval_returns_the_same_key(client, admin, pending_user):
    first = client.post(
        f"/api/v1/admin/users/{pending_user.id}/approve", headers=admin
    ).json()
    second = client.post(
        f"/api/v1/admin/users/{pending_user.id}/approve", headers=admin
    ).json()
    assert second["minted"] is False
    assert second["key"]["key"] == first["key"]["key"]
    keys = client.get("/api/v1/admin/keys", headers=admin).json()
    assert len([k for k in keys if k["user_id"] == pending_user.id]) == 1


def test_validate_every_s3_branch(client, admin, pending_user, db):
    # unknown
    r = validate(client, KEY_PREFIX + "x" * 32)
    assert r.status_code == 200
    assert r.json() == {
        "valid": False,
        "tier": None,
        "expires_at": None,
        "reason": "unknown",
    }

    key = client.post(
        f"/api/v1/admin/users/{pending_user.id}/approve", headers=admin
    ).json()["key"]["key"]

    # valid
    r = validate(client, key)
    assert r.status_code == 200
    assert r.json() == {
        "valid": True,
        "tier": "core",
        "expires_at": None,
        "reason": None,
    }
    summary = client.get("/api/v1/admin/keys", headers=admin).json()[0]
    assert summary["last_validated_at"] is not None

    # expired
    from datetime import UTC, datetime, timedelta

    from app.models import ApiKey

    row = db.get(ApiKey, summary["id"])
    row.expires_at = datetime.now(UTC) - timedelta(days=1)
    db.commit()
    assert validate(client, key).json()["reason"] == "expired"
    row.expires_at = None
    db.commit()

    # revoked
    r = client.post(f"/api/v1/admin/keys/{summary['id']}/revoke", headers=admin)
    assert r.status_code == 200 and r.json()["status"] == "revoked"
    assert validate(client, key).json() == {
        "valid": False,
        "tier": None,
        "expires_at": None,
        "reason": "revoked",
    }


def test_validate_without_the_header_is_422(client):
    assert client.post("/api/v1/keys/validate").status_code == 422


def test_validate_is_503_when_the_database_is_down(client, monkeypatch):
    from sqlalchemy.exc import OperationalError

    from app.services import keys

    def boom(db, plain):
        raise OperationalError("SELECT 1", {}, Exception("connection refused"))

    monkeypatch.setattr(keys, "lookup", boom)
    r = validate(client, KEY_PREFIX + "y" * 32)
    assert r.status_code == 503
    assert "unreachable" in r.json()["detail"]["error"]


def test_rejecting_revokes_and_validate_says_so(client, admin, pending_user):
    key = client.post(
        f"/api/v1/admin/users/{pending_user.id}/approve", headers=admin
    ).json()["key"]["key"]
    r = client.post(
        f"/api/v1/admin/users/{pending_user.id}/reject",
        json={"reason": "no match"},
        headers=admin,
    )
    assert r.status_code == 200 and r.json()["status"] == "rejected"
    assert validate(client, key).json()["reason"] == "revoked"


def test_suspending_stops_the_key_working_too(client, admin, pending_user):
    key = client.post(
        f"/api/v1/admin/users/{pending_user.id}/approve", headers=admin
    ).json()["key"]["key"]
    client.post(f"/api/v1/admin/users/{pending_user.id}/suspend", headers=admin)
    assert validate(client, key).json()["reason"] == "revoked"
    client.post(f"/api/v1/admin/users/{pending_user.id}/reinstate", headers=admin)
    assert validate(client, key).json()["valid"] is True


def test_user_can_rotate_their_own_key(client, admin, pending_user, login):
    old = client.post(
        f"/api/v1/admin/users/{pending_user.id}/approve", headers=admin
    ).json()["key"]["key"]
    token = bearer(login(pending_user.email))
    r = client.post("/api/v1/keys/mine/rotate", headers=token)
    assert r.status_code == 200
    new = r.json()["key"]
    assert KEY_RE.match(new) and new != old
    assert validate(client, old).json()["reason"] == "revoked"
    assert validate(client, new).json()["valid"] is True
    assert client.get("/api/v1/keys/mine", headers=token).json()["key"] == new


def test_pending_user_cannot_rotate(client, pending_user, login):
    assert (
        client.post(
            "/api/v1/keys/mine/rotate", headers=bearer(login(pending_user.email))
        ).status_code
        == 403
    )


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/api/v1/admin/users"),
        ("get", "/api/v1/admin/keys"),
        ("get", "/api/v1/admin/stats"),
        ("get", "/api/v1/admin/audit"),
        ("post", "/api/v1/admin/users/1/approve"),
        ("post", "/api/v1/site/release"),
    ],
)
def test_admin_routes_refuse_a_normal_account(
    client, pending_user, login, method, path
):
    headers = bearer(login(pending_user.email))
    r = getattr(client, method)(
        path,
        headers=headers,
        **({"json": {"is_public": True}} if "release" in path else {}),
    )
    assert r.status_code == 403
    assert getattr(client, method)(path).status_code == 401
