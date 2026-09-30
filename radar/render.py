"""Baut die Webseite (eine einzige HTML-Datei, handytauglich, ohne externe Skripte)."""
import datetime as dt
import html

import numpy as np
import pandas as pd

from .config import CFG
from .market import sentences

GLOSSARY = {
    "konsens": "Durchschnitt der Empfehlungen vieler Bank-Analysten, Note 1 = Strong Buy bis 5 = Sell.",
    "kursziel": "Preis, den ein Analyst in etwa 12 Monaten für angemessen hält. Eine Schätzung, keine Zusage.",
    "hoch": "52-Wochen-Hoch: höchster Kurs der letzten 12 Monate.",
    "vol": "Volatilität: wie stark der Kurs typischerweise hin- und herspringt, in Prozent pro Jahr.",
    "rsi": "RSI (14 Tage): Wert 0–100. Unter 30 gilt eine Aktie als überverkauft (stark gefallen), über 70 als überkauft.",
    "kgv": "Kurs-Gewinn-Verhältnis: Kurs geteilt durch Gewinn je Aktie. Niedrig heißt relativ günstig, je nach Branche.",
    "beta": "Wie stark die Aktie im Vergleich zum Gesamtmarkt schwankt. 1 = wie der Markt.",
    "fcf": "Free Cashflow: Geld, das der Firma nach allen Investitionen bleibt.",
    "mcap": "Marktkapitalisierung: Kurs mal Zahl aller Aktien, also der Börsenwert.",
    "sma": "Gleitender Durchschnitt: Durchschnittskurs der letzten 20 Handelstage. Darüber = kurzfristig aufwärts.",
    "modell": "Zufallsmodell ohne Trend: Chance, dass der Kurs im Zeitfenster mindestens einmal +20 % erreicht. Keine Prognose.",
    "score": "Punktwert 0–100 aus fünf Teilen (siehe Kasten). Er sortiert die Liste, er sagt keine Rendite voraus.",
    "insider": "Insider: Vorstände und Großaktionäre. Käufe gelten als aussagekräftiger als Verkäufe, die oft planmäßig sind.",
}


REC_DE = {"strong_buy": "Strong Buy", "buy": "Buy", "hold": "Hold (halten)", "underperform": "Underperform",
          "sell": "Sell", "strong_sell": "Strong Sell", "none": "keine Angabe"}
ACT_DE = {"main": "bestätigt", "reit": "bestätigt", "up": "hochgestuft", "down": "herabgestuft", "init": "Erstbewertung",
          "upgrade": "hochgestuft", "downgrade": "herabgestuft"}
SECTOR_DE = {"Technology": "Technologie", "Healthcare": "Gesundheit", "Financial Services": "Finanzen",
             "Consumer Cyclical": "Zyklischer Konsum", "Consumer Defensive": "Basiskonsum", "Industrials": "Industrie",
             "Energy": "Energie", "Utilities": "Versorger", "Real Estate": "Immobilien", "Basic Materials": "Grundstoffe",
             "Communication Services": "Kommunikation"}


def esc(x):
    return html.escape(str(x), quote=True)


def de(x, d=1, sign=False):
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "keine Daten"
    x = 0.0 if round(x, d) == 0 else x  # kein "−0,0"
    s = f"{x:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    if sign and x > 0:
        s = "+" + s
    return s.replace("-", "−")


def pc(x, d=1, sign=True):
    return "keine Daten" if x is None or (isinstance(x, float) and not np.isfinite(x)) else de(x * 100, d, sign) + " %"


def big(x, cur=""):
    if x is None or not np.isfinite(x):
        return "keine Daten"
    a = abs(x)
    for lim, suf in ((1e12, " Bio."), (1e9, " Mrd."), (1e6, " Mio.")):
        if a >= lim:
            return de(x / lim, 1) + suf + (" " + cur if cur else "")
    return de(x, 0) + (" " + cur if cur else "")


def T(label, key):
    return f'<span class="t" tabindex="0" data-tip="{esc(GLOSSARY[key])}">{esc(label)}</span>'


def cur_sym(info, tk):
    c = (info or {}).get("currency") or ("EUR" if "." in tk else "USD")
    return {"USD": "$", "EUR": "€", "GBP": "£", "CHF": "CHF"}.get(c, c)


def money(x, sym):
    return "keine Daten" if x is None or not np.isfinite(x) else f"{de(x, 2)} {sym}"


