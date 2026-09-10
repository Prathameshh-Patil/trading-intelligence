"""S7 · `GET /api/v1/forecast/table` — the served reach table over HTTP.

The `TableLoader` seam `forecastMock.ts` declared, on the server side. The body
is `apps/desktop/public/fixtures/reach_table.json` unchanged, so the client's
swap is `fetch("/fixtures/reach_table.json")` -> `fetch(".../forecast/table")`
and nothing else.

**There is no per-cell lookup endpoint, and that is deliberate.** `reach.reach`
is one lookup convention and `forecastMock` is its one transcription; a second
one behind HTTP is how two files quietly disagree about which bracket a cell can
answer -- the same argument `d78d3c1` made for `first_touch` keeping its
signature, and the same shape as the 41,280 unreconciled numbers that needed a
test written for them. The table goes over the wire once and the lookup stays
where it already is.
"""

from fastapi import APIRouter, HTTPException, Request, Response

from app.forecast import TableUnavailable, served_table

router = APIRouter()

# The table changes only when `reach.py` is rerun and the artefact redeployed,
# so it is cacheable -- but it is the numbers a trader audits, so it revalidates
# every time rather than going stale for a max-age the client cannot see past.
CACHE_CONTROL = "public, max-age=0, must-revalidate"


@router.get("/forecast/table")
def forecast_table(request: Request) -> Response:
    try:
        table = served_table()
    except TableUnavailable as exc:
        # The same shape as `health/db` and `analyze`: one way of saying "the
        # thing behind me is not answering". `forecast.ts` already has a name
        # for what the client does with it -- `no-table`.
        raise HTTPException(
            status_code=503,
            detail={"status": "error", "forecast": "no-table", "error": str(exc)},
        ) from exc

    headers = {"ETag": table.etag, "Cache-Control": CACHE_CONTROL}

    # A browser `fetch` revalidates on its own and hands JS a 200 from cache, so
    # this branch is for a client that sets the header itself. Answering it
    # saves resending ~372 KB to a desktop app that reconnects.
    if request.headers.get("if-none-match") == table.etag:
        return Response(status_code=304, headers=headers)

    # Passed through as the bytes that were checked. Re-encoding a payload this
    # size per request buys nothing, and hashing what is actually sent is what
    # makes the `ETag` mean something.
    return Response(content=table.raw, media_type="application/json", headers=headers)
