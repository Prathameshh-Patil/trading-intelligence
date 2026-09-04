"""Thin AllTick HTTP client. Returns (ret, parsed_or_raw) with nothing swallowed."""
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

HOST = "https://quote.alltick.co"
FX = "quote-b-api"          # forex, metals, energy, CFD indices, crypto
STOCK = "quote-stock-b-api"  # US / HK / A-share equities and market indices


def token() -> str:
    t = os.environ.get("ALLTICK_TOKEN")
    if not t:
        raise SystemExit("set ALLTICK_TOKEN")
    return t


def trace() -> str:
    return uuid.uuid4().hex[:24]


def _read(req: urllib.request.Request, tries: int = 3) -> dict:
    for attempt in range(tries):
        try:
            body, status = urllib.request.urlopen(req, timeout=30).read().decode(), 200
            break
        except urllib.error.HTTPError as e:
            body, status = e.read().decode(), e.code
            break
        except urllib.error.URLError:  # TLS handshake / connection reset mid-sweep
            if attempt == tries - 1:
                raise
            time.sleep(5)
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        return {"ret": status, "msg": "non-json response", "raw": body[:400]}
    # Rate-limit rejections skip the documented envelope entirely: HTTP 429 with
    # {"error_msg": "Too many requests"} and no ret/msg fields at all.
    if "ret" not in parsed:
        parsed["ret"] = status
        parsed["msg"] = parsed.get("error_msg", "no ret field in response")
    return parsed


def plain(path: str) -> dict:
    """Endpoints outside the quote APIs: token in the query string, no envelope."""
    return _read(urllib.request.Request(f"{HOST}{path}?token={token()}"))


def get(base: str, path: str, data: dict) -> dict:
    query = urllib.parse.quote(json.dumps({"trace": trace(), "data": data}))
    return _read(urllib.request.Request(f"{HOST}/{base}/{path}?token={token()}&query={query}"))


def post(base: str, path: str, data: dict) -> dict:
    body = json.dumps({"trace": trace(), "data": data}).encode()
    return _read(urllib.request.Request(
        f"{HOST}/{base}/{path}?token={token()}", data=body,
        headers={"Content-Type": "application/json"}))