# ---------------------------------------------------------------- Diagramme
def price_chart(series, hi52, t_mean, sym):
    s = series.dropna().iloc[-252:]
    w, h, ml, mr, mt, mb = 640, 210, 8, 78, 12, 26
    vals = list(s.values) + [hi52] + ([t_mean] if t_mean and np.isfinite(t_mean) else [])
    lo, hi = min(vals) * 0.97, max(vals) * 1.03
    x = lambda i: ml + (w - ml - mr) * i / (len(s) - 1)  # noqa: E731
    y = lambda v: mt + (h - mt - mb) * (1 - (v - lo) / (hi - lo))  # noqa: E731
    pts = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(s.values))
    area = f"{x(0):.1f},{y(lo):.1f} {pts} {x(len(s) - 1):.1f},{y(lo):.1f}"
    grid = ""
    for k in range(4):
        v = lo + (hi - lo) * k / 3
        grid += f'<line class="grid" x1="{ml}" x2="{w - mr}" y1="{y(v):.1f}" y2="{y(v):.1f}"/>'
        grid += f'<text class="ax" x="{w - mr + 6}" y="{y(v) + 4:.1f}">{de(v, 0 if v > 100 else 1)}</text>'
    labels = ""
    for i in (0, len(s) // 2, len(s) - 1):
        d = s.index[i]
        anchor = "start" if i == 0 else "end" if i == len(s) - 1 else "middle"
        labels += f'<text class="ax" x="{x(i):.1f}" y="{h - 8}" text-anchor="{anchor}">{d.strftime("%d.%m.%y")}</text>'
    ref = f'<line class="hi" x1="{ml}" x2="{w - mr}" y1="{y(hi52):.1f}" y2="{y(hi52):.1f}"/>'
    ref += f'<text class="lb hi" x="{ml + 4}" y="{y(hi52) - 4:.1f}">52-Wochen-Hoch {de(hi52, 2)}</text>'
    if t_mean and np.isfinite(t_mean):
        ref += f'<line class="tg" x1="{ml}" x2="{w - mr}" y1="{y(t_mean):.1f}" y2="{y(t_mean):.1f}"/>'
        ref += f'<text class="lb tg" x="{ml + 4}" y="{y(t_mean) - 4:.1f}">mittleres Kursziel {de(t_mean, 2)}</text>'
    last = s.values[-1]
    ref += f'<circle class="dot" cx="{x(len(s) - 1):.1f}" cy="{y(last):.1f}" r="3.5"/>'
    return (f'<svg class="chart" viewBox="0 0 {w} {h}" role="img" aria-label="Kursverlauf der letzten 12 Monate">'
            f'{grid}<polygon class="area" points="{area}"/><polyline class="ln" points="{pts}"/>{ref}{labels}</svg>')


def analyst_bar(rec):
    if not rec:
        return '<p class="muted">Verlauf der Analystenurteile: keine Daten.</p>'
    cur = rec[0]
    parts = [("strongBuy", "Strong Buy", "c1"), ("buy", "Buy", "c2"), ("hold", "Hold", "c3"), ("sell", "Sell", "c4"),
             ("strongSell", "Strong Sell", "c5")]
    tot = sum(cur[k] for k, _, _ in parts) or 1
    seg = "".join(f'<span class="{c}" style="width:{cur[k] / tot * 100:.1f}%"></span>' for k, _, c in parts if cur[k])
    leg = " ".join(f'<span class="lg"><i class="{c}"></i>{n} {cur[k]}</span>' for k, n, c in parts)
    rows = "".join(
        f"<tr><td>{esc('heute' if r['period'] == '0m' else 'vor ' + r['period'].lstrip('-').replace('m', ' Mon.'))}</td>"
        + "".join(f"<td>{r[k]}</td>" for k, _, _ in parts) + "</tr>" for r in rec)
    return (f'<div class="stack">{seg}</div><div class="legend">{leg}</div>'
            f'<table class="mini"><tr><th>Stand</th><th>Strong Buy</th><th>Buy</th><th>Hold</th><th>Sell</th>'
            f'<th>Strong Sell</th></tr>{rows}</table>')


def target_range(price, lo, mean, med, hi, sym):
    vals = [v for v in (price, lo, mean, med, hi) if v and np.isfinite(v)]
    if not lo or not hi or not np.isfinite(lo) or not np.isfinite(hi):
        return '<p class="muted">Kursziel-Spanne: keine Daten.</p>'
    a, b = min(vals) * 0.96, max(vals) * 1.04
    x = lambda v: 10 + 300 * (v - a) / (b - a)  # noqa: E731
    out = f'<svg class="range" viewBox="0 0 320 62" role="img" aria-label="Spanne der Kursziele"><line class="trk" x1="{x(lo):.1f}" x2="{x(hi):.1f}" y1="30" y2="30"/>'
    for v, anc, lab in ((lo, "start", "niedrigstes"), (hi, "end", "höchstes")):
        out += f'<line class="tick" x1="{x(v):.1f}" x2="{x(v):.1f}" y1="24" y2="36"/><text class="ax" x="{x(v):.1f}" y="52" text-anchor="{anc}">{lab} {de(v, 0)}</text>'
    if mean and np.isfinite(mean):
        out += f'<rect class="mean" x="{x(mean) - 4:.1f}" y="24" width="8" height="12" rx="2"/><text class="ax" x="{x(mean):.1f}" y="16" text-anchor="middle">Mittel {de(mean, 0)}</text>'
    out += f'<circle class="px" cx="{x(price):.1f}" cy="30" r="5"/></svg>'
    return out + f'<p class="muted small">Punkt = heutiger Kurs ({money(price, sym)}), Viereck = Mittel, Median {de(med, 2)} {sym}.</p>'


# ---------------------------------------------------------------- Karte pro Aktie
def card(rank, tk, r, uni, info, det, news, ins, hist, real, prices, usd_eur, kind):
    i = info or {}
    sym = cur_sym(i, tk)
    name = i.get("longName") or i.get("shortName") or uni[tk]["name"]
    price = float(r["price"])
    eur = f' <small class="muted">≈ {de(price * usd_eur["rate"], 2)} €</small>' if sym == "$" and usd_eur else ""
    chg = float(r["day_chg"])
    cls = {"realistisch": "good", "möglich": "mid", "unwahrscheinlich": "bad"}[real["label"]]
    fails = ""
    if kind == "watch":
        fails = f'<span class="warn">Nicht erfüllt: {esc(", ".join(r["fail_list"]))}</span>'
    up = pc(r["upside"], 0)
    head = (f'<summary><span class="rk">{rank}</span>'
            f'<span class="nm"><b>{esc(tk)}</b> {esc(name)}<small>{esc(SECTOR_DE.get(i.get("sector"), i.get("sector") or ""))} · {esc(", ".join(uni[tk]["indices"]))}</small></span>'
            f'<span class="px">{money(price, sym)}{eur}<em class="{"up" if chg >= 0 else "dn"}">{pc(chg)}</em></span>'
            f'<span class="sc"><b>{r["score"]:.0f}</b><small>Punkte</small></span>'
            f'<span class="badge {cls}">{real["label"]}</span>'
            f'<span class="sub">Kursziel {up} · {pc(-r["dd"], 0)} vom Hoch{" · " + fails if fails else ""}</span></summary>')

    perf = "".join(f"<td>{pc(r[k])}</td>" for k in ("ret5", "ret20", "ret60", "ret120", "ret250"))
    chart = price_chart(prices["Close"][tk], float(r["hi52"]), r["t_mean"], sym)
    sec_price = (f'<section><h4>Kursverlauf</h4>{chart}'
                 f'<table class="mini perf"><tr><th>1 W.</th><th>1 M.</th><th>3 M.</th><th>6 M.</th><th>12 M.</th></tr><tr>{perf}</tr></table>'
                 f'<p class="muted small">Schlusskurse, bereinigt um Splits und Dividenden. RSI heute: {de(r["rsi"], 0)}. '
                 f'Kurs {"über" if r["price"] > r["sma20"] else "unter"} dem 20-Tage-Durchschnitt ({de(r["sma20"], 2)} {sym}).</p></section>')

    rec_mean = r["rec"]
    acts = ""
    if det and det["actions"]:
        acts = "<table class=\"mini\"><tr><th>Datum</th><th>Haus</th><th>Urteil</th><th>Kursziel</th></tr>" + "".join(
            f"<tr><td>{esc(a['date'])}</td><td>{esc(a['firm'])}</td><td>{esc(ACT_DE.get(a['action'], a['action']))}: {esc(a['from'] + ' → ' if a['from'] else '')}{esc(a['to'])}</td>"
            f"<td>{(de(a['prior_pt'], 0) + ' → ' if a['prior_pt'] else '')}{de(a['pt'], 0) if a['pt'] else '–'}</td></tr>" for a in det["actions"]) + "</table>"
    sec_an = (f'<section><h4>Analysten</h4><p><b>{T("Konsens", "konsens")}:</b> Note {de(rec_mean, 2)} '
              f'({esc(REC_DE.get(i.get("recommendationKey"), i.get("recommendationKey") or "keine Daten"))}) von {de(r["n_an"], 0)} Analysten. '
              f'<b>{T("Kursziel", "kursziel")}</b> im Mittel {money(r["t_mean"], sym)} ({pc(r["upside"], 0)} zum Kurs).</p>'
              f'{analyst_bar(det["rec_trend"] if det else None)}'
              f'{target_range(price, r["t_low"], r["t_mean"], r["t_med"], r["t_high"], sym)}'
              f'{("<h5>Letzte Hoch- und Herabstufungen</h5>" + acts) if acts else ""}</section>')

    # +20-%-Einschaetzung
    cr = real["criteria"]
    mk = lambda ok: '<span class="ok">✓</span>' if ok else '<span class="no">✗</span>'  # noqa: E731
    room = r["hi52"] / r["price"] - 1
    hh = hist or {}
    t_low_txt = f"niedrigstes Kursziel {money(r['t_low'], sym)} ({pc(r['t_low'] / r['price'] - 1, 0)})" if pd.notna(r["t_low"]) else "niedrigstes Kursziel: keine Daten"
    ed = det.get("earnings_date") if det else None
    ed_txt = "keine Daten"
    if ed:
        try:
            d0 = pd.Timestamp(ed[:10])
            ed_txt = f"{d0.strftime('%d.%m.%Y')} (in {(d0.normalize() - pd.Timestamp.now().normalize()).days} Tagen)"
        except Exception:  # noqa: BLE001
            ed_txt = esc(ed)
    w = CFG["weights"]
    comp = "".join(f"<tr><td>{n}</td><td>{int(w[k] * 100)} %</td><td>{v * 100:.0f} von 100</td></tr>" for n, k, v in (
        ("Potenzial bis Kursziel", "upside", r["c_upside"] if pd.notna(r["c_upside"]) else 0),
        ("Tiefe des Rücksetzers", "depth", r["c_depth"]), ("Stärke des Analysten-Konsenses", "consensus", r["c_cons"] if pd.notna(r["c_cons"]) else 0),
        ("Erholungssignal", "recovery", r["c_rec"]), ("Schwankungsbreite", "vol", r["c_vol"] if pd.notna(r["c_vol"]) else 0)))
    sec_real = (
        f'<section class="real"><h4>Wie realistisch sind +20 %? <span class="badge {cls}">{real["label"]}</span></h4>'
        f'<p class="muted small">{real["met"]} von 4 Kriterien erfüllt. Ziel: Schlusskurs mindestens einmal 20 % über dem Einstieg innerhalb von {CFG["horizon"]} Handelstagen. Vorläufige Schwellen, siehe Rückblick.</p>'
        f'<table class="crit"><tr><td>{mk(cr["model"])}</td><td><b>{T("Modellchance", "modell")}</b>: {pc(r["model_prob"], 0, False)}'
        f'<br><small>Schwankung {pc(r["vol"], 0, False)} pro Jahr, Schwelle mind. 10 %</small></td></tr>'
        f'<tr><td>{mk(cr["history"])}</td><td><b>Trefferhistorie</b>: {pc(hh.get("freq"), 1, False)} der Starttage '
        f'({hh.get("hits", "?")} von {hh.get("days", "?")} Tagen in 5 Jahren)<br><small>Schwelle mind. 10 %. Dieselben Fenster als Risiko: in {pc(hh.get("loss10"), 0, False)} der Fälle lag der Kurs zwischendurch mind. 10 % unter dem Einstieg, schlechtester Stand nach {CFG["horizon"]} Tagen {pc(hh.get("worst_end"), 0)}.</small></td></tr>'
        f'<tr><td>{mk(cr["target"])}</td><td><b>Kursziel-Abstand</b>: Mittel {pc(r["upside"], 0)}, {t_low_txt}<br><small>Schwelle mind. +20 %</small></td></tr>'
        f'<tr><td>{mk(cr["room"])}</td><td><b>Platz bis zum Hoch</b>: {T("52-Wochen-Hoch", "hoch")} liegt {pc(room, 0, False)} über dem Kurs<br><small>Schwelle mind. 20 %</small></td></tr>'
        f'<tr><td>ℹ</td><td><b>Nächste Quartalszahlen</b>: {ed_txt}<br><small>Kann den Kurs in beide Richtungen bewegen, kein Kriterium.</small></td></tr></table>'
        f'<details class="inner"><summary>Wie der {T("Punktwert", "score")} {r["score"]:.0f} entsteht</summary>'
        f'<table class="mini"><tr><th>Teil</th><th>Gewicht</th><th>Erreicht</th></tr>{comp}</table></details></section>')

    # Kennzahlen
    kv = [
        (T("Börsenwert", "mcap"), big(i.get("marketCap"), sym)), (T("KGV", "kgv") + " (letzte 12 Mon.)", de(i.get("trailingPE"), 1)),
        ("KGV (Schätzung)", de(i.get("forwardPE"), 1)), (T("Beta", "beta"), de(i.get("beta"), 2)),
        (T("Schwankung", "vol") + " p. a.", pc(r["vol"], 0, False)), (T("Free Cashflow", "fcf"), big(i.get("freeCashflow"), sym)),
        ("Schulden / Eigenkapital", (de(i["debtToEquity"], 0) + " %") if i.get("debtToEquity") is not None else "keine Daten"),
        ("Umsatzwachstum", pc(i.get("revenueGrowth"), 0)), ("Gewinnmarge", pc(i.get("profitMargins"), 1, False)),
        ("Dividendenrendite", (de(i["dividendYield"], 2) + " %") if i.get("dividendYield") is not None else "keine Daten"),
        ("Ø Tagesumsatz (20 Tage)", big(r["turnover20"], sym)), (T("RSI", "rsi") + " (14 Tage)", de(r["rsi"], 0)),
    ]
    sec_kv = '<section><h4>Kennzahlen</h4><div class="kv">' + "".join(f"<div><span>{k}</span><b>{v}</b></div>" for k, v in kv) + "</div></section>"

    summ = (i.get("longBusinessSummary") or "")
    if len(summ) > 260:
        summ = summ[:260].rsplit(" ", 1)[0] + " …"
    sec_co = (f'<section><h4>Unternehmen</h4><p class="muted small">{esc(SECTOR_DE.get(i.get("sector"), i.get("sector") or "keine Daten"))} · {esc(i.get("industry") or "")} · {esc(i.get("country") or "")}'
              f' · {de(i.get("fullTimeEmployees"), 0) if i.get("fullTimeEmployees") else "Mitarbeiterzahl: keine Daten"} Mitarbeiter</p>'
              f'<p>{esc(summ) if summ else "Beschreibung: keine Daten."} <span class="muted small">(Quelle: Yahoo Finance, gekürzt)</span></p></section>')

    if ins:
        ins_txt = (f'{ins["buys"]} Käufe und {ins["sells"]} Verkäufe in {ins["form4_filings"]} Meldungen (Form 4, {ins["days"]} Tage)'
                   + (" — nur die neuesten 12 Meldungen ausgewertet" if ins["capped"] else "")
                   + (f'; Kaufvolumen {big(ins["buy_value"], "$")}' if ins["buys"] else ""))
    else:
        ins_txt = "nur für US-Firmen verfügbar oder keine Daten" if "." in tk else "keine Daten (SEC-Abruf heute nicht möglich)"
    sec_ins = f'<section><h4>{T("Insider", "insider")}-Meldungen (SEC)</h4><p>{ins_txt}</p></section>'

    nl = "".join(f'<li><a href="{esc(n["link"])}" target="_blank" rel="noopener">{esc(n["title"])}</a> <span class="muted small">{esc(n["source"])} · {esc(n["date"])}</span></li>' for n in (news or []))
    sec_news = f'<section><h4>Aktuelle Nachrichten</h4>{"<ul class=news>" + nl + "</ul>" if nl else "<p class=muted>Keine Schlagzeilen gefunden.</p>"}</section>'

    fl = [("Handelbarkeit/Größe", bool(r["f1"])), ("Analysten", bool(r["f2"])), ("Abstand zum Hoch", bool(r["f3"])), ("Erholungssignal", bool(r["f4"]))]
    sec_f = '<section><h4>Filter-Check</h4><p>' + " · ".join(f"{mk(ok)} {n}" for n, ok in fl) + "</p></section>"
    body = f'<div class="body">{sec_price}{sec_real}{sec_an}{sec_kv}{sec_co}{sec_ins}{sec_news}{sec_f}</div>'
    return f'<details class="card {kind}" id="t-{esc(tk)}">{head}{body}</details>'


# ---------------------------------------------------------------- Abschnitte
def section_market(m):
    rows = "".join(
        f"<tr><td>{esc(n)}</td><td>{de(v['last'], 2)}</td><td class=\"{'up' if v['chg1d'] >= 0 else 'dn'}\">{pc(v['chg1d'])}</td>"
        f"<td>{pc(v['chg1m'])}</td><td>{pc(-v['dd'], 1)}</td><td>{'über' if v['above200'] else 'unter'}</td></tr>"
        for n, v in m["table"].items())
    fx = m["fx"]
    fxt = f"1 US-Dollar = {de(fx['rate'], 4)} Euro (EZB-Referenzkurs vom {fx['date']})" if fx else "Wechselkurs: keine Daten"
    sen = "".join(f"<li>{esc(s)}</li>" for s in sentences(m))
    return (f'<section id="markt"><h2>Marktlage</h2><ul class="sent">{sen}</ul>'
            f'<div class="scroll"><table class="tbl"><tr><th>Index</th><th>Stand</th><th>Tag</th><th>1 Monat</th><th>zum 52-W-Hoch</th><th>200-Tage-Schnitt</th></tr>{rows}</table></div>'
            f'<p class="muted small">{fxt}. Zins-Zeile: Stand in Prozent, Veränderungen in Prozent des Stands.</p></section>')


def section_changes(diff, names):
    if not diff:
        return ('<section id="aenderungen"><h2>Seit dem letzten Lauf</h2><p>Das ist der erste Lauf, es gibt noch keinen Vergleich mit gestern. '
                'Ab morgen steht hier, welche Aktien neu dazugekommen oder herausgefallen sind.</p></section>')
    chips = lambda ts: " ".join(f'<a class="chip" href="#t-{esc(t)}">{esc(t)}</a>' for t in ts) or "<span class=muted>keine</span>"  # noqa: E731
    dr = "".join(f"<li><b>{esc(d['ticker'])}</b> {esc(d['name'])}: {esc(d['why'])}</li>" for d in diff["dropped"]) or "<li class=muted>keine</li>"
    return (f'<section id="aenderungen"><h2>Seit dem letzten Lauf ({esc(diff["prev_date"])})</h2>'
            f'<p><b>Neu in der Top-Liste:</b> {chips(diff["new_top"])}</p><p><b>Herausgefallen:</b></p><ul>{dr}</ul>'
            f'<p><b>Neu in der Beobachtungsliste:</b> {chips(diff["new_watch"])}</p>'
            f'<p><b>Aus der Beobachtungsliste gefallen:</b> {" ".join(esc(t) for t in diff["left_watch"]) or "<span class=muted>keine</span>"}</p></section>')


def section_bilanz(picks, summ):
    if not picks:
        body = "<p>Noch keine Empfehlungen gespeichert.</p>"
    else:
        rows = ""
        for p in sorted(picks, key=lambda p: p["signal_date"], reverse=True):
            if p["status"] == "wartet":
                st, extra = "wartet auf Einstieg", "–"
            else:
                st = {"läuft": f'läuft (Tag {p["days"]} von {CFG["horizon"]})', "abgeschlossen": "abgeschlossen"}[p["status"]]
                extra = f'{pc(p["last_gain"])} / max {pc(p["max_gain"])} / min {pc(p["min_gain"])}'
            ziel = "–"
            if p["status"] in ("läuft", "abgeschlossen"):
                ziel = f'✓ erreicht am {p["hit_date"]} (Tag {p["days_to_hit"]})' if p["hit"] else ("✗ nicht erreicht" if p["status"] == "abgeschlossen" else "noch nicht")
            rows += (f'<tr><td><b>{esc(p["ticker"])}</b><br><small>{esc(p["name"])}</small></td><td>{esc(p["signal_date"])}</td>'
                     f'<td>{esc(p["entry_date"] or "–")}<br><small>{money(p["entry_open"], "") if p["entry_open"] else ""}</small></td><td>{st}</td><td>{ziel}</td><td>{extra}</td></tr>')
        body = (f'<div class="scroll"><table class="tbl"><tr><th>Aktie</th><th>Empfohlen (Datenstand)</th><th>Einstieg</th><th>Status</th><th>+20 %</th><th>Stand / bester / schlechtester Schlusskurs</th></tr>{rows}</table></div>')
    if summ.get("done"):
        head = (f'<p><b>{summ["done"]} abgeschlossen:</b> {summ["hits"]} erreichten das Ziel (Trefferquote {pc(summ["hit_rate"], 0, False)}). '
                f'Ø Rendite am Fensterende {pc(summ["avg_end"])}, schlechteste {pc(summ["worst_end"])}; S&P 500 im selben Zeitraum Ø {pc(summ["avg_sp"])}.</p>')
    else:
        head = (f'<p>Noch keine Empfehlung ist abgeschlossen: Das Beobachtungsfenster dauert {CFG["horizon"]} Handelstage ab Einstieg. '
                f'Offen: {summ["running"]} laufend, {summ["waiting"]} wartend auf Einstieg. Eine erste Trefferquote gibt es frühestens nach etwa 4 Wochen, '
                f'belastbar wird sie erst nach mehreren Monaten.</p>')
    rule = (f'<p class="muted small">Regeln: Einstieg = Eröffnungskurs des ersten Handelstags nach dem Datenstand, an dem die Aktie in die Top-Liste kam. '
            f'Ziel erreicht = ein Schlusskurs mindestens {int(CFG["target"] * 100)} % über dem Einstieg innerhalb von {CFG["horizon"]} Handelstagen. '
            f'Kosten, Steuern und Kauf-/Verkaufsspannen sind nicht eingerechnet.</p>')
    return f'<section id="bilanz"><h2>Bilanz der bisherigen Empfehlungen</h2>{head}{body}{rule}</section>'


def section_backtest(bt):
    if not bt:
        return '<section id="rueckblick"><h2>Rückblick: Wie gut hätten die Regeln funktioniert?</h2><p>Noch kein Backtest vorhanden.</p></section>'
    s, b = bt["signal"], bt["baseline_all"]
    f = lambda d, k="hit_rate": pc(d[k], 1, False)  # noqa: E731
    yrs = "".join(
        f'<tr><td>{y}</td><td>{d["n"]}</td><td>{pc(d["hit_rate"], 1, False)}</td><td>{pc(d["baseline_hit_rate"], 1, False)}</td><td>{pc(d["ret_end_mean"])}</td></tr>'
        for y, d in bt["by_year"].items())
    cal = "".join(f'<tr><td>{esc(k)}</td><td>{d["n"]}</td><td>{pc(d["avg_model_prob"], 0, False)}</td><td>{pc(d["hit_rate"], 0, False)}</td></tr>' for k, d in bt["calibration"].items())
    rg = lambda n, d, bd: f'<tr><td>{n}</td><td>{d["n"]}</td><td>{f(d)}</td><td>{f(bd)}</td><td>{pc(d["ret_end_mean"])}</td><td>{pc(bd["ret_end_mean"])}</td></tr>'  # noqa: E731
    reg = (rg("Gesamtmarkt schwach (S&P 500 ≥ 10 % unter Hoch)", bt["market_weak"], bt["baseline_market_weak"])
           + rg("Gesamtmarkt ruhig", bt["market_calm"], bt["baseline_market_calm"])
           + rg("ohne das Jahr 2020", bt["without_2020"], bt["baseline_without_2020"]))
    return f'''<section id="rueckblick"><h2>Rückblick: Wie gut hätten die Regeln funktioniert?</h2>
<p><b>Ergebnis in einem Satz:</b> Die Kursregeln (Handelbarkeit, mind. 25 % unter dem Hoch, Erholungssignal) erreichten im Test in {f(s)} der {s["n"]} Fälle +20 % innerhalb von {bt["horizon"]} Handelstagen, gegenüber {f(b)} bei zufällig gewählten Aktien.
Das Ergebnis hängt aber stark von der Marktlage ab (Tabelle unten), und die Analystenregel ließ sich nicht testen.</p>
<p class="muted small">Getestet: {bt["n_tickers"]} Aktien der heutigen Indexlisten, Signaltage {esc(bt["period"][0])} bis {esc(bt["period"][1])}. Einstieg = Eröffnung am Tag nach dem Signal, Ziel = Schlusskurs ≥ +20 %. Pro Aktie höchstens ein Signal je {bt["horizon"]} Tage.
Der S&P 500 selbst erreichte +20 % in {bt["horizon"]} Handelstagen an nur {pc(bt["index_hit_rate"], 2, False)} der Tage.</p>
<h3>Vergleich: Regeln gegen Zufall</h3>
<div class="scroll"><table class="tbl"><tr><th></th><th>Fälle</th><th>Treffer (Regeln)</th><th>Treffer (Zufall)</th><th>Ø Rendite Tag {bt["horizon"]} (Regeln)</th><th>Ø Rendite (Zufall)</th></tr>
<tr><td><b>Alle Jahre</b></td><td>{s["n"]}</td><td><b>{f(s)}</b></td><td>{f(b)}</td><td>{pc(s["ret_end_mean"])}</td><td>{pc(b["ret_end_mean"])}</td></tr>{reg}</table></div>
<h3>Nach Jahr</h3><div class="scroll"><table class="tbl"><tr><th>Jahr</th><th>Fälle</th><th>Treffer (Regeln)</th><th>Treffer (Zufall)</th><th>Ø Rendite Tag {bt["horizon"]}</th></tr>{yrs}</table></div>
<h3>Risiko bei den Regel-Treffern</h3><ul><li>Mittlere Rendite am Tag {bt["horizon"]}: {pc(s["ret_end_mean"])}, Median {pc(s["ret_end_median"])}.</li>
<li>In {pc(1 - s["share_end_positive"], 0, False)} der Fälle lag der Kurs am Tag {bt["horizon"]} im Minus; die schlechtesten 10 % verloren mehr als {pc(-s["ret_end_p10"], 0, False)}, der schlimmste Fall {pc(s["ret_end_worst"], 0)}.</li>
<li>Im Durchschnitt lag der tiefste Schlusskurs im Fenster {pc(-s["min_gain_mean"], 1, False)} unter dem Einstieg.</li></ul>
<h3>Stimmt das Zufallsmodell?</h3><p class="muted small">Die Seite zeigt je Aktie eine Modellchance. Wie gut sie zur Wirklichkeit passt, zeigt der Vergleich im Test:</p>
<div class="scroll"><table class="tbl"><tr><th>Modellchance</th><th>Fälle</th><th>Ø Modell</th><th>Tatsächliche Treffer</th></tr>{cal}</table></div>
<p class="muted small">Je höher die Modellchance, desto häufiger die Treffer. Das Modell unterschätzt niedrige und überschätzt hohe Werte, es ist also ein Rangfolge-Hinweis, keine genaue Wahrscheinlichkeit.</p>
<h3>Grenzen des Tests</h3><ul>
<li><b>Analystenregel nicht getestet:</b> Kostenlose Quellen liefern keine Analystenurteile von früher. Sie werden deshalb nur in der Bilanz ab dem ersten Tag vorwärts geprüft.</li>
<li><b>Überlebenden-Verzerrung:</b> Getestet wurden nur Firmen, die heute noch in den Indizes stehen. Pleitegegangene fehlen, das Ergebnis ist eher zu optimistisch.</li>
<li><b>Krisen-Erholungen dominieren:</b> Nach dem Crash 2020 stiegen fast alle Aktien. Ohne 2020 sinkt die Trefferquote deutlich.</li>
<li><b>Kein Börsenwert-Filter im Test</b> (historische Werte fehlen); Kosten, Spanne und Steuern nicht eingerechnet.</li>
<li><b>Kein Tuning:</b> Die Schwellen wurden nicht an diesen Daten optimiert; sie sind die Startwerte aus dem Plan.</li></ul></section>'''


def section_sources(status, notes):
    rows = "".join(f'<tr><td>{esc(a)}</td><td>{esc(b)}</td><td>{esc(c)}</td></tr>' for a, b, c in status)
    nt = "".join(f"<li>{esc(n)}</li>" for n in notes)
    return (f'<section id="quellen"><h2>Datenquellen und Hinweise</h2><div class="scroll"><table class="tbl"><tr><th>Quelle</th><th>Verwendet für</th><th>Status heute</th></tr>{rows}</table></div>'
            f'<h3>Datenlücken und Meldungen des Laufs</h3><ul>{nt}</ul>'
            f'<h3>Wichtig</h3><p>Diese Seite liefert Fakten und Statistiken aus frei zugänglichen Quellen. Sie ist <b>keine Anlageberatung</b> und keine Kaufempfehlung. Kurse sind vom Vortag (Schlusskurse), Analystenurteile sind Schätzungen, '
            f'und Kursverluste sind jederzeit möglich. Fehlende Zahlen sind mit „keine Daten“ markiert und nicht geschätzt. Tippe auf gepunktet unterstrichene Wörter für eine kurze Erklärung.</p></section>')


CSS = """
:root{--bg:#f6f7f9;--card:#fff;--ink:#16181d;--mut:#6a717d;--line:#e3e6ea;--acc:#1a56db;--good:#117a45;--goodbg:#e3f5ea;--mid:#9a6700;--midbg:#fbf0d5;--bad:#b42318;--badbg:#fde8e6;--up:#117a45;--dn:#b42318;--hi:#9a6700;--tg:#1a56db;--area:rgba(26,86,219,.10)}
@media (prefers-color-scheme:dark){:root{--bg:#0f1115;--card:#181b21;--ink:#e8eaee;--mut:#9aa1ad;--line:#2a2f38;--acc:#6ea0ff;--good:#4cc985;--goodbg:#143424;--mid:#e3b341;--midbg:#3a2f12;--bad:#ff8a80;--badbg:#3e1b18;--up:#4cc985;--dn:#ff8a80;--hi:#e3b341;--tg:#6ea0ff;--area:rgba(110,160,255,.14)}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
main{max-width:980px;margin:0 auto;padding:0 14px 60px}h1{font-size:1.5rem;margin:.2em 0}h2{font-size:1.25rem;margin:1.6em 0 .5em}h3{font-size:1.02rem;margin:1.2em 0 .4em}h4{font-size:.98rem;margin:0 0 .4em}h5{margin:.8em 0 .3em;font-size:.9rem}
header{padding:18px 0 6px}nav{position:sticky;top:0;background:var(--bg);padding:8px 0;display:flex;gap:8px;overflow-x:auto;z-index:5;border-bottom:1px solid var(--line)}
nav a,.chip{white-space:nowrap;padding:5px 11px;border:1px solid var(--line);border-radius:99px;color:var(--ink);text-decoration:none;font-size:.85rem;background:var(--card)}
.muted{color:var(--mut)}.small{font-size:.82rem}a{color:var(--acc)}section{margin:0}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;margin:10px 0;overflow:hidden}
.card>summary{list-style:none;cursor:pointer;padding:12px 14px;display:grid;grid-template-columns:28px 1fr auto;grid-template-areas:"rk nm px" "rk sub sc" "rk bd bd";gap:2px 10px;align-items:center}
.card>summary::-webkit-details-marker{display:none}.rk{grid-area:rk;font-weight:700;color:var(--mut);align-self:start;padding-top:3px}.nm{grid-area:nm;line-height:1.25}.nm small{display:block;color:var(--mut);font-size:.78rem}
.px{grid-area:px;text-align:right;white-space:nowrap;font-weight:600}.px em{display:block;font-style:normal;font-size:.82rem}.up{color:var(--up)}.dn{color:var(--dn)}
.sc{grid-area:sc;text-align:right}.sc b{font-size:1.25rem}.sc small{display:block;font-size:.7rem;color:var(--mut)}.sub{grid-area:sub;color:var(--mut);font-size:.82rem}
.badge{grid-area:bd;justify-self:start;font-size:.75rem;padding:2px 9px;border-radius:99px;font-weight:600}.badge.good{background:var(--goodbg);color:var(--good)}.badge.mid{background:var(--midbg);color:var(--mid)}.badge.bad{background:var(--badbg);color:var(--bad)}
h4 .badge{font-size:.72rem;margin-left:6px;vertical-align:middle}.warn{color:var(--mid)}
.body{padding:2px 14px 14px;border-top:1px solid var(--line)}.body section{margin-top:14px}
.chart{width:100%;height:auto}.chart .ln{fill:none;stroke:var(--acc);stroke-width:1.6}.chart .area{fill:var(--area)}.chart .grid{stroke:var(--line)}.chart .ax{fill:var(--mut);font-size:10px}
.chart .hi{stroke:var(--hi);stroke-dasharray:4 4;fill:var(--hi)}.chart .tg{stroke:var(--tg);stroke-dasharray:4 4;fill:var(--tg)}.chart .lb{font-size:10px;stroke:none}.chart .dot{fill:var(--acc)}
.range{width:100%;max-width:420px;height:auto}.range .trk{stroke:var(--mut);stroke-width:3;stroke-linecap:round}.range .tick{stroke:var(--mut)}.range .ax{fill:var(--mut);font-size:9.5px}.range .mean{fill:var(--tg)}.range .px{fill:var(--acc)}
.stack{display:flex;height:14px;border-radius:7px;overflow:hidden;margin:6px 0}.c1{background:#0d7a43}.c2{background:#5bbf83}.c3{background:#c9ced6}.c4{background:#e58b82}.c5{background:#b42318}
.stack span,.lg i{display:block}.legend{font-size:.8rem;display:flex;flex-wrap:wrap;gap:4px 12px;margin-bottom:6px}.lg i{display:inline-block;width:9px;height:9px;border-radius:2px;margin-right:4px}
table{border-collapse:collapse;width:100%}.tbl th,.tbl td,.mini th,.mini td{padding:6px 8px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}.tbl th,.mini th{font-size:.78rem;color:var(--mut);font-weight:600}
.mini{font-size:.82rem;margin:6px 0}.mini td,.mini th{padding:4px 6px}.perf td{font-weight:600}.scroll{overflow-x:auto}.tbl{font-size:.88rem;min-width:520px}
.crit td{padding:6px 6px;border-bottom:1px solid var(--line);vertical-align:top}.crit td:first-child{width:26px;text-align:center}.ok{color:var(--good);font-weight:700}.no{color:var(--bad);font-weight:700}
.kv{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:8px}.kv div{background:var(--bg);border-radius:8px;padding:7px 9px}.kv span{display:block;font-size:.74rem;color:var(--mut)}.kv b{font-size:.95rem}
.news{padding-left:18px;margin:0}.news li{margin:5px 0}.sent{padding-left:18px}.sent li{margin:6px 0}
details.inner{margin-top:8px}details.inner>summary{cursor:pointer;font-size:.85rem;color:var(--acc)}
.t{border-bottom:1px dotted var(--mut);cursor:help;position:relative}.t.open::after,.t:hover::after{content:attr(data-tip);position:absolute;left:0;top:1.5em;z-index:20;width:min(280px,80vw);background:var(--ink);color:var(--bg);padding:8px 10px;border-radius:8px;font-size:.78rem;line-height:1.4;font-weight:400;box-shadow:0 4px 14px rgba(0,0,0,.25)}
.stale{background:var(--badbg);color:var(--bad);padding:9px 12px;border-radius:8px;margin:10px 0;font-weight:600}
.lead{background:var(--card);border:1px solid var(--line);border-left:4px solid var(--acc);padding:10px 14px;border-radius:8px}
@media (max-width:520px){.card>summary{grid-template-columns:24px 1fr auto}.tbl{font-size:.82rem}}
"""

JS = """(function(){var a=document.body.getAttribute('data-asof'),b=document.getElementById('stale');if(a&&b&&(Date.now()-Date.parse(a))/864e5>4){b.hidden=false}})();document.addEventListener('click',function(e){var t=e.target.closest('.t');document.querySelectorAll('.t.open').forEach(function(x){if(x!==t)x.classList.remove('open')});if(t){t.classList.toggle('open')}});"""


def build_page(ctx):
    asof = ctx["asof"]
    top, watch = ctx["top"], ctx["watch"]
    uni, info, det, news, ins, hist = ctx["uni"], ctx["info"], ctx["details"], ctx["news"], ctx["insiders"], ctx["hist"]
    prices, fx = ctx["prices"], ctx["fx"]
    now = pd.Timestamp.now(tz="Europe/Berlin")

    def cards(frame, kind, start=1):
        out = []
        for n, (tk, r) in enumerate(frame.iterrows(), start):
            real = ctx["realism"][tk]
            out.append(card(n, tk, r, uni, info.get(tk), det.get(tk), news.get(tk), ins.get(tk), hist.get(tk), real, prices, fx, kind))
        return "".join(out)

    n_pass = len(top)
    short = ""
    if n_pass < CFG["n_top"]:
        short = (f'<p class="lead">Heute erfüllen nur <b>{n_pass}</b> Aktien alle vier Filter (Plätze: {CFG["n_top"]}). Die Liste wird bewusst nicht aufgefüllt. '
                 f'Aktien, die einen Filter knapp verfehlen, stehen darunter in der Beobachtungsliste.</p>')
    counts = ctx["counts"]
    funnel = (f'<p class="muted small">Trichter heute: {counts["universe"]} Aktien in der Liste → {counts["data"]} mit Kursdaten → {counts["liquid"]} handelbar (Kurs, Umsatz) '
              f'→ {counts["dd"]} mit mind. {int(CFG["min_dd"] * 100)} % Abstand zum Hoch → {counts["pass"]} bestehen alle vier Filter.</p>')
    tops = (f'<section id="top"><h2>Top-Kandidaten des Tages ({n_pass})</h2>{short}{funnel}'
            f'<p class="muted small">Sortiert nach {T("Punktwert", "score")}. Tippe auf eine Zeile für Kursverlauf, Analysten, Kennzahlen und Nachrichten.</p>{cards(top, "top")}</section>')
    watchs = (f'<section id="beobachtung"><h2>Beobachtungsliste ({len(watch)})</h2><p class="muted small">Aktien, die höchstens einen Filter verfehlen, nach Punktwert. '
              f'Das Fehlende steht jeweils in der Zeile.</p>{cards(watch, "watch", n_pass + 1)}</section>')

    nav = ('<nav><a href="#markt">Markt</a><a href="#aenderungen">Änderungen</a><a href="#top">Top</a><a href="#beobachtung">Beobachtung</a>'
           '<a href="#bilanz">Bilanz</a><a href="#rueckblick">Rückblick</a><a href="#quellen">Quellen</a></nav>')
    head = (f'<header><h1>Mein Aktien-Radar</h1><p class="muted">Datenstand: Schlusskurse vom {asof.strftime("%d.%m.%Y")} · erstellt {now.strftime("%d.%m.%Y %H:%M")} Uhr (Berlin)<br>'
            f'Ziel: Aktien mit Analysten-Kaufempfehlung, deutlich unter dem Hoch, mit Chance auf +20 % in {CFG["horizon"]} Handelstagen (ca. 4 Wochen). Keine Anlageberatung.</p></header>')
    doc = (f'<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
           f'<title>Mein Aktien-Radar</title><style>{CSS}</style></head><body data-asof="{asof.strftime("%Y-%m-%d")}"><main>{head}'
           f'<div id="stale" class="stale" hidden>Achtung: Die Daten sind älter als 4 Tage. Der tägliche Lauf hat vermutlich nicht funktioniert.</div>{nav}'
           f'{section_market(ctx["market"])}{section_changes(ctx["diff"], ctx["names"])}{tops}{watchs}'
           f'{section_bilanz(ctx["picks"], ctx["picks_summary"])}{section_backtest(ctx["market"]["backtest"])}{section_sources(ctx["source_status"], ctx["notes"])}'
           f'</main><script>{JS}</script></body></html>')
    return doc
