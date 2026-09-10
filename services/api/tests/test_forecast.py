"""S7 boundary tests — `GET /api/v1/forecast/table`.

Two things are being asserted and they are different jobs. **That the route
answers** is the easy half. **That it refuses to answer wrongly** is the half
worth the file: every check in `app/forecast.py` is exercised by building a
table that fails it and asserting a 503, because a validator that has never
rejected anything is a validator nobody knows is wired up.

The served numbers are checked against `analysis/REACH.md`'s published counts
rather than against themselves — 116 cells and 8,256 rows, which is the same
reconciliation `test_the_apps_fixture_still_says_what_the_table_says` does from
the `signal-data` side. A test that only compares the payload to itself would
pass on an empty table.

Requires `services/api/.env`, same as `test_api.py`. Nothing here touches the
network or the database.
"""

import json

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.forecast import ROW, TableUnavailable, load_table, served_table
from app.main import app

client = TestClient(app)

# `analysis/REACH.md` §2, and `plans/current.md` R6: 116 of 144 cells clear the
# floor and 8,256 of 10,368 rows are served. Transcribed, not recomputed.
PUBLISHED_CELLS = 116
PUBLISHED_ROWS = 8_256


@pytest.fixture
def table_path(tmp_path, monkeypatch):
    """Point the service at a table this test writes, and clear the process cache.

    `served_table` is `lru_cache`d for the life of the process, so a test that
    changed the path without clearing it would read the previous test's table
    and pass for the wrong reason.
    """
    served_table.cache_clear()
    path = tmp_path / "reach_table.json"
    monkeypatch.setattr(settings, "reach_table_path", path)
    yield path
    served_table.cache_clear()


def write(path, **overrides):
    """A minimal well-formed served table, with one thing broken on request."""
    payload = {
        "_row": list(ROW),
        "minSamples": 400,
        "cells": {"(7.0, 10.0]|London|STABLE|1": [[2.0, 1.0, 30, 512, 0.31, 0.33, 0.44, 0.25]]},
    }
    payload.update(overrides)
    path.write_text(json.dumps(payload))
    return payload


# --- the committed table, served ------------------------------------------

def test_the_real_table_is_served():
    served_table.cache_clear()
    r = client.get("/api/v1/forecast/table")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/json")


def test_served_body_is_the_loader_contract():
    """`forecastMock.ts`'s `Fixture` reads `minSamples` and `cells`, and `rowOf`
    reads a row positionally in `_row`'s order. All three have to be there."""
    body = client.get("/api/v1/forecast/table").json()
    assert body["minSamples"] == 400
    assert body["_row"] == list(ROW)
    assert isinstance(body["cells"], dict)


def test_served_counts_match_the_published_result():
    body = client.get("/api/v1/forecast/table").json()
    cells = body["cells"]
    assert len(cells) == PUBLISHED_CELLS
    assert sum(len(rows) for rows in cells.values()) == PUBLISHED_ROWS


def test_every_served_row_clears_the_floor():
    """The fixture's own `_note` claims this. The claim is checked, not read."""
    body = client.get("/api/v1/forecast/table").json()
    n = ROW.index("n")
    assert min(row[n] for rows in body["cells"].values() for row in rows) >= 400


def test_horizons_are_minutes_not_bars():
    """S7 divergence 3 — `m1_sweep.HORIZONS` is (15, 30, 60) minutes against
    5-minute bars, and the draft's `horizonBars: 6` is the unit trap §6.4 names.
    A table serving 6 here would render as 6 minutes and be wrong by 5x."""
    body = client.get("/api/v1/forecast/table").json()
    h = ROW.index("horizonMinutes")
    assert {row[h] for rows in body["cells"].values() for row in rows} == {15, 30, 60}


def test_every_probability_carries_its_band():
    """§S7 rule 2: `p` and `pMax` both, always, and `p` is the floor of the band."""
    body = client.get("/api/v1/forecast/table").json()
    p, p_max = ROW.index("p"), ROW.index("pMax")
    assert all(
        row[p] <= row[p_max] for rows in body["cells"].values() for row in rows
    )


# --- caching ---------------------------------------------------------------

