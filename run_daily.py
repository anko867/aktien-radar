"""Taeglicher Lauf: Daten holen, auswaehlen, Verlauf/Bilanz fortschreiben, Webseite bauen -> docs/index.html"""
import json
import sys
import time

import pandas as pd

from radar import data, market, screen, state, universe
from radar.config import CFG, DATA, DOCS
from radar.render import build_page

t0 = time.time()
use_cache = "--cache" in sys.argv
notes = []


def log(msg):
    print(f"[{time.time() - t0:5.0f}s] {msg}", flush=True)


# 1. Aktienliste
uni, unotes = universe.build()
notes += unotes
names = {t: v["name"] for t, v in uni.items()}
log(f"Aktienliste: {len(uni)} Aktien")

# 2. Kurse
prices = data.download_prices(list(uni), "6y", use_cache=use_cache)
prices, asof = data.trim_to_asof(prices)
missing = [t for t in uni if t not in prices["Close"].columns]
if missing:
    notes.append(f"Ohne Kursdaten bei Yahoo ({len(missing)}): " + ", ".join(missing))
log(f"Kurse: {prices['Close'].shape[1]} Aktien, Datenstand {asof.date()}")

idx_df = data.fetch_indices()
idx_df.index = idx_df.index.tz_localize(None) if idx_df.index.tz is not None else idx_df.index
index_close = idx_df["^GSPC"].dropna().loc[:asof]
fx = data.usd_eur()
if not fx:
    notes.append("Wechselkurs (Frankfurter/EZB) nicht erreichbar: Euro-Umrechnung fehlt heute.")

# 3. Stufe A: Kursfilter
rows = screen.price_metrics(prices)
loose = rows[rows["f_liquid_price"] & (rows["dd"] >= CFG["loose_dd"])]
log(f"Handelbar: {int(rows['f_liquid_price'].sum())}, Kandidaten fuer Analystendaten: {len(loose)}")

# 4. Stufe B: Analystendaten nur fuer Kandidaten
info = data.fetch_info(list(loose.index))
bad = [t for t, v in info.items() if not v]
if bad:
    notes.append(f"Keine Yahoo-Kennzahlen/Analystendaten ({len(bad)}): " + ", ".join(bad))
df = screen.evaluate(rows, info)
top, watch = screen.select(df)
log(f"Top: {len(top)} (alle Filter), Beobachtung: {len(watch)}")

# 5. Details fuer die angezeigten Aktien
shown = list(top.index) + list(watch.index)
details = data.fetch_details(shown)
log("Analystenverlauf geladen")
news = data.fetch_news([(t, info[t].get("shortName") or uni[t]["name"], uni[t]["region"]) for t in shown if info.get(t)])
log(f"Nachrichten geladen ({sum(1 for v in news.values() if v)} mit Treffern)")
ins = data.fetch_insiders([t for t in shown if uni[t]["region"] == "US"])
log(f"SEC-Insiderdaten: {sum(1 for v in ins.values() if v)} von {len(ins)}")
hist = screen.history_hit_rate(prices, shown, CFG["hist_years"])
realism = {t: screen.realism(df.loc[t], hist.get(t)) for t in shown}

# 6. Gedaechtnis: Vergleich mit gestern, Bilanz
prev = state.previous_snapshot(asof)
diff = state.diff_with_previous(prev, top, watch, df, names)
state.save_snapshot(asof, top, watch, df)
picks = state.load_picks()
picks = state.add_new_picks(picks, top, asof, names, df)
picks = state.update_picks(picks, prices, index_close)
state.save_picks(picks)
psum = state.summarize(picks)

# 7. Marktlage + Seite
if data.SEC_ERROR:
    notes.append("SEC EDGAR: Zugriff abgelehnt (" + data.SEC_ERROR[0] + "). Die SEC verlangt eine Kontakt-E-Mail im Programmkopf; "
                 "ohne Freigabe bleibt die Insider-Auswertung aus.")
mk = market.overview(idx_df, rows, fx, asof)
n_info = sum(1 for v in info.values() if v)
n_news = sum(1 for v in news.values() if v)
n_ins = sum(1 for v in ins.values() if v)
source_status = [
    ("Yahoo Finance (yfinance)", "Kurse, Analysten, Kursziele, Kennzahlen, Termine, VIX, Zinsen", f"OK: Kurse {prices['Close'].shape[1]} Aktien, Kennzahlen {n_info}"),
    ("Wikipedia", "Indexlisten S&P 500, Nasdaq-100, DAX, MDAX", "; ".join(n.split(":")[0] + " " + n.split(":")[1].split("von")[0].strip() if "gelesen" in n else n for n in unotes)),
    ("Google News (RSS)", "Schlagzeilen je Aktie", f"OK: {n_news} von {len(news)} Aktien mit Treffern"),
    ("Frankfurter / EZB", "Euro-Umrechnung", f"OK ({fx['date']})" if fx else "Fehler"),
    ("SEC EDGAR", "Insider-Käufe und -Verkäufe (nur US-Firmen)",
     f"OK: {n_ins} von {len(ins)} US-Aktien" if n_ins else "pausiert: Die SEC lehnt Abrufe ohne Kontaktangabe im Programmkopf ab (siehe Hinweise)"),
    ("Stooq", "Ersatz-Kursquelle", "nicht verwendet: Die Seite sperrt automatische Abrufe per Bot-Schutz"),
    ("Finnhub, Financial Modeling Prep, Alpha Vantage, FRED", "Zweitquellen für Analysten, Kennzahlen, Zinsen", "noch nicht angeschlossen (API-Schlüssel fehlen)"),
]
counts = {"universe": len(uni), "data": prices["Close"].shape[1], "liquid": int(rows["f_liquid_price"].sum()),
          "dd": int((rows["f_liquid_price"] & (rows["dd"] >= CFG["min_dd"])).sum()), "pass": int(df["passed"].sum())}
ctx = dict(asof=asof, top=top, watch=watch, uni=uni, info=info, details=details, news=news, insiders=ins, hist=hist,
           realism=realism, prices=prices, fx=fx, market=mk, diff=diff, names=names, picks=picks, picks_summary=psum,
           source_status=source_status, notes=notes, counts=counts)
html = build_page(ctx)
(DOCS / "index.html").write_text(html, encoding="utf-8")
(DOCS / ".nojekyll").write_text("", encoding="utf-8")
(DOCS / "robots.txt").write_text("User-agent: *\nDisallow: /\n", encoding="utf-8")
log(f"Seite geschrieben: docs/index.html ({len(html) / 1024:.0f} KB)")

latest = {"asof": str(asof.date()), "top": list(top.index), "watch": list(watch.index), "counts": counts, "notes": notes}
(DATA / "latest.json").write_text(json.dumps(latest, ensure_ascii=False, indent=1), encoding="utf-8")
