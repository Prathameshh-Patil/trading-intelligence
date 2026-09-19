"""Test database and fixtures.

Every test runs inside one outer transaction on a `<db>_test` database that
is rolled back at the end, so tests cannot see each other's rows and the
developer database is never touched. Routes call `db.commit()` freely: with
`join_transaction_mode="create_savepoint"` that commits a savepoint, and the
outer rollback still wins.

The database is created and migrated to head on first use. Postgres has to be
up (`docker compose up -d` at the repo root).
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

# `Settings()` runs at import, so the auth material is set on the instance
# rather than in the environment -- everything reads `settings` at call time.
from app.config import settings
from app.core.security import (
    generate_encryption_secret,
    generate_signing_key,
)

settings.jwt_keys = [generate_signing_key("test")]
settings.jwt_active_kid = "test"
settings.key_encryption_secret = generate_encryption_secret()
settings.proof_dir = Path(tempfile.mkdtemp(prefix="vh-proofs-"))
settings.cors_origins = ["https://visionhub.test", "https://admin.visionhub.test"]

# Point the whole process at the test database before the engine exists.
_MAIN_URL = settings.database_url
_TEST_URL = (
    _MAIN_URL.rsplit("/", 1)[0]
    + "/"
    + _MAIN_URL.rsplit("/", 1)[1].split("?")[0]
    + "_test"
)
settings.database_url = _TEST_URL

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session


def _ensure_test_db() -> None:
    admin = create_engine(_MAIN_URL, isolation_level="AUTOCOMMIT")
    name = _TEST_URL.rsplit("/", 1)[1]
    with admin.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": name}
        ).scalar()
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{name}"'))
    admin.dispose()

    from alembic import command
    from alembic.config import Config

    cfg = Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
    command.upgrade(cfg, "head")


_ensure_test_db()

from fastapi.testclient import TestClient

from app.api import dependencies
from app.api.dependencies import get_db
from app.core.ratelimit import reset_all
from app.core.security import hash_password
from app.db.session import engine
from app.main import app
from app.models import User
from app.services.events import broadcaster

PASSWORD = "correct horse battery"


@pytest.fixture
def db() -> Iterator[Session]:
    connection = engine.connect()
    outer = connection.begin()
    # `autoflush=False`, exactly as `SessionLocal` is built: a test session
    # that flushes for free hides a query that reads stale rows in the real
    # one. `keys.rotate` did just that -- revoke, then look for an active key,
    # and find the one it had just revoked -- and the suite was green.
    session = Session(
        bind=connection, join_transaction_mode="create_savepoint", autoflush=False
    )
    try:
        yield session
    finally:
        session.close()
        outer.rollback()
        connection.close()


@pytest.fixture
def client(db: Session) -> Iterator[TestClient]:
    app.dependency_overrides[get_db] = lambda: db
    # Non-yield sessions (the SSE auth) join the same test transaction.
    original = dependencies.open_session
    dependencies.open_session = lambda: Session(
        bind=db.get_bind(), join_transaction_mode="create_savepoint", autoflush=False
    )
    reset_all()
    broadcaster.recent.clear()
    with TestClient(app, base_url="http://testserver") as c:
        yield c
    app.dependency_overrides.pop(get_db, None)
    dependencies.open_session = original


@pytest.fixture
def make_user(db: Session):
    def _make(
        email: str,
        *,
        role: str = "user",
        status: str = "pending",
        password: str = PASSWORD,
    ) -> User:
        user = User(
            email=email.lower(),
            password_hash=hash_password(password),
            role=role,
            status=status,
        )
        db.add(user)
        db.commit()
        return user

    return _make


@pytest.fixture
def login(client: TestClient):
    def _login(email: str, password: str = PASSWORD) -> str:
        r = client.post(
            "/api/v1/auth/login", json={"email": email, "password": password}
        )
        assert r.status_code == 200, r.text
        return r.json()["access_token"]

    return _login


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin(make_user, login):
    make_user("admin@example.com", role="admin", status="approved")
    return bearer(login("admin@example.com"))


@pytest.fixture
def pending_user(make_user):
    return make_user("trader@example.com")
