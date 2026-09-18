from datetime import UTC, datetime

from fastapi import APIRouter, Request
from sqlalchemy.orm import Session

from app.api.dependencies import DB, AdminUser, MaybeUser
from app.core.ratelimit import client_ip
from app.models import SiteSetting
from app.schemas import Release, SetRelease
from app.services import audit
from app.services.events import ADMIN_CHANNEL, broadcaster

router = APIRouter(prefix="/site", tags=["site"])


def site_setting(db: Session) -> SiteSetting:
    row = db.get(SiteSetting, 1)
    if row is None:
        row = SiteSetting(id=1, is_public=False)
        db.add(row)
        db.commit()
    return row


@router.get("/release", response_model=Release)
def release(db: DB, user: MaybeUser) -> Release:
    """`can_preview` is the server's word: any signed-in account that is not
    suspended sees the pre-release site."""
    row = site_setting(db)
    return Release(
        is_public=row.is_public,
        can_preview=user is not None and user.status != "suspended",
    )


@router.post("/release", response_model=Release)
def set_release(
    body: SetRelease, request: Request, admin: AdminUser, db: DB
) -> Release:
    row = site_setting(db)
    row.is_public = body.is_public
    row.updated_at = datetime.now(UTC)
    audit.record(
        db,
        actor_id=admin.id,
        action="release.set",
        target_type="site",
        target_id=1,
        detail={"is_public": body.is_public},
        ip=client_ip(request),
    )
    db.commit()
    broadcaster.publish(
        ADMIN_CHANNEL,
        "release.changed",
        {"is_public": row.is_public, "by": admin.email},
    )
    return Release(is_public=row.is_public, can_preview=True)
