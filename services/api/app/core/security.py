"""Passwords, access tokens, refresh tokens, and licence keys at rest.

One module so the four secrets this service handles are hashed, signed and
encrypted in one place, with the reasoning next to the code:

- **Passwords** are argon2id. `verify` is constant-time and `DUMMY_HASH` lets a
  login against an unknown email spend the same time as one against a known
  email, so the response time does not say which emails exist.
- **Access tokens** are 15-minute JWTs signed with Ed25519. Asymmetric so a
  second service can verify with the public key alone (`/.well-known/jwks.json`)
  and the private key never leaves this process. `kid` in the header is what
  makes rotation a config change rather than a deploy.
- **Refresh tokens** are opaque 256-bit random strings. Only their sha256 is
  stored, so a database read does not yield a usable token.
- **Licence keys** are stored twice: sha256 for lookup on `/keys/validate`, and
  Fernet ciphertext so `/keys/mine` can show the user their own key again.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from app.config import settings

# ---------------------------------------------------------------- passwords

# RFC 9106's second recommended profile: 64 MiB, 3 passes, 4 lanes. The first
# (2 GiB) is for servers with memory to spare; this one is not.
_hasher = PasswordHasher(time_cost=3, memory_cost=64 * 1024, parallelism=4)

# Hashed once at import so the unknown-email path runs a real verify.
DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(32))


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


# ------------------------------------------------------------ access tokens

Role = Literal["user", "admin"]
Status = Literal["pending", "approved", "rejected", "suspended"]


class TokenError(Exception):
    """Any reason an access token is not accepted. The message is for logs,
    never for the response -- the client gets one 401 whatever the cause."""


def _load_private(pem: str) -> Ed25519PrivateKey:
    key = serialization.load_pem_private_key(pem.encode(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise TokenError("JWT private key is not Ed25519")
    return key


def _load_public(pem: str) -> Ed25519PublicKey:
    key = serialization.load_pem_public_key(pem.encode())
    if not isinstance(key, Ed25519PublicKey):
        raise TokenError("JWT public key is not Ed25519")
    return key


def _keyring() -> dict[str, dict[str, str | None]]:
    return {str(k["kid"]): k for k in settings.jwt_keys if k.get("kid")}


def active_signing_key() -> tuple[str, Ed25519PrivateKey]:
    entry = _keyring().get(settings.jwt_active_kid)
    if not entry or not entry.get("private_pem"):
        raise TokenError("no active JWT signing key configured")
    return settings.jwt_active_kid, _load_private(str(entry["private_pem"]))


def public_key_for(kid: str) -> Ed25519PublicKey:
    entry = _keyring().get(kid)
    if not entry or not entry.get("public_pem"):
        raise TokenError(f"unknown kid {kid!r}")
    return _load_public(str(entry["public_pem"]))


def mint_access_token(
    *,
    user_id: int,
    role: str,
    status: str,
    token_version: int,
    now: datetime | None = None,
) -> tuple[str, int]:
    """Returns `(token, expires_in_seconds)`."""
    kid, key = active_signing_key()
    now = now or datetime.now(UTC)
    claims = {
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=settings.access_ttl_seconds)).timestamp()),
        "jti": uuid.uuid4().hex,
        "role": role,
        "status": status,
        "tv": token_version,
    }
    token = jwt.encode(claims, key, algorithm="EdDSA", headers={"kid": kid})
    return token, settings.access_ttl_seconds


def verify_access_token(token: str) -> dict[str, Any]:
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as exc:
        raise TokenError(f"bad header: {exc}") from exc
    kid = header.get("kid")
    if not isinstance(kid, str):
        raise TokenError("missing kid")
    try:
        return jwt.decode(
            token,
            public_key_for(kid),
            algorithms=["EdDSA"],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
            leeway=30,
            options={"require": ["exp", "iat", "sub", "jti", "aud", "iss"]},
        )
    except jwt.PyJWTError as exc:
        raise TokenError(str(exc)) from exc


def jwks() -> dict[str, Any]:
    """Every public key in the ring, as RFC 8037 OKP JWKs."""
    keys = []
    for kid, entry in _keyring().items():
        if not entry.get("public_pem"):
            continue
        raw = _load_public(str(entry["public_pem"])).public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        keys.append(
            {
                "kty": "OKP",
                "crv": "Ed25519",
                "kid": kid,
                "use": "sig",
                "alg": "EdDSA",
                "x": base64.urlsafe_b64encode(raw).rstrip(b"=").decode(),
            }
        )
    return {"keys": keys}


def generate_signing_key(kid: str) -> dict[str, str]:
    """A fresh Ed25519 pair, in the shape `JWT_KEYS` takes."""
    private = Ed25519PrivateKey.generate()
    return {
        "kid": kid,
        "private_pem": private.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ).decode(),
        "public_pem": private.public_key()
        .public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
        .decode(),
    }


# ----------------------------------------------------------- refresh tokens


def new_refresh_token() -> str:
    return secrets.token_urlsafe(32)


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


# ------------------------------------------------------------ licence keys

_KEY_ALPHABET = "abcdefghijklmnopqrstuvwxyz0123456789"
KEY_PREFIX = "vh_live_"
KEY_BODY_LEN = 32


def mint_licence_key() -> str:
    """`vh_live_` + exactly 32 lowercase alphanumerics -- contracts.md S3."""
    return KEY_PREFIX + "".join(
        secrets.choice(_KEY_ALPHABET) for _ in range(KEY_BODY_LEN)
    )


def _fernet() -> Fernet:
    if not settings.key_encryption_secret:
        raise RuntimeError("KEY_ENCRYPTION_SECRET is not set")
    return Fernet(settings.key_encryption_secret.encode())


def encrypt_licence_key(key: str) -> str:
    return _fernet().encrypt(key.encode()).decode()


def decrypt_licence_key(ciphertext: str) -> str:
    try:
        return _fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise RuntimeError(
            "licence key ciphertext does not decrypt under this secret"
        ) from exc


def generate_encryption_secret() -> str:
    return Fernet.generate_key().decode()
