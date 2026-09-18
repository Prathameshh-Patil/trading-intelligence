"""The admin portal's API. Every mutation here writes an audit row and
publishes an event, so the queue on a second admin's screen moves too.

Approval is the one route that mints a licence key, and it is idempotent:
approving an already-approved account returns the key it already has.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import DB, AdminUser
from app.api.routes.auth import sessions_of
from app.api.routes.keys import licence_of
from app.api.routes.payments import payment_out
from app.api.routes.tickets import staff_ids, ticket_out
from app.core.ratelimit import client_ip
from app.models import (
    ApiKey,
    AuditLog,
    Payment,
    RefreshToken,
    Ticket,
    TicketReply,
    User,
    WaitlistEntry,
)
from app.schemas import (
    ApproveResponse,
    AuditOut,
    KeySummary,
    NoteIn,
    PaymentOut,
    PromoteIn,
    RejectIn,
    ReplyIn,
    RoleIn,
    Stats,
    TicketOut,
    UserDetail,
    UserOut,
    WaitlistOut,
)
from app.services import audit, keys
from app.services.events import ADMIN_CHANNEL, broadcaster, user_channel

router = APIRouter(prefix="/admin", tags=["admin"])


# ------------------------------------------------------------- serialisers


def key_summary(k: ApiKey, email: str) -> KeySummary:
    return KeySummary(
        id=k.id,
        user_id=k.user_id,
        email=email,
        prefix=k.prefix,
        tier=k.tier,  # type: ignore[arg-type]
        status=k.status,
        created_at=k.created_at,
        expires_at=k.expires_at,
        revoked_at=k.revoked_at,
        last_validated_at=k.last_validated_at,
    )


def user_out(db: Session, u: User) -> UserOut:
    key = keys.active_key(db, u.id)
    approver = (
        db.scalar(select(User.email).where(User.id == u.approved_by_id))
        if u.approved_by_id
        else None
    )
    payments_count = (
        db.scalar(
            select(func.count()).select_from(Payment).where(Payment.user_id == u.id)
        )
        or 0
    )
    open_tickets = (
        db.scalar(
            select(func.count())
            .select_from(Ticket)
            .where(
                (Ticket.user_id == u.id) | (Ticket.email == u.email),
                Ticket.status != "closed",
            )
        )
        or 0
    )
    return UserOut(
        id=u.id,
        email=u.email,
        role=u.role,
        status=u.status,
        created_at=u.created_at,  # type: ignore[arg-type]
        last_login_at=u.last_login_at,
        approved_at=u.approved_at,
        approved_by=approver,
        rejection_reason=u.rejection_reason,
        admin_note=u.admin_note,
        key=key_summary(key, u.email) if key else None,
        payments_count=payments_count,
        open_tickets=open_tickets,
    )


def _get_user(db: Session, user_id: int) -> User:
    u = db.get(User, user_id)
    if u is None:
        raise HTTPException(status_code=404, detail={"error": "no such user"})
    return u


def _log(
    db: Session,
    request: Request,
    admin: User,
    action: str,
    target: User,
    detail: dict | None = None,
):
    audit.record(
        db,
        actor_id=admin.id,
        action=action,
        target_type="user",
        target_id=target.id,
        detail={"email": target.email, **(detail or {})},
        ip=client_ip(request),
    )


def _notify(target: User, type_: str, data: dict | None = None) -> None:
    payload = {
        "user_id": target.id,
        "email": target.email,
        "status": target.status,
        **(data or {}),
    }
    broadcaster.publish(user_channel(target.id), type_, payload)
    broadcaster.publish(ADMIN_CHANNEL, type_, payload)


# ------------------------------------------------------------------- stats


@router.get("/stats", response_model=Stats)
def stats(admin: AdminUser, db: DB) -> Stats:
    now = datetime.now(UTC)

    def count_users(status_: str) -> int:
        return (
            db.scalar(
                select(func.count()).select_from(User).where(User.status == status_)
            )
            or 0
        )

    return Stats(
        pending=count_users("pending"),
        approved=count_users("approved"),
        rejected=count_users("rejected"),
        suspended=count_users("suspended"),
        active_keys=db.scalar(
            select(func.count()).select_from(ApiKey).where(ApiKey.status == "active")
        )
        or 0,
        validations_24h=db.scalar(
            select(func.count())
            .select_from(ApiKey)
            .where(ApiKey.last_validated_at > now - timedelta(days=1))
        )
        or 0,
        open_tickets=db.scalar(
            select(func.count()).select_from(Ticket).where(Ticket.status != "closed")
        )
        or 0,
        waitlist=db.scalar(select(func.count()).select_from(WaitlistEntry)) or 0,
        signups_7d=db.scalar(
            select(func.count())
            .select_from(User)
            .where(User.created_at > now - timedelta(days=7))
        )
        or 0,
        live_admins=broadcaster.subscriber_count(ADMIN_CHANNEL),
    )


# ------------------------------------------------------------------- users


@router.get("/users", response_model=list[UserOut])
def users(
    admin: AdminUser,
    db: DB,
    status_: str | None = Query(default=None, alias="status"),
    q: str | None = Query(default=None, max_length=255),
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> list[UserOut]:
    stmt = select(User)
    if status_:
        stmt = stmt.where(User.status == status_)
    if q:
        stmt = stmt.where(User.email.ilike(f"%{q.strip()}%"))
    rows = db.scalars(stmt.order_by(User.created_at.desc()).limit(limit).offset(offset))
    return [user_out(db, u) for u in rows]


@router.get("/users/{user_id}", response_model=UserDetail)
def user_detail(user_id: int, admin: AdminUser, db: DB) -> UserDetail:
    u = _get_user(db, user_id)
    base = user_out(db, u)
    payments = db.scalars(
        select(Payment).where(Payment.user_id == u.id).order_by(Payment.id.desc())
    )
    tickets = db.scalars(
        select(Ticket)
        .where((Ticket.user_id == u.id) | (Ticket.email == u.email))
        .order_by(Ticket.id.desc())
    )
    staff = staff_ids(db)
    return UserDetail(
        **base.model_dump(),
        payments=[payment_out(p, u.email) for p in payments],
        tickets=[ticket_out(t, staff) for t in tickets],
        sessions=sessions_of(db, u.id, None),
    )


@router.post("/users/{user_id}/approve", response_model=ApproveResponse)
def approve(
    user_id: int, request: Request, admin: AdminUser, db: DB
) -> ApproveResponse:
    u = _get_user(db, user_id)
    if u.status == "suspended":
        raise HTTPException(
            status_code=409,
            detail={"error": "reinstate the account before approving it"},
        )
    first_time = u.status != "approved"
    if first_time:
        u.status = "approved"
        u.approved_at = datetime.now(UTC)
        u.approved_by_id = admin.id
        u.rejection_reason = None
    key, minted = keys.issue_for(db, u)
    _log(
        db, request, admin, "user.approve", u, {"minted": minted, "prefix": key.prefix}
    )
    db.commit()
    if first_time or minted:
        _notify(u, "user.approved", {"prefix": key.prefix})
    return ApproveResponse(user=user_out(db, u), key=licence_of(key), minted=minted)


@router.post("/users/{user_id}/reject", response_model=UserOut)
def reject(
    user_id: int, body: RejectIn, request: Request, admin: AdminUser, db: DB
) -> UserOut:
    u = _get_user(db, user_id)
    u.status = "rejected"
    u.rejection_reason = body.reason
    for k in db.scalars(
        select(ApiKey).where(ApiKey.user_id == u.id, ApiKey.status == "active")
    ):
        keys.revoke(db, k)
    _log(db, request, admin, "user.reject", u, {"reason": body.reason})
    db.commit()
    _notify(u, "user.rejected", {"reason": body.reason})
    return user_out(db, u)


@router.post("/users/{user_id}/suspend", response_model=UserOut)
def suspend(user_id: int, request: Request, admin: AdminUser, db: DB) -> UserOut:
    u = _get_user(db, user_id)
    if u.id == admin.id:
        raise HTTPException(
            status_code=409, detail={"error": "you cannot suspend yourself"}
        )
    u.status = "suspended"
    _end_all_sessions(db, u)
    _log(db, request, admin, "user.suspend", u)
    db.commit()
    _notify(u, "user.suspended")
    return user_out(db, u)


@router.post("/users/{user_id}/reinstate", response_model=UserOut)
def reinstate(user_id: int, request: Request, admin: AdminUser, db: DB) -> UserOut:
    u = _get_user(db, user_id)
    if u.status != "suspended":
        raise HTTPException(
            status_code=409, detail={"error": "account is not suspended"}
        )
    # Back to approved if it ever had a key, else back to the queue.
    u.status = "approved" if u.approved_at else "pending"
    _log(db, request, admin, "user.reinstate", u, {"status": u.status})
    db.commit()
    _notify(u, "user.reinstated")
    return user_out(db, u)


@router.post("/users/{user_id}/role", response_model=UserOut)
def set_role(
    user_id: int, body: RoleIn, request: Request, admin: AdminUser, db: DB
) -> UserOut:
    u = _get_user(db, user_id)
    if u.id == admin.id and body.role != "admin":
        raise HTTPException(
            status_code=409, detail={"error": "you cannot demote yourself"}
        )
    u.role = body.role
    _log(db, request, admin, "user.role", u, {"role": body.role})
    db.commit()
    _notify(u, "user.role_changed", {"role": body.role})
    return user_out(db, u)


@router.post("/users/{user_id}/note", response_model=UserOut)
def set_note(
    user_id: int, body: NoteIn, request: Request, admin: AdminUser, db: DB
) -> UserOut:
    u = _get_user(db, user_id)
    u.admin_note = body.note or None
    _log(db, request, admin, "user.note", u)
    db.commit()
    return user_out(db, u)


def _end_all_sessions(db: Session, u: User) -> None:
    u.token_version += 1
    now = datetime.now(UTC)
    for t in db.scalars(
        select(RefreshToken).where(
            RefreshToken.user_id == u.id, RefreshToken.revoked_at.is_(None)
        )
    ):
        t.revoked_at = now


@router.post("/users/{user_id}/logout-all", status_code=status.HTTP_204_NO_CONTENT)
def logout_all(user_id: int, request: Request, admin: AdminUser, db: DB) -> Response:
    u = _get_user(db, user_id)
    _end_all_sessions(db, u)
    _log(db, request, admin, "user.logout_all", u)
    db.commit()
    return Response(status_code=204)


@router.post("/users/{user_id}/keys/rotate", response_model=ApproveResponse)
def rotate_key(
    user_id: int, request: Request, admin: AdminUser, db: DB
) -> ApproveResponse:
    u = _get_user(db, user_id)
    if u.status != "approved":
        raise HTTPException(
            status_code=409, detail={"error": "only an approved account holds a key"}
        )
    row = keys.rotate(db, u)
    _log(db, request, admin, "key.rotate", u, {"prefix": row.prefix})
    db.commit()
    _notify(u, "key.rotated", {"prefix": row.prefix})
    return ApproveResponse(user=user_out(db, u), key=licence_of(row), minted=True)


@router.post("/promote", response_model=UserOut)
def promote(body: PromoteIn, request: Request, admin: AdminUser, db: DB) -> UserOut:
    u = db.scalar(select(User).where(User.email == body.email.lower()))
    if u is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "no account with that email -- they sign up first"},
        )
    u.role = "admin"
    if u.status == "pending":
        u.status = "approved"
        u.approved_at = datetime.now(UTC)
        u.approved_by_id = admin.id
    _log(db, request, admin, "user.promote", u)
    db.commit()
    _notify(u, "user.role_changed", {"role": "admin"})
    return user_out(db, u)


# -------------------------------------------------------------------- keys


@router.get("/keys", response_model=list[KeySummary])
def all_keys(admin: AdminUser, db: DB) -> list[KeySummary]:
    rows = db.execute(
        select(ApiKey, User.email)
        .join(User, User.id == ApiKey.user_id)
        .order_by(ApiKey.id.desc())
    )
    return [key_summary(k, email) for k, email in rows]


@router.post("/keys/{key_id}/revoke", response_model=KeySummary)
def revoke_key(key_id: int, request: Request, admin: AdminUser, db: DB) -> KeySummary:
    k = db.get(ApiKey, key_id)
    if k is None:
        raise HTTPException(status_code=404, detail={"error": "no such key"})
    keys.revoke(db, k)
    _log(db, request, admin, "key.revoke", k.user, {"prefix": k.prefix})
    db.commit()
    _notify(k.user, "key.revoked", {"prefix": k.prefix})
    return key_summary(k, k.user.email)


# ---------------------------------------------------------------- payments


@router.get("/payments", response_model=list[PaymentOut])
def all_payments(admin: AdminUser, db: DB) -> list[PaymentOut]:
    rows = db.scalars(select(Payment).order_by(Payment.id.desc()))
    return [payment_out(p) for p in rows]


# ----------------------------------------------------------------- tickets


@router.get("/tickets", response_model=list[TicketOut])
def all_tickets(admin: AdminUser, db: DB) -> list[TicketOut]:
    staff = staff_ids(db)
    return [
        ticket_out(t, staff)
        for t in db.scalars(select(Ticket).order_by(Ticket.id.desc()))
    ]


def _get_ticket(db: Session, ticket_id: int) -> Ticket:
    t = db.get(Ticket, ticket_id)
    if t is None:
        raise HTTPException(status_code=404, detail={"error": "no such ticket"})
    return t


@router.post("/tickets/{ticket_id}/reply", response_model=TicketOut)
def reply(
    ticket_id: int, body: ReplyIn, request: Request, admin: AdminUser, db: DB
) -> TicketOut:
    t = _get_ticket(db, ticket_id)
    db.add(TicketReply(ticket_id=t.id, author_id=admin.id, body=body.body))
    if t.status == "open":
        t.status = "answered"
    audit.record(
        db,
        actor_id=admin.id,
        action="ticket.reply",
        target_type="ticket",
        target_id=t.id,
        ip=client_ip(request),
    )
    db.commit()
    db.refresh(t)
    if t.user_id:
        broadcaster.publish(
            user_channel(t.user_id), "ticket.replied", {"ticket_id": t.id, "ref": t.ref}
        )
    broadcaster.publish(
        ADMIN_CHANNEL,
        "ticket.replied",
        {"ticket_id": t.id, "ref": t.ref, "by": admin.email},
    )
    return ticket_out(t, staff_ids(db))


@router.post("/tickets/{ticket_id}/close", response_model=TicketOut)
def close(ticket_id: int, request: Request, admin: AdminUser, db: DB) -> TicketOut:
    t = _get_ticket(db, ticket_id)
    t.status = "closed"
    audit.record(
        db,
        actor_id=admin.id,
        action="ticket.close",
        target_type="ticket",
        target_id=t.id,
        ip=client_ip(request),
    )
    db.commit()
    if t.user_id:
        broadcaster.publish(
            user_channel(t.user_id), "ticket.closed", {"ticket_id": t.id, "ref": t.ref}
        )
    broadcaster.publish(
        ADMIN_CHANNEL,
        "ticket.closed",
        {"ticket_id": t.id, "ref": t.ref, "by": admin.email},
    )
    return ticket_out(t, staff_ids(db))


# ---------------------------------------------------------------- waitlist


@router.get("/waitlist", response_model=list[WaitlistOut])
def waitlist(admin: AdminUser, db: DB) -> list[WaitlistOut]:
    return [
        WaitlistOut.model_validate(w)
        for w in db.scalars(select(WaitlistEntry).order_by(WaitlistEntry.id.desc()))
    ]


# ------------------------------------------------------------------- audit


@router.get("/audit", response_model=list[AuditOut])
def audit_log(
    admin: AdminUser,
    db: DB,
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> list[AuditOut]:
    rows = db.execute(
        select(AuditLog, User.email)
        .outerjoin(User, User.id == AuditLog.actor_id)
        .order_by(AuditLog.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return [
        AuditOut(
            id=a.id,
            actor=email,
            action=a.action,
            target_type=a.target_type,
            target_id=a.target_id,
            detail=json.loads(a.detail) if a.detail else None,
            ip=a.ip,
            created_at=a.created_at,
        )
        for a, email in rows
    ]
