"""Aktienliste: S&P 500, Nasdaq-100, DAX, MDAX (Quelle: Wikipedia, MDAX-Kuerzel ueber Yahoo-Suche)."""
import io
import json

import pandas as pd
import requests

from .config import DATA, UA

WIKI = "https://en.wikipedia.org/wiki/"
CACHE_FILE = DATA / "universe.json"
MDAX_FILE = DATA / "mdax_tickers.json"


def _tables(page):
    r = requests.get(WIKI + page, headers=UA, timeout=30)
    r.raise_for_status()
    return pd.read_html(io.StringIO(r.text))


def _yahoo(sym):
    return str(sym).strip().replace(".", "-")  # Yahoo schreibt z. B. BRK-B statt BRK.B


def sp500():
    t = _tables("List_of_S%26P_500_companies")[0]
    return [(_yahoo(r.Symbol), r.Security) for r in t.itertuples()]


def nasdaq100():
    t = _tables("List_of_NASDAQ-100_companies")[0]
    return [(_yahoo(r.Ticker), r.Company) for r in t.itertuples()]


def dax():
    for t in _tables("DAX"):
        cols = [str(c) for c in t.columns]
        if "Ticker" in cols and "Company" in cols and 25 <= len(t) <= 45:
            return [(str(r.Ticker).strip(), r.Company) for r in t.itertuples()]
    raise RuntimeError("DAX-Tabelle nicht gefunden")


def mdax():
    names = None
    for t in _tables("MDAX"):
        cols = [str(c) for c in t.columns]
        if "Name" in cols and 40 <= len(t) <= 60:
            names = [str(n) for n in t["Name"]]
            break
    if not names:
        raise RuntimeError("MDAX-Tabelle nicht gefunden")
    cache = json.loads(MDAX_FILE.read_text(encoding="utf-8")) if MDAX_FILE.exists() else {}
    import yfinance as yf

    out, changed = [], False
    for n in names:
        if n not in cache:
            sym = None
            try:
                for q in yf.Search(n, max_results=8).quotes:
                    if q.get("exchange") == "GER" and str(q.get("symbol", "")).endswith(".DE"):
                        sym = q["symbol"]
                        break
            except Exception:  # noqa: BLE001
                pass
            cache[n] = sym
            changed = True
        if cache[n]:
            out.append((cache[n], n))
    if changed:
        MDAX_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def build():
    """Gibt (universe, meldungen) zurueck. universe: {ticker: {name, indices, region}}."""
    notes, uni = [], {}
    for label, fn in [("S&P 500", sp500), ("Nasdaq-100", nasdaq100), ("DAX", dax), ("MDAX", mdax)]:
        try:
            items = fn()
            notes.append(f"{label}: {len(items)} Aktien von Wikipedia gelesen")
        except Exception as e:  # noqa: BLE001
            notes.append(f"{label}: FEHLER beim Lesen ({type(e).__name__}); nutze zuletzt gespeicherte Liste")
            items = []
            if CACHE_FILE.exists():
                old = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
                items = [(t, v["name"]) for t, v in old.items() if label in v["indices"]]
        for tk, name in items:
            d = uni.setdefault(tk, {"name": name, "indices": [], "region": "US" if "." not in tk else "EU"})
            d["indices"].append(label)
    if len(uni) > 300:
        CACHE_FILE.write_text(json.dumps(uni, ensure_ascii=False, indent=1), encoding="utf-8")
    return uni, notes
