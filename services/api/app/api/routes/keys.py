"""S3 and S5 -- the single wire between web and desktop. Keep it single.

`/keys/validate` is what the desktop app calls with `X-API-Key`. `valid: false`
is a **200, not a 401**: the app must tell "your key is bad" (show the licence
screen) apart from "we could not reach the server" (keep working, retry
quietly), and a 401 conflates them. The 503 is the second case.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy.exc import SQLAlchemyError

from app.api.dependencies import DB, ApiKeyHeader, ApprovedUser, CurrentUser
from app.core.ratelimit import client_ip
from app.schemas import LicenceKey, ValidateResponse
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
def validate(x_api_key: ApiKeyHeader, db: DB) -> ValidateResponse:
    try:
        row = keys.lookup(db, x_api_key)
        if row is None:
            return ValidateResponse(valid=False, reason="unknown", **NOT_VALID)
        if row.status == "revoked" or row.user.status != "approved":
            return ValidateResponse(valid=False, reason="revoked", **NOT_VALID)
        now = datetime.now(UTC)
        if row.expires_at is not None and row.expires_at < now:
            return ValidateResponse(valid=False, reason="expired", **NOT_VALID)
        row.last_validated_at = now
        db.commit()
        return ValidateResponse(
            valid=True, tier=row.tier, expires_at=row.expires_at, reason=None
        )  # type: ignore[arg-type]
    except SQLAlchemyError as exc:
        # Same shape as `health/db` and `analyze`: "the thing behind me is not
        # answering". The desktop treats this as unreachable, not as invalid.
        raise HTTPException(
            status_code=503, detail={"error": f"key service unreachable: {exc}"}
        ) from exc
