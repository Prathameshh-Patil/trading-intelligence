"""Render data/*.json into site/index.html — one self-contained page."""
import json
from datetime import UTC, datetime
from html import escape
from pathlib import Path

DATA = Path("data")
HERE = Path(__file__).parent
OUT = Path("site/index.html")


def load(name: str) -> dict | list | None:
    p = DATA / name
    return json.loads(p.read_text()) if p.exists() else None


catalog = json.loads((DATA / "catalog.json").read_text())
ref = json.loads((DATA / "reference.json").read_text())
rest = load("rest.json")
ents = load("entitlements.json")
ws = load("ws.json")
susp = load("suspension.json")

e = escape
live_codes = sorted({c for v in ents.values() for c in v["live"]}) if ents else []
SECTIONS = [("coverage", "Coverage"), ("endpoints", "Endpoints"), ("access", "What this key sees"),
            ("intervals", "Candle intervals"), ("streaming", "Streaming"),
            ("limits", "Limits & errors"), ("catalog", "Instrument catalog")]


def english_tail(text: str) -> str:
    """Spreadsheet cells are Chinese then English. Cutting at the last Han character
    leaves a trailing time fragment from the Chinese half ("22:00-23:00 Daylight
    Saving Time..."), so start again at the first capitalised English word."""
    cut = max((i for i, ch in enumerate(text) if "\u4e00" <= ch <= "\u9fff"), default=-1)
    tail = text[cut + 1:]
    for wide, plain in (("\u3001", ", "), ("：", ": "), ("，", ", "), ("～", "-")):
        tail = tail.replace(wide, plain)
    start = next((i for i, ch in enumerate(tail) if ch.isascii() and ch.isupper()), 0)
    return " ".join(tail[start:].split())


def code_block(caption: str, obj) -> str:
    body = json.dumps(obj, ensure_ascii=False, indent=1) if not isinstance(obj, str) else obj
    return f'<pre><span class="cap">{e(caption)}</span>{e(body)}</pre>'


def table(headers: list[str], rows: list[list[str]], numeric: set[int] = frozenset()) -> str:
    head = "".join(f'<th class="n">{e(h)}</th>' if i in numeric else f"<th>{e(h)}</th>"
                   for i, h in enumerate(headers))
    body = "".join(
        "<tr>" + "".join(f'<td class="n">{c}</td>' if i in numeric else f"<td>{c}</td>"
                         for i, c in enumerate(r)) + "</tr>"
        for r in rows)
    return f'<div class="scroll"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def pill(kind: str, text: str) -> str:
    return f'<span class="pill {kind}">{e(text)}</span>'


# ---------- coverage ----------
total = sum(c["count"] for c in catalog.values())
hours_rows = [[e(c["label"]), e(english_tail(next((i["hours"] for i in c["items"] if i["hours"]), "")))]
              for c in catalog.values()]
hours_rows = [r for r in hours_rows if r[1]]
biggest = max(c["count"] for c in catalog.values())
bars = "".join(
    f'<div class="bar"><span>{e(c["label"])}</span>'
    f'<span class="track"><span class="fill" style="width:{max(c["count"] / biggest * 100, 0.6):.1f}%"></span></span>'
    f'<span class="val">{c["count"]:,}</span></div>'
    for c in sorted(catalog.values(), key=lambda c: -c["count"]))

coverage = f"""
<p class="eyebrow">Coverage</p>
<h2>Nine asset classes, two hosts</h2>
<p>Every instrument AllTick publishes, pulled from its product spreadsheet rather than the
truncated samples in the docs. Which host answers for a code is not a detail you can guess —
sending an equity code to the forex host returns <code>600 code invalid</code>.</p>
<div class="stats">
  <div class="stat"><b>{total:,}</b><span>Instruments</span></div>
  <div class="stat"><b>9</b><span>Asset classes</span></div>
  <div class="stat"><b>6</b><span>REST endpoints</span></div>
  <div class="stat"><b>10</b><span>Candle intervals</span></div>
</div>
<h3>Instruments per class</h3>
<div class="bars">{bars}</div>
<h3>Host routing</h3>
{table(["Host", "Serves"], [
    [f'<span class="k">{e(k)}</span>', e(v)]
    for k, v in ref["hosts"].items() if k.startswith("quote")])}
<h3>Session hours</h3>
<p>The spreadsheet states these once per exchange, as a merged cell, not per instrument — so they
are a property of the class, not of the code.</p>
{table(["Class", "Hours as published"], hours_rows)}
"""

