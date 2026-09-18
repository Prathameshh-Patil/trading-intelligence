import secrets

from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import DB, CurrentUser, MaybeUser
from app.models import Ticket, TicketReply, User
from app.schemas import TicketIn, TicketOut, TicketReplyOut
from app.services.events import ADMIN_CHANNEL, broadcaster

router = APIRouter(prefix="/tickets", tags=["tickets"])


def new_ref(db: Session) -> str:
    while True:
        ref = "VH-" + secrets.token_hex(2).upper()
        if not db.scalar(select(Ticket.id).where(Ticket.ref == ref)):
            return ref


def ticket_out(t: Ticket, staff_ids: set[int]) -> TicketOut:
    return TicketOut(
        id=t.id,
        ref=t.ref,
        email=t.email,
        category=t.category,
        subject=t.subject,
        body=t.body,
        status=t.status,
        created_at=t.created_at,
        replies=[
            TicketReplyOut(
                id=r.id,
                body=r.body,
                created_at=r.created_at,
                from_staff=r.author_id is not None and r.author_id in staff_ids,
            )
            for r in t.replies
        ],
    )


def staff_ids(db: Session) -> set[int]:
    return set(db.scalars(select(User.id).where(User.role == "admin")))


@router.post("", response_model=TicketOut, status_code=201)
def create(body: TicketIn, user: MaybeUser, db: DB) -> TicketOut:
    email = (user.email if user else body.email or "").lower()
    if not email:
        raise HTTPException(
            status_code=422, detail={"error": "an email is needed to reply to"}
        )
    row = Ticket(
        ref=new_ref(db),
        user_id=user.id if user else None,
        email=email,
        category=body.category,
        subject=body.subject,
        body=body.body,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    broadcaster.publish(
        ADMIN_CHANNEL,
        "ticket.created",
        {"ticket_id": row.id, "ref": row.ref, "email": email},
    )
    return ticket_out(row, staff_ids(db))


@router.get("/mine", response_model=list[TicketOut])
def mine(user: CurrentUser, db: DB) -> list[TicketOut]:
    rows = db.scalars(
        select(Ticket)
        .where((Ticket.user_id == user.id) | (Ticket.email == user.email))
        .order_by(Ticket.id.desc())
    )
    staff = staff_ids(db)
    return [ticket_out(t, staff) for t in rows]


__all__ = ["TicketReply", "router", "staff_ids", "ticket_out"]
