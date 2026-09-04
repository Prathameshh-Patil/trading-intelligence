"""Measure exactly what depth granularity AllTick gives for GOLD.

L1 / L2 / MBP / MBO is decided by what the order-book push contains, and whether
trades carry a usable aggressor side. Both are measured over a live window
rather than read off the docs. Output: data/gold.json
"""
import asyncio
import json
import statistics
import sys
from collections import Counter
from itertools import pairwise
from pathlib import Path

import websockets
from client import FX, HOST, get, token, trace

SECONDS = int(sys.argv[1]) if len(sys.argv) > 1 else 90
CODE = "GOLD"


async def capture(seconds: int) -> dict:
    url = f"{HOST.replace('https://', 'wss://')}/quote-b-ws-api?token={token()}"
    book_levels, spreads, book_seq, book_times = Counter(), [], [], []
    trades, sides, volumes, trade_times, prices, directions = 0, Counter(), [], [], [], []
    first_book = None
    async with websockets.connect(url, open_timeout=20) as ws:
        for seq, cmd in ((1, 22004), (2, 22002)):
            await ws.send(json.dumps({"cmd_id": cmd, "seq_id": seq, "trace": trace(),
                                      "data": {"symbol_list": [{"code": CODE}]}}))
            await asyncio.sleep(1)

        async def heartbeat():
            while True:
                await asyncio.sleep(10)
                await ws.send(json.dumps({"cmd_id": 22000, "seq_id": 99, "trace": trace(),
                                          "data": {}}))

        beat = asyncio.create_task(heartbeat())
        try:
            async with asyncio.timeout(seconds):
                async for raw in ws:
                    msg = json.loads(raw)
                    d = msg.get("data", {})
                    if d.get("code") != CODE:
                        continue
                    if msg.get("cmd_id") == 22999:
                        book_levels[(len(d["bids"]), len(d["asks"]))] += 1
                        spreads.append(float(d["asks"][0]["price"]) - float(d["bids"][0]["price"]))
                        book_seq.append(int(d["seq"]))
                        book_times.append(int(d["tick_time"]))
                        first_book = first_book or d
                    elif msg.get("cmd_id") == 22998:
                        trades += 1
                        sides[d.get("trade_direction")] += 1
                        directions.append(d.get("trade_direction"))
                        volumes.append(float(d["volume"]))
                        prices.append(float(d["price"]))
                        trade_times.append(int(d["tick_time"]))
        except TimeoutError:
            pass
        beat.cancel()

    def rate(times: list[int]) -> float | None:
        span = (max(times) - min(times)) / 1000 if len(times) > 1 else 0
        return round(len(times) / span, 2) if span else None

    return {
        "window_seconds": seconds,
        "book_updates": sum(book_levels.values()),
        "book_levels_seen": {f"{b}x{a}": n for (b, a), n in book_levels.items()},
        "book_updates_per_second": rate(book_times),
        "spread_min": min(spreads, default=None),
        "spread_median": round(statistics.median(spreads), 4) if spreads else None,
        "spread_max": max(spreads, default=None),
        "book_seq_is_timestamp": bool(book_seq) and all(s > 1_700_000_000_000 for s in book_seq),
        "first_book": first_book,
        "trades": trades,
        "trades_per_second": rate(trade_times),
        "trade_direction_counts": {str(k): v for k, v in sides.items()},
        "trade_volume_distinct": sorted(set(volumes))[:20],
        "trade_time_ms_resolution": sorted({t % 1000 for t in trade_times})[:10],
        # If trade_direction were a real aggressor side it would flip when price falls.
        # A transition prices[i] -> prices[i+1] is attributed to directions[i+1].
        "price_ticks_up": sum(1 for a, b in pairwise(prices) if b > a),
        "price_ticks_down": sum(1 for a, b in pairwise(prices) if b < a),
        "price_ticks_flat": sum(1 for a, b in pairwise(prices) if b == a),
        "direction_on_down_ticks": dict(Counter(
            nxt for (a, b), (_, nxt) in zip(pairwise(prices), pairwise(directions), strict=True)
            if b < a)),
        "direction_on_up_ticks": dict(Counter(
            nxt for (a, b), (_, nxt) in zip(pairwise(prices), pairwise(directions), strict=True)
            if b > a)),
    }


def seq_of(r: dict) -> tuple[int, int] | None:
    ticks = r.get("data", {}).get("tick_list", [])
    return (int(ticks[0]["seq"]), int(ticks[0]["tick_time"])) if ticks else None


async def main() -> None:
    depth = get(FX, "depth-tick", {"symbol_list": [{"code": CODE}]})
    await asyncio.sleep(11)
    before = seq_of(get(FX, "trade-tick", {"symbol_list": [{"code": CODE}]}))
    stream = await capture(SECONDS)
    await asyncio.sleep(11)
    after = seq_of(get(FX, "trade-tick", {"symbol_list": [{"code": CODE}]}))
    # seq is a venue-side counter: its slope is the real tick rate behind the feed.
    upstream = None
    if before and after and after[1] > before[1]:
        upstream = round((after[0] - before[0]) / ((after[1] - before[1]) / 1000), 1)
    out = {"rest_depth": depth, "seq_before": before, "seq_after": after,
           "upstream_ticks_per_second": upstream, "stream": stream}
    Path("data/gold.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    s = out["stream"]
    print("upstream ticks/s:", out["upstream_ticks_per_second"])
    print(json.dumps({k: v for k, v in s.items() if k != "first_book"}, indent=1))


if __name__ == "__main__":
    asyncio.run(main())
