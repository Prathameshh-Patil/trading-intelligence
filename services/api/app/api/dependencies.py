"""The guards every route hangs off.

`bearer_user` is the only place an access token is read. It verifies the
signature statelessly, then loads the user row -- one primary-key read -- so a
suspension, a rejection, a role change or a "log out everywhere" all take
effect on the *next request*, not fifteen minutes later when the token would
have expired on its own.
"""

from __future__ import annotations

from collections.abc import Generator
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.security import TokenError, verify_access_token
from app.db.session import SessionLocal
from app.models import User


def open_session() -> Session:
    """One place to construct a session, so tests can point it at their
    transaction."""
    return SessionLocal()


def get_db() -> Generator[Session, None, None]:
    db = open_session()

    try:
        yield db
    finally:
        db.close()


DB = Annotated[Session, Depends(get_db)]


def _unauthorized() -> HTTPException:
    # One message whatever went wrong. Which check failed is for the log.
    return HTTPException(
        status_code=401,
        detail={"error": "sign in to continue"},
        headers={"WWW-Authenticate": "Bearer"},
    )


def resolve_bearer(request: Request, db: Session) -> User | None:
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        return None
    token = header[7:].strip()
    try:
        claims = verify_access_token(token)
    except TokenError:
        return None
    try:
        user_id = int(claims["sub"])
    except (KeyError, ValueError):
        return None
    user = db.get(User, user_id)
    if user is None or claims.get("tv") != user.token_version:
        return None
    return user


def bearer_user(request: Request, db: DB) -> User | None:
    """The signed-in user, or None when there is no (valid) bearer token."""
    return resolve_bearer(request, db)


def stream_user(request: Request) -> User | None:
    """`bearer_user` for a streaming route. A `yield` dependency's session
    would stay open for the life of the stream, pinning a pooled connection
    per subscriber; this one is closed before the first byte goes out."""
    db = open_session()
    try:
        user = resolve_bearer(request, db)
        if user is not None:
            db.expunge(user)
        return user
    finally:
        db.close()


MaybeUser = Annotated[User | None, Depends(bearer_user)]


def require_user(user: MaybeUser) -> User:
    if user is None:
        raise _unauthorized()
    if user.status == "suspended":
        raise HTTPException(
            status_code=403, detail={"error": "this account is suspended"}
        )
    return user


CurrentUser = Annotated[User, Depends(require_user)]


def require_approved(user: CurrentUser) -> User:
    if user.status != "approved":
        raise HTTPException(
            status_code=403, detail={"error": "this account is not approved yet"}
        )
    return user


ApprovedUser = Annotated[User, Depends(require_approved)]


def require_stream_user(user: Annotated[User | None, Depends(stream_user)]) -> User:
    return require_user(user)


def require_stream_admin(user: Annotated[User, Depends(require_stream_user)]) -> User:
    return require_admin(user)


StreamUser = Annotated[User, Depends(require_stream_user)]
StreamAdmin = Annotated[User, Depends(require_stream_admin)]


def require_admin(user: CurrentUser) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail={"error": "admins only"})
    return user


AdminUser = Annotated[User, Depends(require_admin)]


def api_key_header(x_api_key: Annotated[str, Header()]) -> str:
    """S3: a missing header is a 422 -- the seventh case, and the one the
    desktop app should never produce."""
    return x_api_key


ApiKeyHeader = Annotated[str, Depends(api_key_header)]
