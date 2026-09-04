"""Page AllTick candle history backwards into a JSONL file.

One /kline call returns at most 500 candles ending at `kline_timestamp_end`, so
history comes out in pages walked from newest to oldest. The free plan allows one
request per ten seconds and 1,000 per day, which makes a full 1-minute pull a
multi-day job: the run checkpoints after every page and resumes from where it
stopped.

    ALLTICK_TOKEN=... python packages/probe/pull_klines.py --interval 5m --since 2022-06-01

Output is newline-delimited JSON, one candle per line, appended as each page
lands. Nothing is held in memory and an interrupted run loses at most one page.
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import UTC, datetime
from pathlib import Path

from client import FX, STOCK, get

# kline_type codes; the API takes the integer, humans do not.
INTERVALS = {"1m": 1, "5m": 2, "15m": 3, "30m": 4, "1h": 5, "2h": 6, "4h": 7,
             "1d": 8, "1w": 9, "1mo": 10}
PAGE = 500          # documented maximum candles per call
GAP = 11.0          # free plan: 1 request per 10 s, with a second of headroom
BUSY = {429, 605}   # rate limited: back off and retry, never treat as empty
DAILY_CAP = 950     # free plan allows 1,000; leave room for other calls


def stamp(ts: str | int) -> str:
    return datetime.fromtimestamp(int(ts), UTC).strftime("%Y-%m-%d %H:%M")


def page(base: str, code: str, kline_type: int, end: int) -> list[dict]:
    """One call, retried through rate limiting. Raises on anything else."""
    for _ in range(5):
        r = get(base, "kline", {"code": code, "kline_type": kline_type,
                                "kline_timestamp_end": end, "query_kline_num": PAGE,
                                "adjust_type": 0})
        if r.get("ret") == 200:
            return r.get("data", {}).get("kline_list", [])
        if r.get("ret") not in BUSY:
            raise RuntimeError(f"kline failed: ret={r.get('ret')} msg={r.get('msg')}")
        time.sleep(15)
    raise RuntimeError("rate limited five times in a row; stopping rather than hammering")


def cursor_path(out: Path) -> Path:
    return out.with_suffix(out.suffix + ".cursor")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--code", default="GOLD")
    ap.add_argument("--interval", default="5m", choices=sorted(INTERVALS))
    ap.add_argument("--since", default="2022-06-01", help="stop once a page reaches this date")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--max-requests", type=int, default=DAILY_CAP)
    ap.add_argument("--stock", action="store_true", help="use the equities host")
    args = ap.parse_args()

    out = args.out or Path(f"data/klines/{args.code}_{args.interval}.jsonl")
    out.parent.mkdir(parents=True, exist_ok=True)
    cursor = cursor_path(out)
    floor = int(datetime.strptime(args.since, "%Y-%m-%d").replace(tzinfo=UTC).timestamp())

    # Resume from the checkpoint rather than re-walking pages already on disk.
    end = json.loads(cursor.read_text())["end"] if cursor.exists() else 0
    if end:
        print(f"resuming from {stamp(end)}")

    base = STOCK if args.stock else FX
    kline_type = INTERVALS[args.interval]
    total = 0
    for n in range(args.max_requests):
        bars = page(base, args.code, kline_type, end)
        if not bars:
            print(f"page {n}: empty — history exhausted at {stamp(end) if end else 'now'}")
            cursor.unlink(missing_ok=True)
            break

        with out.open("a") as f:
            for b in bars:
                f.write(json.dumps(b, separators=(",", ":")) + "\n")
        total += len(bars)
        oldest = int(bars[0]["timestamp"])
        end = oldest - 1
        cursor.write_text(json.dumps({"end": end}))

        left = args.max_requests - n - 1
        print(f"page {n + 1:5}  {len(bars):4} bars  reached {stamp(oldest)}  "
              f"total {total:7}  {left} requests left  ~{left * GAP / 3600:.1f}h",
              flush=True)

        if oldest <= floor:
            print(f"reached --since {args.since}; done")
            break
        time.sleep(GAP)
    else:
        print(f"\nrequest budget spent. Resume tomorrow with the same command — "
              f"the cursor at {cursor} picks up from {stamp(end)}.")

    print(f"{total} candles appended to {out}")


if __name__ == "__main__":
    main()