def test_etag_is_returned_and_revalidates():
    served_table.cache_clear()
    first = client.get("/api/v1/forecast/table")
    etag = first.headers["ETag"]

    again = client.get("/api/v1/forecast/table", headers={"If-None-Match": etag})
    assert again.status_code == 304
    assert again.headers["ETag"] == etag
    assert not again.content


def test_stale_etag_gets_the_table():
    r = client.get("/api/v1/forecast/table", headers={"If-None-Match": '"stale"'})
    assert r.status_code == 200
    assert r.json()["minSamples"] == 400


# --- the refusals ----------------------------------------------------------

def test_missing_table_is_503_no_table(table_path):
    r = client.get("/api/v1/forecast/table")
    assert r.status_code == 503
    assert r.json()["detail"]["forecast"] == "no-table"


def test_a_missing_table_is_retried_rather_than_cached(table_path):
    """`lru_cache` does not cache exceptions, and that is load-bearing: putting
    the artefact in place must not need a restart."""
    assert client.get("/api/v1/forecast/table").status_code == 503
    write(table_path)
    assert client.get("/api/v1/forecast/table").status_code == 200


def test_transposed_columns_are_refused(table_path):
    """The check this module exists for. `p` and `pStop` swapped is a wrong
    probability rendered with total confidence — the consumer reads positionally
    and cannot see the header move."""
    swapped = list(ROW)
    swapped[ROW.index("p")], swapped[ROW.index("pStop")] = "pStop", "p"
    write(table_path, _row=swapped)

    r = client.get("/api/v1/forecast/table")
    assert r.status_code == 503
    assert "positionally" in r.json()["detail"]["error"]


def test_a_different_floor_is_refused(table_path):
    write(table_path, minSamples=200)
    assert client.get("/api/v1/forecast/table").status_code == 503


def test_a_thin_row_is_refused(table_path):
    write(table_path, cells={"(7.0, 10.0]|London|STABLE|1": [[2.0, 1.0, 30, 399, 0.3, 0.3, 0.4, 0.3]]})
    r = client.get("/api/v1/forecast/table")
    assert r.status_code == 503
    assert "MIN_SAMPLES" in r.json()["detail"]["error"]


def test_a_present_but_empty_cell_is_refused(table_path):
    """A cell the archive cannot answer is ABSENT. Present-and-empty would read
    as 'answered, with nothing', which is a different claim."""
    write(table_path, cells={"(7.0, 10.0]|London|STABLE|1": []})
    assert client.get("/api/v1/forecast/table").status_code == 503


def test_a_short_row_is_refused(table_path):
    write(table_path, cells={"(7.0, 10.0]|London|STABLE|1": [[2.0, 1.0, 30, 512, 0.31]]})
    assert client.get("/api/v1/forecast/table").status_code == 503


def test_malformed_json_is_refused(table_path):
    table_path.write_text('{"cells": ')
    assert client.get("/api/v1/forecast/table").status_code == 503


def test_load_table_raises_rather_than_returning_a_thinner_answer(table_path):
    """Both failure reasons are one exception on purpose — neither may become a
    number, and `no-table` is a wiring fault rather than a market condition."""
    with pytest.raises(TableUnavailable):
        load_table(table_path)


# --- CORS ------------------------------------------------------------------

@pytest.mark.parametrize(
    "origin",
    [
        # `tauri dev` — the webview loads `devUrl`, so this is an ordinary origin.
        "http://localhost:1420",
        # A packaged app. macOS and Linux serve the frontend over Tauri's custom
        # protocol; Windows uses the http form. Neither carries a port, so
        # neither matched the localhost branch before this route needed them.
        "tauri://localhost",
        "http://tauri.localhost",
    ],
)
def test_cors_allows_the_desktop_origins(origin):
    r = client.get("/api/v1/forecast/table", headers={"Origin": origin})
    assert r.headers["access-control-allow-origin"] == origin


def test_cors_still_rejects_a_foreign_origin():
    """The Tauri entries are exact hosts, not a widened pattern."""
    r = client.get(
        "/api/v1/forecast/table",
        headers={"Origin": "https://tauri.localhost.evil.example.com"},
    )
    assert "access-control-allow-origin" not in r.headers
