"""S3 and S5 -- the single wire between web and desktop. Keep it single.

`/keys/validate` is what the desktop app calls with `X-API-Key`. `valid: false`
is a **200, not a 401**: the app must tell "your key is bad" (show the licence
screen) apart from "we could not reach the server" (keep working, retry
quietly), and a 401 conflates them. The 503 is the second case.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.exc import SQLAlchemyError

from app.api.dependencies import DB, ApiKeyHeader, ApprovedUser, CurrentUser
from app.core.ratelimit import client_ip, limit
from app.schemas import Activation, LicenceKey, ValidateResponse
from app.services import audit, keys
from app.services.events import ADMIN_CHANNEL, broadcaster, user_channel

router = APIRouter(prefix="/keys", tags=["keys"])


def licence_of(row) -> LicenceKey:
    return LicenceKey(key=keys.reveal(row), tier=row.tier, created_at=row.created_at)


@router.get("/mine", response_model=LicenceKey)
def mine(user: CurrentUser, db: DB) -> LicenceKey:
    """S5's exit door. 404 is "not yet" -- a real answer, not a failure."""
    if user.status != "approved":
        raise HTTPException(
            status_code=404, detail={"error": "no key yet", "reason": user.status}
        )
    row = keys.active_key(db, user.id)
    if row is None:
        raise HTTPException(
            status_code=404, detail={"error": "no key yet", "reason": "revoked"}
        )
    return licence_of(row)


@router.get("/mine/activation", response_model=Activation)
def activation(user: CurrentUser, db: DB) -> Activation:
    """The account page's last timeline step: has the app actually run with
    this key? `validate` writes `last_validated_at`; this reads it. A user
    without an active key simply has not activated -- no 404, because the
    question has an answer either way."""
    row = keys.active_key(db, user.id) if user.status == "approved" else None
    seen = row.last_validated_at if row is not None else None
    return Activation(activated=seen is not None, last_validated_at=seen)


@router.post("/mine/rotate", response_model=LicenceKey)
def rotate_mine(request: Request, user: ApprovedUser, db: DB) -> LicenceKey:
    row = keys.rotate(db, user)
    audit.record(
        db,
        actor_id=user.id,
        action="key.rotate",
        target_type="user",
        target_id=user.id,
        detail={"prefix": row.prefix, "self": True},
        ip=client_ip(request),
    )
    db.commit()
    broadcaster.publish(user_channel(user.id), "key.rotated", {"prefix": row.prefix})
    broadcaster.publish(
        ADMIN_CHANNEL,
        "key.rotated",
        {"user_id": user.id, "email": user.email, "prefix": row.prefix},
    )
    return licence_of(row)


NOT_VALID = {"tier": None, "expires_at": None}


@router.post("/validate", response_model=ValidateResponse)
def validate(
    x_api_key: ApiKeyHeader, db: DB, _: None = Depends(limit("validate"))
) -> ValidateResponse:
    # Its own budget (`rate_limit_validate_per_minute`): an unauthenticated
    # route that must not be a free oracle for guessing keys, and an office of
    # desktops behind one address that must not read as one.
    try:
        row, reason = keys.resolve(db, x_api_key)
        if row is None:
            return ValidateResponse(valid=False, reason=reason, **NOT_VALID)
        now = datetime.now(UTC)
        first = row.last_validated_at is None
        row.last_validated_at = now
        db.commit()
        if first:
            # The account page's last timeline step. Once, on the first
            # validation -- every later one is the app's routine six-hourly
            # check and nobody is waiting on it.
            broadcaster.publish(
                user_channel(row.user_id),
                "key.activated",
                {"prefix": row.prefix, "at": now.isoformat()},
            )
        return ValidateResponse(
            valid=True, tier=row.tier, expires_at=row.expires_at, reason=None
        )  # type: ignore[arg-type]
    except SQLAlchemyError as exc:
        # Same shape as `health/db` and `analyze`: "the thing behind me is not
        # answering". The desktop treats this as unreachable, not as invalid.
        raise HTTPException(
            status_code=503, detail={"error": f"key service unreachable: {exc}"}
        ) from exc
