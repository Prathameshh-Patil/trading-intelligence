"""Alerts: an admin publishes one, every licensed client receives it.

Two audiences, two routers. `/admin/alerts` is the publish side and the
admin's history, behind the admin JWT. `/alerts` is the catch-up side,
behind a licence key: the socket in `ws.py` has no replay, so a client that
was away asks here for everything newer than the last id it saw, then goes
back to listening.

The tier is the whole contract. The server says which of three an alert is;
the client decides what that looks like. Nothing here is a recommendation.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select

from app.api.dependencies import DB, AdminUser, KeyRow
from app.core.ratelimit import client_ip, limit
from app.models import Alert
from app.schemas import AlertIn, AlertOut
from app.services import audit
from app.services.events import ALERTS_CHANNEL, broadcaster

router = APIRouter(prefix="/alerts", tags=["alerts"])
admin_router = APIRouter(prefix="/admin/alerts", tags=["admin"])

MAX_CATCH_UP = 200


def alert_out(a: Alert) -> AlertOut:
    return AlertOut.model_validate(a)


@router.get("", response_model=list[AlertOut])
def since(
    key: KeyRow,
    db: DB,
    since: int = Query(default=0, ge=0),
    limit_: int = Query(default=50, ge=1, le=MAX_CATCH_UP, alias="limit"),
    _: None = Depends(limit("validate")),
) -> list[AlertOut]:
    """Alerts with `id > since`, unexpired, oldest first. The same per-address
    budget as `/keys/validate`: a reconnect storm is the case both guard."""
    now = datetime.now(UTC)
    rows = db.scalars(
        select(Alert)
        .where(Alert.id > since, (Alert.expires_at.is_(None)) | (Alert.expires_at > now))
        .order_by(Alert.id)
        .limit(limit_)
    )
    return [alert_out(a) for a in rows]


@admin_router.post("", response_model=AlertOut, status_code=201)
def publish(body: AlertIn, request: Request, admin: AdminUser, db: DB) -> AlertOut:
    a = Alert(
        tier=body.tier,
        title=body.title,
        body=body.body,
        symbol=body.symbol or None,
        created_by_id=admin.id,
        expires_at=body.expires_at,
    )
    db.add(a)
    db.flush()
    audit.record(
        db,
        actor_id=admin.id,
        action="alert.publish",
        target_type="alert",
        target_id=a.id,
        detail={"tier": a.tier, "title": a.title, "symbol": a.symbol},
        ip=client_ip(request),
    )
    db.commit()
    db.refresh(a)
    out = alert_out(a)
    broadcaster.publish(ALERTS_CHANNEL, "alert", out.model_dump(mode="json"))
    return out


@admin_router.get("", response_model=list[AlertOut])
def history(
    admin: AdminUser,
    db: DB,
    limit_: int = Query(default=200, ge=1, le=1000, alias="limit"),
    offset: int = Query(default=0, ge=0),
) -> list[AlertOut]:
    rows = db.scalars(select(Alert).order_by(Alert.id.desc()).limit(limit_).offset(offset))
    return [alert_out(a) for a in rows]
