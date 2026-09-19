"""Operator commands. `uv run python -m app.cli <command>`.

gen-jwt-key [kid]      print a fresh Ed25519 pair and a Fernet secret, as .env lines
create-admin <email> [--reset]
                       create an admin; prompts for a password. Refuses an
                       existing account unless --reset is given
promote <email>        make an existing account an admin
"""

from __future__ import annotations

import getpass
import json
import sys
from datetime import UTC, datetime


def gen_jwt_key(kid: str | None) -> None:
    from app.core.security import generate_encryption_secret, generate_signing_key

    kid = kid or datetime.now(UTC).strftime("%Y-%m-%d")
    key = generate_signing_key(kid)
    print(f"JWT_ACTIVE_KID={kid}")
    print(f"JWT_KEYS={json.dumps([key])}")
    print(f"KEY_ENCRYPTION_SECRET={generate_encryption_secret()}")


def create_admin(email: str, *, reset: bool = False) -> None:
    from sqlalchemy import select

    from app.core.security import hash_password
    from app.db.session import SessionLocal
    from app.models import User

    email = email.lower()
    with SessionLocal() as db:
        existing = db.scalar(select(User).where(User.email == email))
        if existing is not None and not reset:
            # An existing account's password is not overwritten by accident.
            # `promote` makes them admin without touching it.
            sys.exit(
                f"{email} already exists (id {existing.id}). "
                "Use `promote` to make them admin, or `create-admin --reset` "
                "to set a new password."
            )

    password = getpass.getpass("Password (min 10 chars): ")
    if len(password) < 10:
        sys.exit("password too short")
    if password != getpass.getpass("Again: "):
        sys.exit("passwords differ")

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(email=email, password_hash=hash_password(password))
            db.add(user)
        else:
            user.password_hash = hash_password(password)
        user.role = "admin"
        user.status = "approved"
        user.approved_at = user.approved_at or datetime.now(UTC)
        db.commit()
        print(f"admin ready: {email} (id {user.id})")


def promote(email: str) -> None:
    from sqlalchemy import select

    from app.db.session import SessionLocal
    from app.models import User

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email.lower()))
        if user is None:
            sys.exit("no such account -- they sign up first")
        user.role = "admin"
        if user.status == "pending":
            user.status = "approved"
            user.approved_at = datetime.now(UTC)
        db.commit()
        print(f"promoted: {user.email}")


def main(argv: list[str]) -> None:
    if not argv or argv[0] in {"-h", "--help"}:
        print(__doc__)
        return
    cmd, *rest = argv
    if cmd == "gen-jwt-key":
        gen_jwt_key(rest[0] if rest else None)
    elif cmd == "create-admin" and rest:
        create_admin(rest[0], reset="--reset" in rest[1:])
    elif cmd == "promote" and rest:
        promote(rest[0])
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
