"""Find which catalog codes this token can actually read.

A code the token cannot access is dropped from the response; a request where
every code is unauthorised comes back ret=604. So batching five at a time (the
free-plan per-request cap) tells us exactly which codes are live.

Caveat: a code can also be missing because the venue has never printed a tick
into the cache, so absence is "no data for this token right now", not proof of
a permission denial. Output: data/entitlements.json
"""
import json
import sys
import time
from pathlib import Path

from client import get

GAP = 11.0
BATCH = 5
BUSY = {429, 605}  # rate limited: retry, never record as a denial
# Small classes are swept whole; the equity books are far too large, so sample.
SAMPLE = {"forex": 59, "metals": 9, "energy": 3, "cfd_index": 30, "index": 10,
          "crypto": 50, "us_stock": 50, "hk_stock": 50, "cn_stock": 50}

catalog = json.loads(Path("data/catalog.json").read_text())
out = {}
for key, cat in catalog.items():
    codes = [i["code"] for i in cat["items"][:SAMPLE[key]]]
    live, dark, unknown, rets = [], [], [], {}
    for i in range(0, len(codes), BATCH):
        chunk = codes[i:i + BATCH]
        for attempt in range(4):
            r = get(cat["base"], "trade-tick", {"symbol_list": [{"code": c} for c in chunk]})
            if r.get("ret") not in BUSY:
                break
            time.sleep(15)
        ret = r.get("ret")
        rets[str(ret)] = rets.get(str(ret), 0) + 1
        if ret in BUSY:
            unknown += chunk
        else:
            got = [t["code"] for t in r.get("data", {}).get("tick_list", [])]
            live += got
            dark += [c for c in chunk if c not in got]
        print(f"{key:9} {i + len(chunk):4}/{len(codes)} ret={ret} live={len(live)}", flush=True)
        time.sleep(GAP)
    out[key] = {"base": cat["base"], "scanned": len(codes), "total_in_catalog": cat["count"],
                "live": live, "no_data": dark, "unknown": unknown, "ret_counts": rets}
    Path("data/entitlements.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))

for key, v in out.items():
    print(f"{key:10} {len(v['live']):4}/{v['scanned']} live", file=sys.stderr)