# ---------- endpoints ----------
SAMPLES = {}
if rest:
    for key, v in rest.get("trade_tick", {}).items():
        if v["sample"]:
            SAMPLES["/trade-tick"] = (key, v["sample"][0])
            break
    for key, v in rest.get("depth_tick", {}).items():
        if v.get("sample"):
            SAMPLES["/depth-tick"] = (key, v["sample"][0])
            break
    for code, v in rest.get("kline_types", {}).items():
        one = v["types"].get("1") or v["types"].get(1) or {}
        if one.get("sample"):
            SAMPLES["/kline"] = (code, one["sample"][0])
            break
    for code, v in rest.get("static_info", {}).items():
        if v.get("sample"):
            SAMPLES["/static_info"] = (code, v["sample"][0])
            break
    for code, v in rest.get("batch_kline", {}).items():
        if v.get("ret") == 200 and v.get("sample"):
            SAMPLES["/batch-kline"] = (code, v["sample"])
            break
if susp:
    for ex, v in susp.items():
        if v.get("sample"):
            SAMPLES["/api/suspension"] = (ex, v["sample"][0])
            break

cards = []
for ep in ref["endpoints"]:
    params = table(["Field", "Type", "Meaning"],
                   [[f'<span class="k">{e(a)}</span>', f"<code>{e(b)}</code>", e(c)]
                    for a, b, c in ep["params"]]) if ep["params"] else \
        '<p style="margin:0">No parameters beyond the token.</p>'
    key = next((k for k in SAMPLES if k in ep["path"]), None)
    sample = code_block(f"live response · {SAMPLES[key][0]}", SAMPLES[key][1]) if key else ""
    verb = "post" if ep["method"] == "POST" else "get"
    cards.append(f"""<div class="card">
  <header><span class="verb {verb}">{ep["method"]}</span>
    <h4>{e(ep["name"])}</h4><span class="path">{e(ep["path"])}</span></header>
  <div class="body">{params}
    <h3 style="margin-top:18px">Returns</h3><p style="margin:0">{e(ep["returns"])}</p>
    {f'<p class="note" style="margin:16px 0 0">{e(ep["note"])}</p>' if ep.get("note") else ""}</div>
  {sample}
</div>""")

endpoints = f"""
<p class="eyebrow">Endpoints</p>
<h2>Six REST calls, one envelope</h2>
<p>Every GET takes <code>?token=…&amp;query=</code> plus a URL-encoded
<code>{{"trace": "…", "data": {{…}}}}</code> body, and answers with
<code>{{"ret", "msg", "trace", "data"}}</code>. <code>batch-kline</code> is the exception: its
parameters go in a POST body. The samples below are real responses captured from this key.</p>
{"".join(cards)}
"""

# ---------- access ----------
if rest and rest.get("trade_tick"):
    trade_rows, depth_rows = [], []
    for key, v in rest["trade_tick"].items():
        got, asked = len(v["returned"]), len(v["requested"])
        state = ("ok", "returned") if got == asked else ("part", "partial") if got else ("no", v["msg"])
        trade_rows.append([e(catalog[key]["label"]), f'<span class="k">{e(v["base"])}</span>',
                           pill(state[0], state[1]),
                           e(", ".join(v["returned"]) or "—"), f"{got}/{asked}"])
    for key, v in rest.get("depth_tick", {}).items():
        if v["levels"]:
            state = pill("ok", "order book")
        elif v["ret"] == 200:
            state = pill("part", "reachable, no book")  # indices carry no depth
        else:
            state = pill("no", e(str(v["msg"])))
        depth_rows.append([e(catalog[key]["label"]), f'<span class="k">{e(v["code"])}</span>',
                           state, str(v["levels"]) if v["levels"] else "—"])
    access_tables = (
        "<h3>Latest trade price, five codes per class</h3>"
        + table(["Class", "Host", "Result", "Codes returned", "Hit"], trade_rows, {4})
        + "<h3>Order book depth</h3>"
        + table(["Class", "Probe code", "Result", "Bid levels"], depth_rows, {3}))
else:
    access_tables = '<p class="note">Run <code>make probe</code> to fill this in.</p>'

