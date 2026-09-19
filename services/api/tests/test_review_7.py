"""PR #7's review findings, each pinned so it stays fixed.

Numbered as in the review (github.com/.../pull/7#issuecomment-5734302806):
1 spoofable X-Forwarded-For, 2 the per-IP budget shared with refresh,
3 BOOTSTRAP_ADMIN_EMAIL never read, 4 the production guard covering one
secret, 5 reject leaving sessions alive, 6 unlimited tickets/validate/uploads.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.config import Settings, production_problems, settings
from app.core import ratelimit
from app.core.ratelimit import (
    auth_bucket,
    refresh_bucket,
    upload_bucket,
    validate_bucket,
)
from app.models import AuditLog, RefreshToken, User
from app.services.bootstrap import promote_bootstrap_admin
from tests.conftest import PASSWORD, bearer

COOKIE = settings.refresh_cookie_name
ORIGIN = {"Origin": "https://visionhub.test"}
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


@pytest.fixture
def small_bucket():
    """Shrink a bucket for one test and put it back."""
    changed: list[tuple[ratelimit.TokenBucket, int]] = []

    def _shrink(bucket: ratelimit.TokenBucket, capacity: int) -> None:
        changed.append((bucket, bucket.capacity))
        bucket.capacity = capacity
        bucket.reset()

    yield _shrink
    for bucket, capacity in changed:
        bucket.capacity = capacity
        bucket.reset()


# 1 ---------------------------------------------------------------------------


def test_a_forwarded_for_header_does_not_buy_a_fresh_bucket(client, small_bucket):
    small_bucket(auth_bucket, 2)
    codes = [
        client.post(
            "/api/v1/auth/signup",
            json={"email": f"n{i}@example.com", "password": PASSWORD},
            headers={"X-Forwarded-For": f"10.0.0.{i}"},
        ).status_code
        for i in range(4)
    ]
    # Two signups per address, then 429 -- whatever the header says.
    assert codes == [201, 201, 429, 429]


def test_the_header_is_honoured_only_behind_a_trusted_proxy(client, small_bucket, monkeypatch):
    small_bucket(auth_bucket, 2)
    monkeypatch.setattr(settings, "trusted_proxy", True)
    codes = [
        client.post(
            "/api/v1/auth/signup",
            json={"email": f"p{i}@example.com", "password": PASSWORD},
            headers={"X-Forwarded-For": f"10.0.0.{i}, 192.168.1.1"},
        ).status_code
        for i in range(4)
    ]
    assert codes == [201, 201, 201, 201]


def test_the_audit_ip_is_the_peer_not_the_header(client, admin, pending_user, db):
    client.post(
        f"/api/v1/admin/users/{pending_user.id}/approve",
        headers={**admin, "X-Forwarded-For": "203.0.113.9"},
    )
    row = db.scalar(select(AuditLog).where(AuditLog.action == "user.approve"))
    assert row is not None
    assert row.ip != "203.0.113.9"


# 2 ---------------------------------------------------------------------------


def test_refresh_spends_its_own_budget_keyed_on_the_session(client, make_user, small_bucket):
    small_bucket(auth_bucket, 2)
    make_user("tabs@example.com")
    client.post(
        "/api/v1/auth/login", json={"email": "tabs@example.com", "password": PASSWORD}
    )
    # Six refreshes from one address: would have exhausted a shared 2/min
    # auth budget on the third. Each rotates the cookie, and the client keeps it.
    for _ in range(6):
        assert client.post("/api/v1/auth/refresh", headers=ORIGIN).status_code == 200
    # And signup from the same address still has its untouched budget.
    r = client.post(
        "/api/v1/auth/signup", json={"email": "after@example.com", "password": PASSWORD}
    )
    assert r.status_code == 201


def test_refresh_is_still_limited_per_session(client, make_user, small_bucket):
    small_bucket(refresh_bucket, 3)
    make_user("hammer@example.com")
    client.post(
        "/api/v1/auth/login", json={"email": "hammer@example.com", "password": PASSWORD}
    )
    first = client.cookies[COOKIE]
    codes = []
    for _ in range(5):
        # Present the same cookie every time so it is one session's budget.
        client.cookies.set(COOKIE, first, path="/api/v1/auth")
        codes.append(client.post("/api/v1/auth/refresh", headers=ORIGIN).status_code)
    assert 429 in codes


# 3 ---------------------------------------------------------------------------


def test_bootstrap_promotes_an_existing_account_and_audits_it(db, make_user):
    u = make_user("first@example.com")
    assert u.role == "user" and u.status == "pending"
    promoted = promote_bootstrap_admin(db, "First@Example.com")
    assert promoted is u
    assert u.role == "admin" and u.status == "approved" and u.approved_at is not None
    row = db.scalar(select(AuditLog).where(AuditLog.action == "user.bootstrap_admin"))
    assert row is not None and row.target_id == str(u.id)


def test_bootstrap_never_creates_an_account(db):
    assert promote_bootstrap_admin(db, "nobody@example.com") is None
    assert db.scalar(select(User).where(User.email == "nobody@example.com")) is None


def test_bootstrap_is_a_no_op_when_unset_or_already_admin(db, make_user):
    assert promote_bootstrap_admin(db, None) is None
    a = make_user("already@example.com", role="admin", status="approved")
    assert promote_bootstrap_admin(db, a.email) is None


# 4 ---------------------------------------------------------------------------


def _prod(**overrides) -> Settings:
    return settings.model_copy(update={"app_env": "production", **overrides})


def test_production_refuses_to_boot_with_any_secret_missing():
    empty = _prod(cookie_secure=False, jwt_keys=[], jwt_active_kid="", key_encryption_secret="")
    problems = production_problems(empty)
    assert [p.split()[0] for p in problems] == [
        "COOKIE_SECURE",
        "JWT_KEYS",
        "JWT_ACTIVE_KID",
        "KEY_ENCRYPTION_SECRET",
    ]


def test_production_names_an_active_kid_that_is_not_in_the_keyring():
    s = _prod(
        cookie_secure=True,
        jwt_keys=[{"kid": "2026-09", "private_pem": "x", "public_pem": "y"}],
        jwt_active_kid="2025-01",
        key_encryption_secret="s",
    )
    assert production_problems(s) == ["JWT_ACTIVE_KID='2025-01' is not in JWT_KEYS"]


def test_production_with_everything_set_is_clean_and_development_is_never_checked():
    ok = _prod(
        cookie_secure=True,
        jwt_keys=[{"kid": "k", "private_pem": "x", "public_pem": "y"}],
        jwt_active_kid="k",
        key_encryption_secret="s",
    )
    assert production_problems(ok) == []
    dev = settings.model_copy(update={"app_env": "development", "cookie_secure": False})
    assert production_problems(dev) == []


# 5 ---------------------------------------------------------------------------


def test_reject_ends_every_session_like_suspend_does(client, admin, pending_user, login, db):
    token = login(pending_user.email)
    assert client.get("/api/v1/auth/me", headers=bearer(token)).status_code == 200

    r = client.post(
        f"/api/v1/admin/users/{pending_user.id}/reject",
        json={"reason": "not a fit"},
        headers=admin,
    )
    assert r.status_code == 200, r.text

    assert client.get("/api/v1/auth/me", headers=bearer(token)).status_code == 401
    assert client.post("/api/v1/auth/refresh", headers=ORIGIN).status_code == 401
    live = db.scalars(
        select(RefreshToken).where(
            RefreshToken.user_id == pending_user.id, RefreshToken.revoked_at.is_(None)
        )
    ).all()
    assert live == []


# 6 ---------------------------------------------------------------------------


def test_anonymous_tickets_are_rate_limited(client, small_bucket):
    small_bucket(auth_bucket, 2)
    body = {"email": "anon@example.com", "category": "billing", "subject": "s", "body": "b"}
    codes = [client.post("/api/v1/tickets", json=body).status_code for _ in range(3)]
    assert codes == [201, 201, 429]


def test_validate_has_its_own_budget(client, small_bucket):
    small_bucket(validate_bucket, 2)
    codes = [
        client.post(
            "/api/v1/keys/validate", headers={"X-API-Key": "vh_live_" + "x" * 32}
        ).status_code
        for _ in range(3)
    ]
    assert codes == [200, 200, 429]


def test_uploads_are_rate_limited(client, pending_user, login, small_bucket):
    small_bucket(upload_bucket, 1)
    token = bearer(login(pending_user.email))
    form = {"plan": "core", "method": "upi", "amount": "1", "currency": "inr", "reference": "r"}
    codes = [
        client.post(
            "/api/v1/payments",
            data=form,
            files={"proof": ("p.png", PNG, "image/png")},
            headers=token,
        ).status_code
        for _ in range(2)
    ]
    assert codes == [201, 429]


def test_an_upload_is_typed_by_its_bytes_not_its_label(client, pending_user, login):
    token = bearer(login(pending_user.email))
    form = {"plan": "core", "method": "upi", "amount": "1", "currency": "inr", "reference": "r"}
    html = client.post(
        "/api/v1/payments",
        data=form,
        files={"proof": ("p.png", b"<html><script>1</script>", "image/png")},
        headers=token,
    )
    assert html.status_code == 415

    pdf = client.post(
        "/api/v1/payments",
        data=form,
        files={"proof": ("p.png", b"%PDF-1.4 fake", "image/png")},
        headers=token,
    )
    assert pdf.status_code == 201, pdf.text
    served = client.get(pdf.json()["proof_url"], headers=token)
    assert served.headers["content-type"].startswith("application/pdf")


# worth fixing --------------------------------------------------------------


def test_the_batched_user_out_matches_the_per_user_one(client, admin, pending_user, login, db):
    from app.api.routes.admin import UserFacts, user_out

    token = bearer(login(pending_user.email))
    client.post(
        "/api/v1/tickets",
        json={"category": "install", "subject": "s", "body": "b"},
        headers=token,
    )
    client.post(f"/api/v1/admin/users/{pending_user.id}/approve", headers=admin)
    users = list(db.scalars(select(User)))
    facts = UserFacts(db, users)
    for u in users:
        assert user_out(db, u, facts) == user_out(db, u)
    me = next(u for u in users if u.id == pending_user.id)
    out = user_out(db, me, facts)
    assert out.open_tickets == 1 and out.key is not None and out.approved_by is not None


def test_admin_lists_page(client, admin):
    for i in range(3):
        client.post("/api/v1/waitlist", json={"email": f"w{i}@example.com"})
    first = client.get("/api/v1/admin/waitlist?limit=2", headers=admin).json()
    rest = client.get("/api/v1/admin/waitlist?limit=2&offset=2", headers=admin).json()
    assert len(first) == 2 and len(rest) == 1
    assert {w["email"] for w in first + rest} == {f"w{i}@example.com" for i in range(3)}
    assert client.get("/api/v1/admin/keys?limit=0", headers=admin).status_code == 422
