"""S3 fake — `POST /api/v1/keys/validate`, all six branches.

The contract is frozen in `plans/team/contracts.md` S3. This stands in for the
real route (Varad, W5D3) so the desktop key flow can be built against it from
W5D1 without waiting.

    uv run uvicorn tests.fixtures.keys_fake:app --port 8001

The branch is selected by the key itself, so every one is reachable on demand
rather than only when the server happens to be in that state. `ti_live_down…`
is the "we couldn't reach the server" case — the one the desktop app must
handle differently from a bad key, which is why `valid: false` is a 200.
"""

from typing import Annotated

from fastapi import FastAPI, Header, HTTPException

app = FastAPI(title="keys_fake (S3)")


def _key(name: str) -> str:
    """`ti_live_` + exactly 32 chars, per the contract."""
    return "ti_live_" + name.ljust(32, "0")


# Annotated because dict is invariant: mypy joins these heterogeneous literals
# to `object` otherwise, and `.get` stops returning a dict.
Answer = dict[str, bool | str | None]

KEYS: dict[str, Answer] = {
    _key("core"): {"valid": True, "tier": "core", "expires_at": None, "reason": None},
    _key("journal"): {"valid": True, "tier": "core_journal", "expires_at": "2026-12-01T00:00:00Z", "reason": None},
    _key("expired"): {"valid": False, "tier": None, "expires_at": None, "reason": "expired"},
    _key("revoked"): {"valid": False, "tier": None, "expires_at": None, "reason": "revoked"},
}
UNKNOWN: Answer = {"valid": False, "tier": None, "expires_at": None, "reason": "unknown"}
DOWN = _key("down")


@app.post("/api/v1/keys/validate")
def validate_key(x_api_key: Annotated[str, Header()]) -> Answer:
    if x_api_key == DOWN:
        # Same shape as the analyze route's 503 — one way of saying "the thing
        # behind me is not answering".
        raise HTTPException(status_code=503, detail={"error": "key service unreachable"})
    return KEYS.get(x_api_key, UNKNOWN)
