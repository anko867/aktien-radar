"""Datenabruf: Kurse, Analystendaten, Nachrichten, Wechselkurs, SEC-Insidermeldungen."""
import datetime as dt
import os
import re
import time
import urllib.parse
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor

import feedparser
import pandas as pd
import requests
import yfinance as yf

from .config import CACHE, UA

FIELDS = ["Open", "High", "Low", "Close", "Volume"]


# ---------------------------------------------------------------- Kurse
def download_prices(tickers, period="6y", chunk=100, use_cache=False):
    """Tageskurse (bereinigt um Splits/Dividenden). Gibt {feld: DataFrame[datum x ticker]} zurueck."""
    cache_file = CACHE / f"prices_{period}.pkl"
    if use_cache and cache_file.exists():
        return pd.read_pickle(cache_file)
    frames = []
    for i in range(0, len(tickers), chunk):
        part = tickers[i:i + chunk]
        for attempt in range(3):
            try:
                df = yf.download(part, period=period, interval="1d", auto_adjust=True, group_by="column",
                                 threads=True, progress=False)
                break
            except Exception:  # noqa: BLE001
                time.sleep(3 * (attempt + 1))
                df = None
        if df is None or df.empty:
            continue
        if not isinstance(df.columns, pd.MultiIndex):
            df.columns = pd.MultiIndex.from_product([df.columns, part[:1]])
        frames.append(df)
    wide = pd.concat(frames, axis=1)
    wide = wide.loc[:, ~wide.columns.duplicated()]
    if wide.index.tz is not None:
        wide.index = wide.index.tz_localize(None)
    out = {f: wide[f].copy() for f in FIELDS}
    out["Close"] = out["Close"].dropna(axis=1, how="all")
    for f in FIELDS:
        out[f] = out[f].reindex(columns=out["Close"].columns)
    pd.to_pickle(out, cache_file)
    return out


def last_complete_date(index, now=None):
    """Letzter abgeschlossener US-Handelstag (Schluss 16:00 New York, plus 1,5 Stunden Puffer)."""
    now = now or pd.Timestamp.now(tz="America/New_York")
    cutoff = now.normalize().tz_localize(None)
    if now.hour + now.minute / 60 < 17.5:
        cutoff -= pd.Timedelta(days=1)
    idx = index.tz_localize(None) if index.tz is not None else index
    return idx[idx <= cutoff][-1]


def clean(prices):
    """Feiertage einzelner Laender erzeugen Luecken (NaN) in der gemeinsamen Zeitachse. Kurz aufgefuellt mit dem
    letzten Schlusskurs (flacher Tag, Umsatz 0), sonst waeren alle gleitenden Durchschnitte leer."""
    c = prices["Close"]
    gap = c.isna()
    c2 = c.ffill(limit=3)
    out = {"Close": c2, "Volume": prices["Volume"].where(~gap, 0)}
    for f in ("Open", "High", "Low"):
        out[f] = prices[f].where(~gap, c2)
    return out


def trim_to_asof(prices):
    asof = last_complete_date(prices["Close"].index)
    return clean({k: v.loc[:asof] for k, v in prices.items()}), asof


# ---------------------------------------------------------------- Yahoo: Kennzahlen/Analysten
INFO_KEYS = [
    "currency", "shortName", "longName", "sector", "industry", "country", "fullTimeEmployees", "website",
    "longBusinessSummary", "marketCap", "trailingPE", "forwardPE", "beta", "freeCashflow", "totalDebt",
    "totalCash", "debtToEquity", "revenueGrowth", "earningsGrowth", "profitMargins", "returnOnEquity",
    "dividendYield", "targetMeanPrice", "targetMedianPrice", "targetLowPrice", "targetHighPrice",
    "recommendationMean", "recommendationKey", "numberOfAnalystOpinions", "averageVolume", "priceToBook",
    "enterpriseToEbitda", "grossMargins", "operatingMargins", "currentRatio",
]


