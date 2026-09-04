"""Turn AllTick's published product spreadsheet into data/catalog.json.

The spreadsheet is the only authoritative list of instrument codes; the GitHub
docs only ship a truncated sample of each tab.
"""
import json
import sys
import urllib.request
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

SHEET = "1avkeR1heZSj6gXIkDeBt8X3nv4EzJetw4yFuKjSDYtA"
XLSX = f"https://docs.google.com/spreadsheets/d/{SHEET}/export?format=xlsx"
NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
RNS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"

# tab name -> (key, english label, which of the two API hosts serves it)
TABS = {
    "外汇code（FX code）": ("forex", "Forex", "quote-b-api"),
    "贵金属code（Metals code）": ("metals", "Precious Metals", "quote-b-api"),
    "能源code（Energy code）": ("energy", "Energy", "quote-b-api"),
    "指数（ index）": ("cfd_index", "CFD Indices", "quote-b-api"),
    "加密货币code（crypto code）": ("crypto", "Cryptocurrency", "quote-b-api"),
    "美股code（US stocks code）": ("us_stock", "US Stocks", "quote-stock-b-api"),
    "港股code（HK stocks code）": ("hk_stock", "HK Stocks", "quote-stock-b-api"),
    "大盘指数（Index）": ("index", "Market Indices", "quote-stock-b-api"),
    "A股code（China stocks code）": ("cn_stock", "China A-Shares", "quote-stock-b-api"),
}


def sheet_rows(z: zipfile.ZipFile) -> dict[str, list[list[str]]]:
    strings = [
        "".join(t.text or "" for t in si.iter(NS + "t"))
        for si in ET.fromstring(z.read("xl/sharedStrings.xml"))
    ]
    rels = {r.get("Id"): r.get("Target") for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))}
    out = {}
    for sh in ET.fromstring(z.read("xl/workbook.xml")).iter(NS + "sheet"):
        target = rels[sh.get(RNS + "id")].lstrip("/")
        if not target.startswith("xl/"):
            target = "xl/" + target
        rows = []
        for r in ET.fromstring(z.read(target)).iter(NS + "row"):
            cells = []
            for c in r.iter(NS + "c"):
                v = c.find(NS + "v")
                text = "" if v is None else (strings[int(v.text)] if c.get("t") == "s" else v.text)
                cells.append((text or "").strip())
            while cells and not cells[-1]:
                cells.pop()
            if cells:
                rows.append(cells)
        out[sh.get("name")] = rows
    return out


def flat(cell: str) -> str:
    return cell.replace("\n", " ").strip()


def code_index(row: list[str]) -> int | None:
    """Product codes are the only short, space-free ASCII cells in a row."""
    for i, c in enumerate(row):
        head = c.split("\n")[0].strip()
        if head and head.isascii() and " " not in head and len(head) <= 12:
            return i
    return None


def parse(rows: list[list[str]]) -> list[dict[str, str]]:
    """Tabs share a preamble banner and a header row but not a column layout: the
    crypto tab has no Name column, the KRW block has no Category column, and the
    banner repeats as the last row of several sheets. Only Hours and Category are
    read positionally; the code is found by shape so a shifted block still parses."""
    cols: dict[str, int] = {}
    items = []
    for r in rows:
        lower = [c.lower() for c in r]
        if not cols:
            if "code" not in lower:
                continue
            for i, c in enumerate(lower):
                for key, prefix in (("code", "code"), ("name", "name"),
                                    ("hours", "transaction hour"), ("group", "category")):
                    if c.startswith(prefix):
                        cols.setdefault(key, i)
            if "分类" in r:
                cols.setdefault("group", r.index("分类"))
            continue

        i = code_index(r)
        if i is None:
            continue

        # A code cell may append a note on a second line ("inactive, use for FX rate").
        named = "name" in cols and i + 1 < len(r) and cols.get("hours") != i + 1
        items.append({
            "code": r[i].split("\n")[0].strip(),
            "name": flat(r[i + 1]) if named else "",
            "hours": flat(r[cols["hours"]]) if len(r) > cols.get("hours", 99) else "",
            "group": flat(r[cols["group"]]) if len(r) > cols.get("group", 99) else "",
        })
    return items


def main() -> None:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "data/catalog.json")
    xlsx = out.parent / "product_list.xlsx"
    out.parent.mkdir(parents=True, exist_ok=True)
    if not xlsx.exists():
        xlsx.write_bytes(urllib.request.urlopen(XLSX, timeout=120).read())
    rows = sheet_rows(zipfile.ZipFile(xlsx))
    catalog = {}
    for tab, (key, label, base) in TABS.items():
        items = parse(rows[tab])
        catalog[key] = {"label": label, "base": base, "count": len(items), "items": items}
        print(f"{key:10} {label:18} {len(items):5}")
    out.write_text(json.dumps(catalog, ensure_ascii=False, indent=1))
    print("total", sum(v["count"] for v in catalog.values()), "->", out)


if __name__ == "__main__":
    main()
