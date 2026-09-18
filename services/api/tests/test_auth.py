"""Sign up, sign in, refresh rotation, reuse detection, log out everywhere."""

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from sqlalchemy import select

from app.config import settings
from app.core.ratelimit import auth_bucket
from app.core.security import mint_access_token
from app.models import RefreshToken, User
from tests.conftest import PASSWORD, bearer

COOKIE = settings.refresh_cookie_name


def test_signup_creates_a_pending_account_and_signs_in(client, db):
    r = client.post(
        "/api/v1/auth/signup", json={"email": "New@Example.com", "password": PASSWORD}
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == settings.access_ttl_seconds
    assert body["user"]["email"] == "new@example.com"
    assert body["user"]["status"] == "pending"
    assert body["user"]["role"] == "user"
    # The refresh cookie is httpOnly and scoped to the auth path only.
    set_cookie = r.headers["set-cookie"]
    assert f"{COOKIE}=" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "Path=/api/v1/auth" in set_cookie
    assert "SameSite=lax" in set_cookie.lower().replace("samesite=lax", "SameSite=lax")
    assert r.headers["cache-control"] == "no-store"
    assert (
        db.scalar(select(User).where(User.email == "new@example.com")).status
        == "pending"
    )


def test_signup_rejects_short_passwords(client):
    r = client.post(
        "/api/v1/auth/signup", json={"email": "a@b.example.com", "password": "short"}
    )
    assert r.status_code == 422


def test_signup_twice_is_a_409(client):
    payload = {"email": "dup@example.com", "password": PASSWORD}
    assert client.post("/api/v1/auth/signup", json=payload).status_code == 201
    assert client.post("/api/v1/auth/signup", json=payload).status_code == 409


def test_login_wrong_password_and_unknown_email_look_the_same(client, make_user):
    make_user("known@example.com")
    bad = client.post(
        "/api/v1/auth/login",
        json={"email": "known@example.com", "password": "not the password"},
    )
    unknown = client.post(
        "/api/v1/auth/login", json={"email": "nobody@example.com", "password": PASSWORD}
    )
    assert bad.status_code == unknown.status_code == 401
    assert bad.json() == unknown.json()
    assert COOKIE not in bad.headers.get("set-cookie", "")


def test_access_token_is_an_eddsa_jwt_with_the_expected_claims(
    client, make_user, login
):
    make_user("claims@example.com", status="approved")
    token = login("claims@example.com")
    header = jwt.get_unverified_header(token)
    assert header["alg"] == "EdDSA"
    assert header["kid"] == settings.jwt_active_kid
    claims = jwt.decode(
        token, options={"verify_signature": False}, audience=settings.jwt_audience
    )
    assert claims["iss"] == settings.jwt_issuer
    assert claims["aud"] == settings.jwt_audience
    assert claims["role"] == "user"
    assert claims["status"] == "approved"
    assert claims["tv"] == 0
    assert claims["exp"] - claims["iat"] == settings.access_ttl_seconds
    assert len(claims["jti"]) == 32


def test_me_requires_a_valid_bearer(client, make_user, login):
    make_user("me@example.com")
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get("/api/v1/auth/me", headers=bearer("garbage")).status_code == 401
    r = client.get("/api/v1/auth/me", headers=bearer(login("me@example.com")))
    assert r.status_code == 200
    assert r.json()["email"] == "me@example.com"


def test_tampered_expired_and_wrong_audience_tokens_are_refused(
    client, make_user, login
):
    user = make_user("tamper@example.com")
    good = login("tamper@example.com")

    # Flip a character in the signature.
    head, body, sig = good.split(".")
    tampered = f"{head}.{body}.{'A' if sig[0] != 'A' else 'B'}{sig[1:]}"
    assert client.get("/api/v1/auth/me", headers=bearer(tampered)).status_code == 401

    expired, _ = mint_access_token(
        user_id=user.id,
        role="user",
        status="pending",
        token_version=0,
        now=datetime.now(UTC) - timedelta(hours=1),
    )
    assert client.get("/api/v1/auth/me", headers=bearer(expired)).status_code == 401

    settings.jwt_audience = "someone-else"
    try:
        wrong_aud, _ = mint_access_token(
            user_id=user.id, role="user", status="pending", token_version=0
        )
    finally:
        settings.jwt_audience = "vision-hub"
    assert client.get("/api/v1/auth/me", headers=bearer(wrong_aud)).status_code == 401


def test_refresh_rotates_and_the_old_token_is_dead(client, make_user, db):
    make_user("rotate@example.com")
    r = client.post(
        "/api/v1/auth/login", json={"email": "rotate@example.com", "password": PASSWORD}
    )
    first = r.cookies[COOKIE]

    r2 = client.post(
        "/api/v1/auth/refresh", headers={"Origin": "https://visionhub.test"}
    )
    assert r2.status_code == 200, r2.text
    second = r2.cookies[COOKIE]
    assert second != first
    assert r2.json()["access_token"]

    rows = list(db.scalars(select(RefreshToken).order_by(RefreshToken.id)))
    assert len(rows) == 2
    assert rows[0].used_at is not None
    assert rows[1].parent_id == rows[0].id
    assert rows[0].family_id == rows[1].family_id

    # Presenting the first token again is reuse: the whole family dies,
    # including the second token the legitimate client still holds.
    client.cookies.set(COOKIE, first, path="/api/v1/auth")
    r3 = client.post(
        "/api/v1/auth/refresh", headers={"Origin": "https://visionhub.test"}
    )
    assert r3.status_code == 401
    client.cookies.set(COOKIE, second, path="/api/v1/auth")
    r4 = client.post(
        "/api/v1/auth/refresh", headers={"Origin": "https://visionhub.test"}
    )
    assert r4.status_code == 401
    assert all(row.revoked_at is not None for row in db.scalars(select(RefreshToken)))


def test_refresh_from_a_foreign_origin_is_refused(client, make_user):
    make_user("csrf@example.com")
    client.post(
        "/api/v1/auth/login", json={"email": "csrf@example.com", "password": PASSWORD}
    )
    r = client.post("/api/v1/auth/refresh", headers={"Origin": "https://evil.example"})
    assert r.status_code == 403
    # ...and from a trusted one, or with no Origin at all (not a browser), it works.
    assert (
        client.post(
            "/api/v1/auth/refresh", headers={"Origin": "http://localhost:3000"}
        ).status_code
        == 200
    )
    assert client.post("/api/v1/auth/refresh").status_code == 200


def test_refresh_without_a_cookie_is_401(client):
    assert client.post("/api/v1/auth/refresh").status_code == 401


def test_logout_ends_the_session(client, make_user):
    make_user("bye@example.com")
    client.post(
        "/api/v1/auth/login", json={"email": "bye@example.com", "password": PASSWORD}
    )
    r = client.post("/api/v1/auth/logout")
    assert r.status_code == 204
    assert (
        f"{COOKIE}=" in r.headers["set-cookie"]
        and "Max-Age=0" in r.headers["set-cookie"]
    )
    assert client.post("/api/v1/auth/refresh").status_code == 401


def test_logout_all_kills_every_access_token_on_the_next_request(
    client, make_user, login
):
    make_user("everywhere@example.com")
    laptop = login("everywhere@example.com")
    phone = login("everywhere@example.com")
    assert client.get("/api/v1/auth/me", headers=bearer(phone)).status_code == 200

    assert (
        client.post("/api/v1/auth/logout-all", headers=bearer(laptop)).status_code
        == 204
    )

    assert client.get("/api/v1/auth/me", headers=bearer(laptop)).status_code == 401
    assert client.get("/api/v1/auth/me", headers=bearer(phone)).status_code == 401
    assert client.post("/api/v1/auth/refresh").status_code == 401


def test_sessions_lists_live_families_and_can_end_one(client, make_user, login):
    make_user("devices@example.com")
    a = login("devices@example.com")
    login("devices@example.com")  # second device; its cookie is now the client's
    r = client.get("/api/v1/auth/sessions", headers=bearer(a))
    assert r.status_code == 200
    sessions = r.json()
    assert len(sessions) == 2
    assert sum(s["current"] for s in sessions) == 1
    other = next(s for s in sessions if not s["current"])
    assert (
        client.delete(
            f"/api/v1/auth/sessions/{other['family_id']}", headers=bearer(a)
        ).status_code
        == 204
    )
    assert len(client.get("/api/v1/auth/sessions", headers=bearer(a)).json()) == 1


def test_suspended_account_cannot_sign_in_or_keep_working(client, make_user, login, db):
    user = make_user("susp@example.com", status="approved")
    token = login("susp@example.com")
    user.status = "suspended"
    db.commit()
    # Existing access token: refused on the very next request.
    assert client.get("/api/v1/auth/me", headers=bearer(token)).status_code == 403
    assert (
        client.post(
            "/api/v1/auth/login",
            json={"email": "susp@example.com", "password": PASSWORD},
        ).status_code
        == 403
    )
    assert client.post("/api/v1/auth/refresh").status_code == 401


def test_login_is_rate_limited(client, make_user):
    make_user("limited@example.com")
    auth_bucket.capacity = 3
    auth_bucket.reset()
    try:
        codes = [
            client.post(
                "/api/v1/auth/login",
                json={
                    "email": "limited@example.com",
                    "password": "wrong-but-long-enough",
                },
            ).status_code
            for _ in range(5)
        ]
    finally:
        auth_bucket.capacity = settings.rate_limit_auth_per_minute
        auth_bucket.reset()
    assert codes[:3] == [401, 401, 401]
    assert codes[3] == 429
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "limited@example.com", "password": "wrong-but-long-enough"},
    )
    assert r.status_code in (401, 429)


def test_jwks_publishes_the_active_public_key(client):
    r = client.get("/.well-known/jwks.json")
    assert r.status_code == 200
    keys = r.json()["keys"]
    assert any(
        k["kid"] == settings.jwt_active_kid
        and k["kty"] == "OKP"
        and k["crv"] == "Ed25519"
        for k in keys
    )
    assert all("d" not in k for k in keys)


@pytest.mark.parametrize(
    "origin", ["https://visionhub.test", "https://admin.visionhub.test"]
)
def test_cors_allows_the_two_sites_with_credentials(client, origin):
    r = client.options(
        "/api/v1/auth/refresh",
        headers={"Origin": origin, "Access-Control-Request-Method": "POST"},
    )
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == origin
    assert r.headers["access-control-allow-credentials"] == "true"
    allowed = r.headers["access-control-allow-headers"].lower()
    assert "authorization" in allowed and "x-api-key" in allowed
