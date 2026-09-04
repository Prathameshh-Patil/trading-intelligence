"""Hit every documented REST endpoint once and record what actually comes back.

Free-plan tokens allow 10 requests/minute across all HTTP endpoints, so every
call is spaced by GAP seconds. Output: data/rest.json
"""
import json
import sys
import time
from pathlib import Path

from client import FX, STOCK, get, post

GAP = 11.0
CATALOG = json.loads(Path("data/catalog.json").read_text())
result: dict = {}


def save() -> None:
    Path("data/rest.json").write_text(json.dumps(result, ensure_ascii=False, indent=1))


def step(label: str, fn) -> dict:
    save()  # checkpoint, so a dropped connection mid-sweep does not lose the run
    r = fn()
    print(f"{label:22} ret={r.get('ret')} msg={r.get('msg')}", flush=True)
    time.sleep(GAP)
    return r


def kline(base: str, code: str, kline_type: int, n: int) -> dict:
    return get(base, "kline", {"code": code, "kline_type": kline_type,
                               "kline_timestamp_end": 0, "query_kline_num": n, "adjust_type": 0})


def symbols(base: str, path: str, codes: list[str]) -> dict:
    return get(base, path, {"symbol_list": [{"code": c} for c in codes]})


# 1. Latest trade price, five codes per category (the free-plan per-request cap).
result["trade_tick"] = {}
for key, cat in CATALOG.items():
    codes = [i["code"] for i in cat["items"][:5]]
    r = step(f"trade-tick/{key}", lambda c=cat, k=codes: symbols(c["base"], "trade-tick", k))
    ticks = r.get("data", {}).get("tick_list", [])
    result["trade_tick"][key] = {"base": cat["base"], "requested": codes,
                                 "returned": [t["code"] for t in ticks], "ret": r.get("ret"),
                                 "msg": r.get("msg"), "sample": ticks[:1]}

# 2. Order book depth, one code per category.
result["depth_tick"] = {}
for key, cat in CATALOG.items():
    code = cat["items"][0]["code"]
    r = step(f"depth-tick/{key}", lambda c=cat, k=code: symbols(c["base"], "depth-tick", [k]))
    ticks = r.get("data", {}).get("tick_list", [])
    result["depth_tick"][key] = {"base": cat["base"], "code": code, "ret": r.get("ret"),
                                 "msg": r.get("msg"),
                                 "levels": len(ticks[0]["bids"]) if ticks else 0,
                                 "sample": ticks[:1]}

# 3. Which of the ten kline_type values each host answers.
result["kline_types"] = {}
for base, code in ((FX, "GOLD"), (STOCK, "700.HK")):
    per_base = {}
    for kt in range(1, 11):
        r = step(f"kline/{code}/{kt}", lambda b=base, c=code, k=kt: kline(b, c, k, 3))
        bars = r.get("data", {}).get("kline_list", [])
        per_base[kt] = {"ret": r.get("ret"), "msg": r.get("msg"), "bars": len(bars),
                        "sample": bars[:1]}
    result["kline_types"][code] = {"base": base, "types": per_base}

# 4. How much history one /kline call yields when asking for the documented max.
r = step("kline/GOLD/500d", lambda: kline(FX, "GOLD", 8, 500))
bars = r.get("data", {}).get("kline_list", [])
result["kline_max"] = {"requested": 500, "returned": len(bars), "ret": r.get("ret"),
                       "oldest": bars[0]["timestamp"] if bars else None,
                       "newest": bars[-1]["timestamp"] if bars else None}

# 5. Static/reference data.
result["static_info"] = {}
for base, code in ((FX, "GOLD"), (STOCK, "700.HK"), (STOCK, "AAPL.US")):
    r = step(f"static_info/{code}", lambda b=base, c=code: symbols(b, "static_info", [c]))
    result["static_info"][code] = {"base": base, "ret": r.get("ret"), "msg": r.get("msg"),
                                   "raw": r.get("raw"),
                                   "sample": r.get("data", {}).get("static_info_list", [])[:1]}

# 6. Batch kline (POST, latest two bars per code+type pair).
result["batch_kline"] = {}
for base, code in ((FX, "GOLD"), (STOCK, "700.HK")):
    r = step(f"batch-kline/{code}", lambda b=base, c=code: post(b, "batch-kline", {
        "data_list": [{"code": c, "kline_type": 1, "kline_timestamp_end": 0,
                       "query_kline_num": 2, "adjust_type": 0}]}))
    result["batch_kline"][code] = {"base": base, "ret": r.get("ret"), "msg": r.get("msg"),
                                   "sample": r.get("data", {})}

save()
print("-> data/rest.json", file=sys.stderr)
