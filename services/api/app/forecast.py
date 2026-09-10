"""S7 · the served reach table, as `services/api` hands it over.

`plans/team/contracts.md` §S7, frozen 2026-09-10, ends on the sentence this
module exists to act on: *"there is no real implementation and no `services/api`
route. Writing those fills slots this contract already specifies and is not a
contract change."* This is the route's half of that.

WHAT IT SERVES, AND WHAT IT DELIBERATELY DOES NOT.

`reach.py` has two public functions and only one of them can be honest today.
`reach()` is a lookup -- a key and a horizon in, the brackets the archive can
answer out -- and needs nothing but the table. `cell_of()` turns a bar into that
key, which needs `atr_bp` and `rv_slope`, which needs a live feed, which does
not exist (`plans/current.md` row C1, reopened 5 Sep). **So this serves the
table and does not form the key.** That is not a shortcut; it is where
`forecastMock.ts` already says the line falls -- *"Once `engine/real.ts` exists
this file's only job disappears: the key comes from the bars and the lookup is
unchanged."* Serving a key from here would mean inventing `atr_bp`, and a made-up
bucket wearing a real probability is the failure mode §S7 rule 1 is written
against.

THE SEAM WAS DECLARED BEFORE THIS FILE, so this is transcription, not design.
`forecastMock.ts` exports

    export type TableLoader = () => Promise<Fixture>;

and says why in its own words: *"the real implementation will load this from
`services/api` rather than a fixture. A seam that only exists for tests tends to
rot; this one is on the path."* The route therefore answers in the `Fixture`
shape byte for byte, and the client swaps one function rather than a file.

THE COLUMN ORDER IS CHECKED ON LOAD, AND THAT CHECK IS THE POINT OF THIS FILE.
`forecastMock.rowOf` reads a row **positionally** -- `r[4]` is `p`, `r[6]` is
`pStop`. A table regenerated with two columns transposed is a wrong probability
rendered with complete confidence, invisible from both ends: the API has no
opinion about what it is passing through and the UI has no way to know the
column moved. The fixture declares its own order in `_row`, so it is checked
against the order the consumer reads, and a mismatch refuses to serve rather
than serving something plausible. Same class as `DELTA_CVD_FINDINGS.md`'s
inverted side and the `horizonBars`/`horizonMinutes` divergence: right in
isolation, wrong in composition.

ONE ARTEFACT, TWO READERS, AND STILL NO GENERATOR. The table served here is
`apps/desktop/public/fixtures/reach_table.json` -- the same file the desktop app
fetches, hand-produced from `services/signal-data/analysis/reach_table.csv` with
no script in between. Nothing is copied here and no third copy is made: this
service reads the one committed artefact, so `test_the_apps_fixture_still_says_
what_the_table_says` (Varad, 10 Sep) covers what this serves for free. **Two
things are still owed and neither is invented here:** the generator
(`export_fixture_json.py` is the precedent), and a neutral home for the file --
a service reaching into an app's `public/` directory is the right dependency
pointing the wrong way, and it should invert once the generator writes it.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.config import settings

# `forecastMock.ts`'s `FixtureRow`, field for field AND IN THIS ORDER. The
# consumer reads these positionally -- see the module docstring.
ROW: tuple[str, ...] = (
    "targetAtr",
    "stopAtr",
    "horizonMinutes",
    "n",
    "p",
    "pMax",
    "pStop",
    "pNeither",
)

_N = ROW.index("n")

# `reach.MIN_SAMPLES`, derived rather than picked in `strategy-precommit.md` §3.
# NOT re-applied here: the thin rows were dropped when the table was generated,
# so absence is the floor already having been applied, and re-gating would be a
# second copy of a threshold. It is checked so that a table built under a
# different floor cannot be served under this one's label.
MIN_SAMPLES = 400


class TableUnavailable(RuntimeError):
    """No served table, or one this service refuses to serve.

    Deliberately one exception for both. They reach the client as `no-table`,
    which `forecast.ts` calls *"a wiring fault, not a market condition"* -- and
    a table that fails its shape check is exactly that, not a thinner answer.
    Nothing downstream may turn either into a number.
    """


@dataclass(frozen=True)
class ServedTable:
    """The checked table, kept as the bytes that were checked.

    `raw` rather than the parsed object because the payload is ~372 KB and
    FastAPI would otherwise re-serialise it on every request to produce the
    identical bytes. Keeping them also means the `ETag` is a hash of what is
    actually sent.
    """

    raw: bytes
    etag: str
    cells: int
    rows: int


def _validate(payload: object, path: Path) -> tuple[int, int]:
    """Refuse anything the consumer would read wrongly. Returns (cells, rows)."""
    if not isinstance(payload, dict):
        raise TableUnavailable(f"{path}: expected a JSON object, got {type(payload).__name__}")

    declared = payload.get("_row")
    if declared != list(ROW):
        raise TableUnavailable(
            f"{path}: declares column order {declared!r}, but the consumer reads "
            f"{list(ROW)!r} positionally. Refusing to serve -- a moved column is a "
            "wrong probability with nothing on either side to notice it."
        )

    floor = payload.get("minSamples")
    if floor != MIN_SAMPLES:
        raise TableUnavailable(
            f"{path}: built under minSamples={floor!r}; this service serves {MIN_SAMPLES}"
        )

    cells = payload.get("cells")
    if not isinstance(cells, dict) or not cells:
        raise TableUnavailable(f"{path}: no `cells`")

    rows = 0
    for key, got in cells.items():
        if not isinstance(got, list) or not got:
            # A cell the archive cannot answer is ABSENT, never present and
            # empty. An empty list would read as "answered, with nothing".
            raise TableUnavailable(f"{path}: cell {key!r} is present but carries no rows")
        for row in got:
            if not isinstance(row, list) or len(row) != len(ROW):
                raise TableUnavailable(
                    f"{path}: cell {key!r} has a row of width "
                    f"{len(row) if isinstance(row, list) else '?'}, expected {len(ROW)}"
                )
            if not isinstance(row[_N], (int, float)) or row[_N] < MIN_SAMPLES:
                raise TableUnavailable(
                    f"{path}: cell {key!r} carries a row with n={row[_N]!r}, below "
                    f"MIN_SAMPLES={MIN_SAMPLES}. Every served row clears the floor."
                )
        rows += len(got)

    return len(cells), rows


def load_table(path: Path) -> ServedTable:
    """Read and check the served table, or raise `TableUnavailable`."""
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise TableUnavailable(f"{path}: {exc.strerror or exc}") from exc

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise TableUnavailable(f"{path}: not JSON -- {exc}") from exc

    cells, rows = _validate(payload, path)
    return ServedTable(
        raw=raw,
        etag=f'"{hashlib.sha256(raw).hexdigest()[:32]}"',
        cells=cells,
        rows=rows,
    )


@lru_cache(maxsize=1)
def served_table() -> ServedTable:
    """The table, read and checked once per process.

    `lru_cache` does not cache exceptions, which is the behaviour wanted rather
    than a detail tolerated: a table that is missing at boot is retried on the
    next request, so putting the file in place does not need a restart. A table
    that loaded stays loaded -- rebuilding it is a deploy, not a market event.
    """
    return load_table(settings.reach_table_path)
