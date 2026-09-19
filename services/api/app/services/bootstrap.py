"""`BOOTSTRAP_ADMIN_EMAIL`: promote one existing account to admin at startup.

For a fresh deployment where nobody can run `app.cli create-admin` against the
database yet. It promotes an account that already exists -- someone signed up
on the site -- and never creates one, so a typo in the setting is a no-op
rather than a password-less admin. The promotion is audited like any other.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User
from app.services import audit

log = logging.getLogger(__name__)


def promote_bootstrap_admin(db: Session, email: str | None) -> User | None:
    """Returns the promoted user, or None when there was nothing to do."""
    if not email:
        return None
    user = db.scalar(select(User).where(User.email == email.lower()))
    if user is None:
        log.warning("BOOTSTRAP_ADMIN_EMAIL=%s: no such account; nothing promoted", email)
        return None
    if user.role == "admin" and user.status == "approved":
        return None
    user.role = "admin"
    user.status = "approved"
    user.approved_at = user.approved_at or datetime.now(UTC)
    audit.record(
        db,
        actor_id=None,
        action="user.bootstrap_admin",
        target_type="user",
        target_id=user.id,
        detail={"email": user.email},
    )
    db.commit()
    log.info("BOOTSTRAP_ADMIN_EMAIL=%s: promoted to admin (id %s)", email, user.id)
    return user
