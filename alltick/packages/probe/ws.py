"""Subscribe over WebSocket and record what the server pushes.

Free plan: one connection at a time, so the two hosts are probed in sequence.
cmd_id 22004 = subscribe trades, 22002 = subscribe order book, 22000 = heartbeat
(required every ~10s), 22998/22999 = the trade / order-book pushes.
Output: data/ws.json
"""
import asyncio
import json
from pathlib import Path

import websockets
from client import HOST, token, trace

WS = HOST.replace("https://", "wss://")


async def probe(path: str, codes: list[str], seconds: int = 25) -> dict:
    log = {"path": path, "codes": codes, "acks": [], "pushes": 0, "pushed_codes": [],
           "samples": {}, "error": None}
    subs = [{"code": c} for c in codes]
    try:
        async with websockets.connect(f"{WS}/{path}?token={token()}", open_timeout=20) as ws:
            for seq, cmd in ((1, 22004), (2, 22002)):
                await ws.send(json.dumps({"cmd_id": cmd, "seq_id": seq, "trace": trace(),
                                          "data": {"symbol_list": subs}}))
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
                        cmd = msg.get("cmd_id")
                        if cmd in (22998, 22999):
                            log["pushes"] += 1
                            log["samples"].setdefault(str(cmd), msg)
                            code = msg.get("data", {}).get("code")
                            if code and code not in log["pushed_codes"]:
                                log["pushed_codes"].append(code)
                        else:
                            log["acks"].append({"cmd_id": cmd, "ret": msg.get("ret"),
                                                "msg": msg.get("msg")})
            except TimeoutError:
                pass
            beat.cancel()
    # A rejected connection is the finding, not a crash: the free plan allows one
    # socket, and an unauthorised code is refused at the handshake.
    except (websockets.WebSocketException, OSError, TimeoutError) as e:
        log["error"] = f"{type(e).__name__}: {e}"
    return log


async def main() -> None:
    out = [await probe("quote-b-ws-api", ["GOLD", "BTCUSDT", "USOIL"])]
    await asyncio.sleep(5)
    out.append(await probe("quote-stock-b-ws-api", ["700.HK", "TSLA.US"]))
    Path("data/ws.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    for o in out:
        print(o["path"], "pushes:", o["pushes"], "acks:", o["acks"], "err:", o["error"])


if __name__ == "__main__":
    asyncio.run(main())
