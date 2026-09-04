"""Exchange halt/resume feeds. Separate host path, outside the quote APIs.

Output: data/suspension.json
"""
import json
import time
from pathlib import Path

from client import plain

out = {}
for exchange in ("sse", "nyse", "nasdaq"):
    for attempt in range(4):
        d = plain(f"/api/suspension/{exchange}")
        if d.get("ret") != 429:
            break
        time.sleep(15)
    out[exchange] = {"success": d.get("success"), "total": d.get("totalCount"),
                     "ret": d.get("ret"), "msg": d.get("msg"), "sample": d.get("data", [])[:3]}
    print(exchange, out[exchange]["ret"], out[exchange]["success"], out[exchange]["total"], flush=True)
    time.sleep(11)
Path("data/suspension.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