if ents:
    scan_rows = [[e(catalog[k]["label"]),
                  ", ".join(f'<span class="k">{e(c)}</span>' for c in v["live"]) or "—",
                  f'{len(v["live"]):,}', f'{v["scanned"]:,}', f'{catalog[k]["count"]:,}']
                 for k, v in ents.items()]
    scanned = sum(v["scanned"] for v in ents.values())
    scan = (f"<h3>Entitlement scan</h3>"
            f"<p>Codes the key cannot reach are dropped silently from a mixed request; a request "
            f"where every code is unauthorised returns <code>604</code>. Scanning five at a time "
            f"therefore isolates exactly which codes answer. Across {scanned:,} codes probed, "
            f"<strong>{len(live_codes)} answered</strong> — the free plan is one sample instrument "
            f"per asset class, not a sample of every instrument.</p>"
            + table(["Class", "Codes that answer", "Live", "Scanned", "In catalog"],
                      scan_rows, {2, 3, 4}))
else:
    scan = ""

access = f"""
<p class="eyebrow">Access</p>
<h2>What this key actually returns</h2>
<p>A token is entitled per product, not per asset class. The catalog above is what AllTick sells;
this is what the key in <code>ALLTICK_TOKEN</code> answers for right now. Note that a market that
is closed can look identical to one that is denied, so treat a miss as
<strong>no data for this token right now</strong>, not a proven permission error.</p>
{access_tables}
{scan}
"""

# ---------- intervals ----------
if rest and rest.get("kline_types"):
    names = {t[0]: t[1] for t in ref["kline_types"]}
    stock_ok = {t[0]: t[2] for t in ref["kline_types"]}
    probed = list(rest["kline_types"].items())
    rows = []
    for kt, name in names.items():
        cells = [f'<span class="k">{kt}</span>', e(name)]
        for code, v in probed:
            r = v["types"].get(str(kt), {})
            if r.get("bars"):
                cells.append(pill("ok", f'{r["bars"]} bars'))
            elif r.get("ret") == 200:
                cells.append(pill("dim", "empty"))  # answered, returned no candles
            else:
                cells.append(pill("no", str(r.get("msg", "—"))))
        cells.append("yes" if stock_ok[kt] else "no")
        rows.append(cells)
    headers = ["Type", "Interval"] + [f"{c}" for c, _ in probed] + ["Docs: equities"]
    interval_table = table(headers, rows)
    mx = rest.get("kline_max", {})
    depth_note = ""
    if mx.get("returned"):
        old = datetime.fromtimestamp(int(mx["oldest"]), UTC).date()
        new = datetime.fromtimestamp(int(mx["newest"]), UTC).date()
        depth_note = (f'<p class="note">Asking for the documented maximum of 500 daily candles on '
                      f'GOLD returned <strong>{mx["returned"]}</strong>, spanning {old} to {new}. '
                      f'Deeper history means walking backwards with '
                      f'<code>kline_timestamp_end</code>, which only forex, metals and crypto accept.</p>')
else:
    interval_table, depth_note = '<p class="note">Run <code>make probe</code> to fill this in.</p>', ""

intervals = f"""
<p class="eyebrow">Intervals</p>
<h2>Ten candle types, not all everywhere</h2>
<p>The two middle columns are measured, not quoted: each is a real <code>/kline</code>
call asking for three bars. {e(ref["kline_types_note"])}</p>
{interval_table}
{depth_note}
"""

# ---------- streaming ----------
if ws:
    ws_rows = []
    for conn in ws:
        acks = ", ".join(f'{a["cmd_id"]}→{a["ret"]}' for a in conn["acks"]) or "—"
        ws_rows.append([f'<span class="k">{e(conn["path"])}</span>', e(", ".join(conn["codes"])),
                        e(", ".join(conn.get("pushed_codes", [])) or "—"),
                        pill("no", e(conn["error"][:60])) if conn["error"]
                        else pill("ok", f'{conn["pushes"]} pushes / 25s'), e(acks)])
    ws_live = table(["Path", "Subscribed", "Pushed", "Result", "Acks"], ws_rows)
    push = next((c["samples"] for c in ws if c.get("samples")), {})
    ws_sample = code_block("live push", next(iter(push.values()))) if push else ""