def _info_one(tk):
    for attempt in range(3):
        try:
            info = yf.Ticker(tk).info or {}
            if info:
                return tk, {k: info.get(k) for k in INFO_KEYS}
        except Exception:  # noqa: BLE001
            pass
        time.sleep(1.5 * (attempt + 1))
    return tk, None


def fetch_info(tickers, workers=6, rounds=4):
    """Yahoo drosselt bei vielen Abrufen. Fehlgeschlagene werden in weiteren Runden mit Pause und weniger Parallelitaet wiederholt."""
    result, pending = {}, list(tickers)
    for rnd in range(rounds):
        if not pending:
            break
        if rnd:
            time.sleep(8 * rnd)
        with ThreadPoolExecutor(max(1, workers // (rnd + 1))) as ex:
            for tk, info in ex.map(_info_one, pending):
                if info:
                    result[tk] = info
        pending = [t for t in pending if t not in result]
    for t in pending:
        result[t] = None
    return result


def fetch_detail(tk):
    """Analysten-Verlauf, letzte Hoch-/Herabstufungen, Termine."""
    out = {"rec_trend": None, "actions": [], "earnings_date": None}
    t = yf.Ticker(tk)
    try:
        rec = t.recommendations
        if rec is not None and len(rec):
            out["rec_trend"] = [
                {"period": r["period"], **{k: int(r[k]) for k in ["strongBuy", "buy", "hold", "sell", "strongSell"]}}
                for _, r in rec.iterrows()
            ]
    except Exception:  # noqa: BLE001
        pass
    try:
        ud = t.upgrades_downgrades
        if ud is not None and len(ud):
            ud = ud.reset_index().head(6)
            for _, r in ud.iterrows():
                out["actions"].append({
                    "date": str(pd.Timestamp(r["GradeDate"]).date()), "firm": r.get("Firm"),
                    "from": r.get("FromGrade") or "", "to": r.get("ToGrade") or "", "action": r.get("Action") or "",
                    "pt": None if pd.isna(r.get("currentPriceTarget")) else float(r.get("currentPriceTarget")),
                    "prior_pt": None if pd.isna(r.get("priorPriceTarget")) else float(r.get("priorPriceTarget")),
                })
    except Exception:  # noqa: BLE001
        pass
    try:
        cal = t.calendar or {}
        ed = cal.get("Earnings Date")
        if ed:
            out["earnings_date"] = str(ed[0] if isinstance(ed, (list, tuple)) else ed)
    except Exception:  # noqa: BLE001
        pass
    return tk, out


def fetch_details(tickers, workers=6):
    with ThreadPoolExecutor(workers) as ex:
        return dict(ex.map(fetch_detail, tickers))


# ---------------------------------------------------------------- Google News
def google_news(name, region="US", n=5):
    clean = re.sub(r"\b(Inc\.?|Corporation|Corp\.?|Company|Co\.?|Ltd\.?|plc|SE|AG|N\.V\.)\b", "", name).strip(" ,.")
    if region == "US":
        q, loc = f'"{clean}" stock when:14d', "hl=en-US&gl=US&ceid=US:en"
    else:
        q, loc = f'"{clean}" Aktie when:14d', "hl=de&gl=DE&ceid=DE:de"
    url = f"https://news.google.com/rss/search?q={urllib.parse.quote(q)}&{loc}"
    try:
        feed = feedparser.parse(url)
    except Exception:  # noqa: BLE001
        return []
    items = []
    for e in feed.entries[:n]:
        src = (e.get("source") or {}).get("title", "")
        title = e.title
        if src and title.endswith(" - " + src):
            title = title[: -len(src) - 3]
        date = ""
        if e.get("published_parsed"):
            date = time.strftime("%Y-%m-%d", e.published_parsed)
        items.append({"title": title, "source": src, "date": date, "link": e.link})
    return items


def fetch_news(names, workers=6):
    def one(args):
        tk, name, region = args
        return tk, google_news(name, region)

    with ThreadPoolExecutor(workers) as ex:
        return dict(ex.map(one, names))


# ---------------------------------------------------------------- Wechselkurs (EZB ueber Frankfurter)
def usd_eur():
    try:
        r = requests.get("https://api.frankfurter.dev/v1/latest?base=USD&symbols=EUR", headers=UA, timeout=20)
        r.raise_for_status()
        j = r.json()
        return {"rate": j["rates"]["EUR"], "date": j["date"]}
    except Exception:  # noqa: BLE001
        return None


# ---------------------------------------------------------------- SEC EDGAR: Insider-Meldungen (Form 4)
# Die SEC verlangt Name/Kontakt im User-Agent (Fair-Access-Regel). Kontakt kommt aus der Umgebungsvariable SEC_CONTACT
# (lokal oder als GitHub-Secret). Ohne Angabe lehnt www.sec.gov anonyme Abrufe ab und der Insider-Teil bleibt aus.
_SEC = {"User-Agent": "AktienRadar " + (os.environ.get("SEC_CONTACT") or "private research project")}
SEC_ERROR = []
_cik = {}


def _sec_get(url, **kw):
    time.sleep(0.12)  # SEC erlaubt max. 10 Abrufe pro Sekunde
    return requests.get(url, headers=_SEC, timeout=25, **kw)


def _load_cik():
    if not _cik:
        r = _sec_get("https://www.sec.gov/files/company_tickers.json")
        r.raise_for_status()
        for v in r.json().values():
            _cik[v["ticker"].upper()] = int(v["cik_str"])
    return _cik


def insiders(tk, days=90, max_filings=12):
    """Zaehlt Insider-Kaeufe (Code P) und -Verkaeufe (Code S) der letzten Tage. Nur US-Firmen."""
    if SEC_ERROR:
        return None
    try:
        cik = _load_cik().get(tk.upper())
        if not cik:
            return None
        sub = _sec_get(f"https://data.sec.gov/submissions/CIK{cik:010d}.json").json()
        rec = sub["filings"]["recent"]
        cutoff = (dt.date.today() - dt.timedelta(days=days)).isoformat()
        filings = [(rec["accessionNumber"][i], rec["primaryDocument"][i], rec["filingDate"][i])
                   for i in range(len(rec["form"]))
                   if rec["form"][i] == "4" and rec["filingDate"][i] >= cutoff][:max_filings]
        buys = sells = 0
        buy_val = sell_val = 0.0
        for acc, doc, _date in filings:
            url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc.replace('-', '')}/{doc.split('/')[-1]}"
            try:
                root = ET.fromstring(_sec_get(url).content)
            except Exception:  # noqa: BLE001
                continue
            for tr in root.iter("nonDerivativeTransaction"):
                code = tr.findtext("transactionCoding/transactionCode")
                sh = float(tr.findtext("transactionAmounts/transactionShares/value") or 0)
                px = float(tr.findtext("transactionAmounts/transactionPricePerShare/value") or 0)
                if code == "P":
                    buys += 1
                    buy_val += sh * px
                elif code == "S":
                    sells += 1
                    sell_val += sh * px
        return {"days": days, "form4_filings": len(filings), "buys": buys, "sells": sells,
                "buy_value": round(buy_val), "sell_value": round(sell_val),
                "capped": len(filings) >= max_filings}
    except Exception:  # noqa: BLE001
        return None


def fetch_insiders(tickers):
    try:
        _load_cik()
    except Exception as e:  # noqa: BLE001
        SEC_ERROR.append(str(e)[:80])
        return {tk: None for tk in tickers}
    return {tk: insiders(tk) for tk in tickers}


# ---------------------------------------------------------------- Marktindizes
INDICES = {"^GSPC": "S&P 500", "^IXIC": "Nasdaq Composite", "^GDAXI": "DAX", "^VIX": "VIX (Schwankungsindex)",
           "^TNX": "Rendite 10-jährige US-Anleihe"}


def fetch_indices(period="2y"):
    df = yf.download(list(INDICES), period=period, interval="1d", auto_adjust=False, group_by="column",
                     threads=True, progress=False)
    return df["Close"].dropna(how="all")
