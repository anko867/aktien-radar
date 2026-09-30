"""Testet die Datenquellen ohne API-Schluessel einmal live und meldet, was wirklich ankommt."""
import io
import json
import sys
import time

import pandas as pd
import requests

UA = {"User-Agent": "Mozilla/5.0 (AktienRadar private research project)"}
results = {}


def check(name, fn):
    t = time.time()
    try:
        out = fn()
        results[name] = ("OK", out, round(time.time() - t, 1))
    except Exception as e:  # noqa: BLE001
        results[name] = ("FEHLER", f"{type(e).__name__}: {str(e)[:200]}", round(time.time() - t, 1))
    status, out, sec = results[name]
    print(f"[{status}] {name} ({sec}s): {out}")
    sys.stdout.flush()


def yahoo():
    import yfinance as yf

    tk = yf.Ticker("AAPL")
    info = tk.info
    keep = {k: info.get(k) for k in [
        "currentPrice", "fiftyTwoWeekHigh", "fiftyTwoWeekLow", "targetMeanPrice", "targetMedianPrice",
        "targetLowPrice", "targetHighPrice", "recommendationMean", "recommendationKey",
        "numberOfAnalystOpinions", "trailingPE", "marketCap", "beta", "freeCashflow", "sector"]}
    hist = tk.history(period="1y")
    keep["history_rows"] = len(hist)
    return keep


def yahoo_extra():
    import yfinance as yf

    tk = yf.Ticker("AAPL")
    out = {}
    try:
        rec = tk.recommendations
        out["recommendations_rows"] = None if rec is None else len(rec)
    except Exception as e:  # noqa: BLE001
        out["recommendations_err"] = str(e)[:100]
    try:
        out["news_items"] = len(tk.news or [])
    except Exception as e:  # noqa: BLE001
        out["news_err"] = str(e)[:100]
    try:
        cal = tk.calendar
        out["calendar"] = {k: str(v) for k, v in (cal or {}).items()}
    except Exception as e:  # noqa: BLE001
        out["calendar_err"] = str(e)[:100]
    try:
        pt = tk.analyst_price_targets
        out["analyst_price_targets"] = pt
    except Exception as e:  # noqa: BLE001
        out["pt_err"] = str(e)[:100]
    return out


def stooq():
    r = requests.get("https://stooq.com/q/d/l/?s=aapl.us&i=d", headers=UA, timeout=20)
    r.raise_for_status()
    txt = r.text
    if "Date" not in txt[:50]:
        return f"Keine CSV erhalten, Antwort beginnt mit: {txt[:120]!r}"
    df = pd.read_csv(io.StringIO(txt))
    return {"rows": len(df), "first": df["Date"].iloc[0], "last": df["Date"].iloc[-1]}


def edgar():
    r = requests.get("https://data.sec.gov/submissions/CIK0000320193.json", headers=UA, timeout=20)
    if r.status_code != 200:
        return f"HTTP {r.status_code}: {r.text[:120]!r}"
    j = r.json()
    return {"name": j.get("name"), "recent_filings": len(j["filings"]["recent"]["form"])}


def frankfurter():
    r = requests.get("https://api.frankfurter.dev/v1/latest?base=USD&symbols=EUR", headers=UA, timeout=20)
    r.raise_for_status()
    return r.json()


def wikipedia():
    r = requests.get("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies", headers=UA, timeout=30)
    r.raise_for_status()
    tables = pd.read_html(io.StringIO(r.text))
    sp = tables[0]
    return {"sp500_rows": len(sp), "columns": list(sp.columns)[:5]}


def wikipedia_others():
    out = {}
    for name, url in {
        "nasdaq100": "https://en.wikipedia.org/wiki/Nasdaq-100",
        "dax": "https://en.wikipedia.org/wiki/DAX",
        "mdax": "https://en.wikipedia.org/wiki/MDAX",
    }.items():
        r = requests.get(url, headers=UA, timeout=30)
        r.raise_for_status()
        tables = pd.read_html(io.StringIO(r.text))
        best = max(tables, key=len)
        out[name] = {"largest_table_rows": len(best), "cols": [str(c) for c in best.columns][:6]}
    return out


def gnews():
    import feedparser

    feed = feedparser.parse("https://news.google.com/rss/search?q=Apple+stock&hl=en-US&gl=US&ceid=US:en")
    return {"entries": len(feed.entries), "first": feed.entries[0].title if feed.entries else None}


def vix():
    import yfinance as yf

    h = yf.Ticker("^VIX").history(period="5d")
    return {"last_close": round(float(h["Close"].iloc[-1]), 2), "date": str(h.index[-1].date())}


for n, f in [
    ("1 Yahoo Finance (info+Verlauf)", yahoo),
    ("1b Yahoo Finance (Empfehlungen, News, Termine)", yahoo_extra),
    ("1c Yahoo Finance (VIX)", vix),
    ("2 Stooq", stooq),
    ("6 SEC EDGAR", edgar),
    ("8 Frankfurter/EZB", frankfurter),
    ("9 Wikipedia S&P 500", wikipedia),
    ("9b Wikipedia Nasdaq-100, DAX, MDAX", wikipedia_others),
    ("10 Google News RSS", gnews),
]:
    check(n, f)

with open("test_sources_result.json", "w", encoding="utf-8") as fh:
    json.dump(results, fh, ensure_ascii=False, indent=2, default=str)
