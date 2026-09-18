"""Sign up, sign in, refresh, sign out.

Two tokens. The **access token** is a 15-minute Ed25519 JWT the browser keeps
in memory and sends as `Authorization: Bearer`. The **refresh token** is an
opaque random string in an httpOnly cookie scoped to `/api/v1/auth`, so it is
sent to the two routes below that need it and to nothing else.

Refresh tokens rotate on every use. Each login starts a *family*; every
refresh replaces the token with a child in the same family and marks the
parent used. A parent presented a second time is the signature of a stolen
token -- the client that holds the legitimate child would never send the
parent again -- so the whole family is revoked and both holders are signed
out. The attacker keeps nothing; the user signs in again.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func, select

from app.api.dependencies import DB, CurrentUser
from app.config import settings
from app.core.origins import origin_allowed
from app.core.ratelimit import client_ip, limit
from app.core.security import (
    DUMMY_HASH,
    hash_password,
    mint_access_token,
    new_refresh_token,
    password_needs_rehash,
    sha256_hex,
    verify_password,
)
from app.models import RefreshToken, User
from app.schemas import AuthResponse, Credentials, Me, SessionInfo
from app.services.events import ADMIN_CHANNEL, broadcaster

router = APIRouter(prefix="/auth", tags=["auth"])

NO_STORE = {"Cache-Control": "no-store"}


def me_of(user: User) -> Me:
    return Me(
        id=user.id,
        email=user.email,
        role=user.role,
        status=user.status,
        created_at=user.created_at,
    )  # type: ignore[arg-type]


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=token,
        max_age=settings.refresh_ttl_days * 86400,
        path=settings.refresh_cookie_path,
        domain=settings.cookie_domain,
        secure=settings.cookie_secure,
        httponly=True,
        samesite="lax",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.refresh_cookie_name,
        path=settings.refresh_cookie_path,
        domain=settings.cookie_domain,
        secure=settings.cookie_secure,
        httponly=True,
        samesite="lax",
    )


def _issue(
    db,
    request: Request,
    response: Response,
    user: User,
    *,
    family_id: str,
    parent: RefreshToken | None,
) -> AuthResponse:
    """Mint an access token and a fresh refresh token in `family_id`."""
    now = datetime.now(UTC)
    plain = new_refresh_token()
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=sha256_hex(plain),
            family_id=family_id,
            parent_id=parent.id if parent else None,
            expires_at=now + timedelta(days=settings.refresh_ttl_days),
            user_agent=(request.headers.get("user-agent") or "")[:512] or None,
            ip=client_ip(request),
        )
    )
    access, expires_in = mint_access_token(
        user_id=user.id,
        role=user.role,
        status=user.status,
        token_version=user.token_version,
        now=now,
    )
    db.commit()
    _set_refresh_cookie(response, plain)
    response.headers.update(NO_STORE)
    return AuthResponse(access_token=access, expires_in=expires_in, user=me_of(user))


def _email_key(request: Request) -> str:
    # Best effort: the body is JSON and small. If it is not parseable the
    # per-IP bucket still applies.
    return getattr(request.state, "email_key", "?")


@router.post("/signup", response_model=AuthResponse, status_code=201)
def signup(
    body: Credentials,
    request: Request,
    response: Response,
    db: DB,
    _: None = Depends(limit("signup")),
) -> AuthResponse:
    email = body.email.lower()
    if db.scalar(select(User.id).where(User.email == email)):
        # Says so plainly. Hiding this would mean not signing the person in,
        # and the per-IP limit above is what stops bulk enumeration.
        raise HTTPException(
            status_code=409,
            detail={"error": "an account with this email already exists"},
        )
    user = User(
        email=email,
        password_hash=hash_password(body.password),
        last_login_at=datetime.now(UTC),
    )
    db.add(user)
    db.flush()
    broadcaster.publish(
        ADMIN_CHANNEL, "user.signed_up", {"user_id": user.id, "email": user.email}
    )
    return _issue(db, request, response, user, family_id=uuid.uuid4().hex, parent=None)


@router.post("/login", response_model=AuthResponse)
def login(
    body: Credentials,
    request: Request,
    response: Response,
    db: DB,
    _: None = Depends(limit("login")),
) -> AuthResponse:
    email = body.email.lower()
    # Per-email bucket, so one address cannot be hammered from many IPs.
    wait = limit("login-email", lambda _r: email)
    wait(request)

    user = db.scalar(select(User).where(User.email == email))
    # Same work whether or not the email exists, so the timing does not say.
    ok = verify_password(body.password, user.password_hash if user else DUMMY_HASH)
    if not user or not ok:
        raise HTTPException(
            status_code=401, detail={"error": "email or password is wrong"}
        )
    if user.status == "suspended":
        raise HTTPException(
            status_code=403, detail={"error": "this account is suspended"}
        )
    if password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(body.password)
    user.last_login_at = datetime.now(UTC)
    return _issue(db, request, response, user, family_id=uuid.uuid4().hex, parent=None)


@router.post("/refresh", response_model=AuthResponse)
def refresh(
    request: Request,
    response: Response,
    db: DB,
    _: None = Depends(limit("refresh")),
) -> AuthResponse:
    if not origin_allowed(request.headers.get("origin")):
        raise HTTPException(status_code=403, detail={"error": "origin not allowed"})

    plain = request.cookies.get(settings.refresh_cookie_name)
    if not plain:
        raise HTTPException(status_code=401, detail={"error": "no session"})

    row = db.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == sha256_hex(plain))
    )
    now = datetime.now(UTC)

    def reject(reason: str) -> HTTPException:
        _clear_refresh_cookie(response)
        return HTTPException(
            status_code=401, detail={"error": reason}, headers=dict(response.headers)
        )

    if row is None:
        raise reject("no session")
    if row.revoked_at is not None:
        raise reject("session ended")
    if row.used_at is not None:
        # Reuse. Whoever holds the child is now signed out too.
        _revoke_family(db, row.family_id, now)
        db.commit()
        raise reject("session ended")
    if row.expires_at < now:
        raise reject("session expired")

    user = db.get(User, row.user_id)
    if user is None or user.status == "suspended":
        _revoke_family(db, row.family_id, now)
        db.commit()
        raise reject("session ended")

    row.used_at = now
    return _issue(db, request, response, user, family_id=row.family_id, parent=row)


def _revoke_family(db, family_id: str, now: datetime) -> None:
    for token in db.scalars(
        select(RefreshToken).where(
            RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None)
        )
    ):
        token.revoked_at = now


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, db: DB) -> Response:
    plain = request.cookies.get(settings.refresh_cookie_name)
    if plain:
        row = db.scalar(
            select(RefreshToken).where(RefreshToken.token_hash == sha256_hex(plain))
        )
        if row:
            _revoke_family(db, row.family_id, datetime.now(UTC))
            db.commit()
    out = Response(status_code=204)
    _clear_refresh_cookie(out)
    return out


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
def logout_all(user: CurrentUser, db: DB) -> Response:
    """Every device: bump the token version (kills access tokens on their next
    request) and revoke every refresh token (kills the sessions)."""
    user.token_version += 1
    now = datetime.now(UTC)
    for token in db.scalars(
        select(RefreshToken).where(
            RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None)
        )
    ):
        token.revoked_at = now
    db.commit()
    out = Response(status_code=204)
    _clear_refresh_cookie(out)
    return out


@router.get("/me", response_model=Me)
def me(user: CurrentUser, response: Response) -> Me:
    response.headers.update(NO_STORE)
    return me_of(user)


def _live_families(db, user_id: int) -> list[RefreshToken]:
    """The newest row of each family that is still alive."""
    now = datetime.now(UTC)
    latest = (
        select(RefreshToken.family_id, func.max(RefreshToken.id).label("id"))
        .where(RefreshToken.user_id == user_id)
        .group_by(RefreshToken.family_id)
        .subquery()
    )
    rows = db.scalars(
        select(RefreshToken)
        .join(latest, RefreshToken.id == latest.c.id)
        .where(RefreshToken.revoked_at.is_(None), RefreshToken.expires_at > now)
        .order_by(RefreshToken.created_at.desc())
    )
    return list(rows)


def sessions_of(db, user_id: int, current_family: str | None) -> list[SessionInfo]:
    out = []
    for row in _live_families(db, user_id):
        first = db.scalar(
            select(func.min(RefreshToken.created_at)).where(
                RefreshToken.family_id == row.family_id
            )
        )
        out.append(
            SessionInfo(
                family_id=row.family_id,
                created_at=first or row.created_at,
                last_used_at=row.created_at,
                user_agent=row.user_agent,
                ip=row.ip,
                current=row.family_id == current_family,
            )
        )
    return out


def _current_family(request: Request, db) -> str | None:
    plain = request.cookies.get(settings.refresh_cookie_name)
    if not plain:
        return None
    row = db.scalar(
        select(RefreshToken.family_id).where(
            RefreshToken.token_hash == sha256_hex(plain)
        )
    )
    return row


@router.get("/sessions", response_model=list[SessionInfo])
def sessions(request: Request, user: CurrentUser, db: DB) -> list[SessionInfo]:
    return sessions_of(db, user.id, _current_family(request, db))


@router.delete("/sessions/{family_id}", status_code=status.HTTP_204_NO_CONTENT)
def end_session(family_id: str, user: CurrentUser, db: DB) -> Response:
    owned = db.scalar(
        select(RefreshToken.id).where(
            RefreshToken.family_id == family_id, RefreshToken.user_id == user.id
        )
    )
    if not owned:
        raise HTTPException(status_code=404, detail={"error": "no such session"})
    _revoke_family(db, family_id, datetime.now(UTC))
    db.commit()
    return Response(status_code=204)
