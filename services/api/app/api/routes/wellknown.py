from fastapi import APIRouter

from app.core.security import jwks

router = APIRouter(tags=["auth"])


@router.get("/.well-known/jwks.json")
def jwks_document() -> dict:
    """Every public signing key. Anything that needs to verify an access token
    -- a second service, a worker -- reads this instead of sharing a secret."""
    return jwks()
