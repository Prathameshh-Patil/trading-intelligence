"""Optional proof of payment, attached to an account for the admin to see.

The proof is a file on disk under `settings.proof_dir`, served back through
`/payments/{id}/proof` to its owner or an admin and to nobody else. It is not a
public static path, so the URL in `PaymentOut.proof_url` needs the bearer
token to fetch -- the clients read it as a blob, not as an `<img src>`.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select

from app.api.dependencies import DB, CurrentUser
from app.config import settings
from app.models import Payment, User
from app.schemas import PaymentOut
from app.services.events import ADMIN_CHANNEL, broadcaster

router = APIRouter(prefix="/payments", tags=["payments"])

MAX_PROOF_BYTES = 8 * 1024 * 1024
ALLOWED = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "application/pdf": ".pdf",
}


def payment_out(p: Payment, email: str | None = None) -> PaymentOut:
    return PaymentOut(
        id=p.id,
        user_id=p.user_id,
        email=email or p.user.email,
        plan=p.plan,
        method=p.method,
        amount=p.amount,
        currency=p.currency,
        reference=p.reference,
        proof_name=p.proof_name,
        proof_url=f"/api/v1/payments/{p.id}/proof",
        status=p.status,
        rejection_reason=p.rejection_reason,
        created_at=p.created_at,
        reviewed_at=p.reviewed_at,
    )


@router.post("", response_model=PaymentOut, status_code=201)
async def submit(
    user: CurrentUser,
    db: DB,
    plan: Annotated[Literal["core", "core_journal"], Form()],
    method: Annotated[Literal["upi", "usdt"], Form()],
    amount: Annotated[int, Form(ge=1)],
    currency: Annotated[Literal["usd", "inr"], Form()],
    reference: Annotated[str, Form(min_length=1, max_length=255)],
    proof: Annotated[UploadFile, File()],
) -> PaymentOut:
    media_type = proof.content_type or ""
    if media_type not in ALLOWED:
        raise HTTPException(
            status_code=415, detail={"error": "proof must be a PNG, JPEG, WebP or PDF"}
        )
    data = await proof.read(MAX_PROOF_BYTES + 1)
    if len(data) > MAX_PROOF_BYTES:
        raise HTTPException(
            status_code=413, detail={"error": "proof must be under 8 MB"}
        )

    folder = Path(settings.proof_dir) / str(user.id)
    folder.mkdir(parents=True, exist_ok=True)
    stored = folder / f"{uuid.uuid4().hex}{ALLOWED[media_type]}"
    stored.write_bytes(data)

    row = Payment(
        user_id=user.id,
        plan=plan,
        method=method,
        amount=amount,
        currency=currency,
        reference=reference,
        proof_name=(proof.filename or "proof")[:255],
        proof_path=str(stored.relative_to(settings.proof_dir)),
        proof_media_type=media_type,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    broadcaster.publish(
        ADMIN_CHANNEL,
        "payment.submitted",
        {"user_id": user.id, "email": user.email, "payment_id": row.id},
    )
    return payment_out(row, user.email)


@router.get("/mine", response_model=list[PaymentOut])
def mine(user: CurrentUser, db: DB) -> list[PaymentOut]:
    rows = db.scalars(
        select(Payment).where(Payment.user_id == user.id).order_by(Payment.id.desc())
    )
    return [payment_out(p, user.email) for p in rows]


@router.get("/{payment_id}/proof")
def proof(payment_id: int, user: CurrentUser, db: DB) -> FileResponse:
    row = db.get(Payment, payment_id)
    if row is None or (row.user_id != user.id and user.role != "admin"):
        # A 404 either way: a non-owner does not learn the id exists.
        raise HTTPException(status_code=404, detail={"error": "no such payment"})
    path = Path(settings.proof_dir) / row.proof_path
    if not path.is_file():
        raise HTTPException(status_code=404, detail={"error": "proof file missing"})
    return FileResponse(
        path,
        media_type=row.proof_media_type,
        headers={"Cache-Control": "private, no-store"},
    )


def owner_email(db, user_id: int) -> str:
    return db.scalar(select(User.email).where(User.id == user_id)) or ""
