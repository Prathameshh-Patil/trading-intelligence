"""Licence key issuance -- S3's key, S5's exit door.

`issue_for` is idempotent on purpose: S5's rule was "webhooks arrive twice;
the handler is idempotent or it issues two keys and bills once", and two
admins with the approval queue open is the same bug in a different hat.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import (
    decrypt_licence_key,
    encrypt_licence_key,
    mint_licence_key,
    sha256_hex,
)
from app.models import ApiKey, User


def active_key(db: Session, user_id: int) -> ApiKey | None:
    return db.scalar(
        select(ApiKey)
        .where(ApiKey.user_id == user_id, ApiKey.status == "active")
        .order_by(ApiKey.id.desc())
    )


def issue_for(db: Session, user: User, tier: str = "core") -> tuple[ApiKey, bool]:
    """Returns `(key_row, minted)`. `minted` is False when an active key already
    existed and was returned instead."""
    existing = active_key(db, user.id)
    if existing:
        return existing, False
    plain = mint_licence_key()
    row = ApiKey(
        user_id=user.id,
        key_hash=sha256_hex(plain),
        key_ciphertext=encrypt_licence_key(plain),
        prefix=plain[:12],
        tier=tier,
    )
    db.add(row)
    db.flush()
    return row, True


def revoke(db: Session, key: ApiKey) -> None:
    if key.status == "active":
        key.status = "revoked"
        key.revoked_at = datetime.now(UTC)


def rotate(db: Session, user: User) -> ApiKey:
    """Revoke whatever is active and mint a replacement in one go."""
    tier = "core"
    current = active_key(db, user.id)
    if current:
        tier = current.tier
        revoke(db, current)
    row, _ = issue_for(db, user, tier)
    return row


def reveal(key: ApiKey) -> str:
    return decrypt_licence_key(key.key_ciphertext)


def lookup(db: Session, plain: str) -> ApiKey | None:
    return db.scalar(select(ApiKey).where(ApiKey.key_hash == sha256_hex(plain)))