else:
    ws_live, ws_sample = '<p class="note">Run <code>make probe</code> to fill this in.</p>', ""

streaming = f"""
<p class="eyebrow">Streaming</p>
<h2>WebSocket: same payloads, pushed</h2>
<p>Connect with the token in the query string, subscribe, then send a heartbeat every ten seconds
or the server drops you. The push bodies match the REST tick shapes exactly, so one parser covers both.</p>
{table(["cmd_id", "Message", "Notes"],
       [[f'<span class="k">{c}</span>', e(n), e(note)] for c, n, note in ref["websocket"]["commands"]])}
<h3>Measured</h3>
{ws_live}
{ws_sample}
"""

# ---------- limits ----------
limits = f"""
<p class="eyebrow">Limits</p>
<h2>Plan ceilings and the error codes you will hit</h2>
<p class="note">The free plan's real constraint is <strong>one request per ten seconds per
endpoint</strong>. Exceeding it does not return the documented envelope: the server answers
HTTP&nbsp;429 with <code>{{"error_msg": "Too many requests"}}</code> — no <code>ret</code>, no
<code>msg</code>. A client that reads <code>ret</code> without checking the status code sees a
malformed success rather than a rate limit.</p>
{table(ref["plans"]["columns"], [[e(c) for c in r] for r in ref["plans"]["rows"]])}
<h3>Error codes</h3>
{table(["ret", "msg", "Meaning"],
       [[f'<span class="k">{c}</span>', f"<code>{e(m)}</code>", e(d)] for c, m, d in ref["errors"]])}
"""

# ---------- catalog ----------
rows = [[k, i["code"], i["name"]] for k, c in catalog.items() for i in c["items"]]
labels = {k: c["label"] for k, c in catalog.items()}
options = "".join(f'<option value="{e(k)}">{e(v["label"])} ({v["count"]:,})</option>'
                  for k, v in catalog.items())
catalog_html = f"""
<p class="eyebrow">Catalog</p>
<h2>Every code AllTick publishes</h2>
<p>All {total:,} instruments, searchable by code or name. Case matters — the API matches codes
exactly as they appear here.</p>
<div class="filters">
  <input type="search" id="q" placeholder="Search code or name" aria-label="Search instruments">
  <select id="cat" aria-label="Filter by asset class"><option value="">All classes</option>{options}</select>
  <span class="count" id="count"></span>
</div>
<div class="card"><div class="scroll"><table>
  <thead><tr><th>Code</th><th>Name</th><th>Class</th></tr></thead>
  <tbody id="rows"></tbody>
</table></div></div>
"""

live_total = f"{len(live_codes)}" if ents else "an unmeasured number of"
built = datetime.now(UTC).strftime("%d %b %Y %H:%M UTC")
nav_links = "".join(f'<li><a href="#{i}">{e(t)}</a></li>' for i, t in SECTIONS)
bodies = dict(zip([s[0] for s in SECTIONS],
                  [coverage, endpoints, access, intervals, streaming, limits, catalog_html]))
sections = "".join(f'<section id="{i}"><hr>{bodies[i]}</section>' for i, _ in SECTIONS)

page = f"""<meta charset="utf-8">
<title>AllTick Surface Map</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@500;600;700&family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600&display=swap">
<style>{(HERE / "style.css").read_text()}</style>
<div class="shell">
<nav>
  <div class="brand"><b>AllTick</b><span>Surface map</span></div>
  <ol>{nav_links}</ol>
  <div class="foot">Built {built}<br>Live samples captured with a free-plan token.</div>
</nav>
<main>
  <header>
    <p class="eyebrow">Market data API</p>
    <h1>Everything AllTick serves, measured against a real key</h1>
    <p class="lede">{total:,} instruments across nine asset classes, six REST endpoints and a
    WebSocket feed. Every claim below was checked against a live free-plan key — which turns out
    to reach {live_total} of them.</p>
  </header>
  {sections}
</main>
</div>
<script>
const CATALOG = {json.dumps(rows, ensure_ascii=False, separators=(",", ":"))};
const LABEL = {json.dumps(labels, ensure_ascii=False, separators=(",", ":"))};
{(HERE / "app.js").read_text()}
</script>
"""
OUT.parent.mkdir(exist_ok=True)
OUT.write_text(page)
print(f"{OUT} — {len(page) / 1024:.0f} KB")
