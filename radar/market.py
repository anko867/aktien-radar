"""Marktlage: Indizes, VIX, Zinsen, Marktbreite aus den eigenen Daten. Nur Fakten und benannte Konventionen."""
import json

import numpy as np
import pandas as pd

from .config import DATA
from .data import INDICES


def _row(s):
    s = s.dropna()
    last = float(s.iloc[-1])
    hi = float(s.iloc[-252:].max())
    return {
        "last": last, "date": str(s.index[-1].date()),
        "chg1d": last / float(s.iloc[-2]) - 1,
        "chg1m": last / float(s.iloc[-22]) - 1 if len(s) > 22 else None,
        "chg3m": last / float(s.iloc[-64]) - 1 if len(s) > 64 else None,
        "dd": 1 - last / hi,
        "above200": bool(last > float(s.iloc[-200:].mean())) if len(s) >= 200 else None,
        "abs1m": last - float(s.iloc[-22]) if len(s) > 22 else None,  # fuer Renditen: Prozentpunkte
    }


def overview(idx_df, rows, fx, asof):
    idx_df = idx_df.copy()
    idx_df.index = idx_df.index.tz_localize(None) if idx_df.index.tz is not None else idx_df.index
    idx_df = idx_df.loc[:asof]
    tbl = {INDICES[k]: _row(idx_df[k]) for k in INDICES if k in idx_df and idx_df[k].notna().sum() > 30}
    vix_s = idx_df["^VIX"].dropna() if "^VIX" in idx_df else None
    vix_pct = float((vix_s.iloc[-252:] < vix_s.iloc[-1]).mean()) if vix_s is not None and len(vix_s) > 100 else None

    liquid = rows[rows["f_liquid_price"]]
    breadth = {
        "n": int(len(liquid)),
        "above200": float((liquid["price"] > liquid["sma200"]).mean()),
        "above50": float((liquid["price"] > liquid["sma50"]).mean()),
        "dd25": float((liquid["dd"] >= 0.25).mean()),
        "near_high": float((liquid["dd"] <= 0.05).mean()),
        "up_today": float((liquid["day_chg"] > 0).mean()),
    }
    sp = tbl.get("S&P 500")
    bt = DATA / "backtest.json"
    bt = json.loads(bt.read_text(encoding="utf-8")) if bt.exists() else None
    return {"asof": str(asof.date()), "table": tbl, "vix_pct": vix_pct, "breadth": breadth, "fx": fx,
            "sp_weak": bool(sp and sp["dd"] >= 0.10), "backtest": bt}


def sentences(m):
    """Kurze Einordnung nur aus Zahlen; Schwellen sind als Konvention gekennzeichnet."""
    out = []
    de = lambda x, d=1: f"{x:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".").replace("-", "−")  # noqa: E731
    sp = m["table"].get("S&P 500")
    if sp:
        trend = "über" if sp["above200"] else "unter"
        out.append(f"Der S&P 500 schloss am {sp['date']} bei {de(sp['last'], 0)} Punkten: {de(sp['dd'] * 100)} % unter "
                   f"seinem 52-Wochen-Hoch, {trend} dem 200-Tage-Durchschnitt, {de(sp['chg1m'] * 100)} % in einem Monat.")
    v = m["table"].get("VIX (Schwankungsindex)")
    if v:
        lvl = "ruhig" if v["last"] < 15 else "normal" if v["last"] < 25 else "erhöht" if v["last"] < 35 else "sehr hoch"
        pc = f" Im letzten Jahr lag der Wert an {de(m['vix_pct'] * 100, 0)} % der Tage darunter." if m["vix_pct"] is not None else ""
        out.append(f"Der VIX steht bei {de(v['last'])}. Nach gängiger Konvention (unter 15 ruhig, 15–25 normal, "
                   f"25–35 erhöht, darüber sehr hoch) gilt das als {lvl}.{pc}")
    b = m["breadth"]
    out.append(f"Marktbreite ({b['n']} handelbare Aktien der Liste): {de(b['above200'] * 100, 0)} % handeln über ihrem "
               f"200-Tage-Durchschnitt, {de(b['near_high'] * 100, 0)} % liegen höchstens 5 % unter ihrem Hoch, "
               f"{de(b['dd25'] * 100, 0)} % liegen mindestens 25 % darunter. Am Datenstand-Tag stiegen "
               f"{de(b['up_today'] * 100, 0)} % der Aktien.")
    y = m["table"].get("Rendite 10-jährige US-Anleihe")
    if y:
        d = y["abs1m"]
        out.append(f"Die 10-jährige US-Staatsanleihe rentiert mit {de(y['last'], 2)} % "
                   f"({'+' if d >= 0 else '−'}{de(abs(d), 2)} Prozentpunkte in einem Monat).")
    bt = m.get("backtest")
    if bt and sp:
        weak = m["sp_weak"]
        out.append(
            f"Für dieses Radar wichtig: Im Backtest lag die Trefferquote der Kursregeln an Tagen mit schwachem Gesamtmarkt "
            f"(S&P 500 mindestens 10 % unter Hoch) bei {de(bt['market_weak']['hit_rate'] * 100)} %, in ruhigen Märkten bei "
            f"{de(bt['market_calm']['hit_rate'] * 100)} %. Heute gilt der Markt als {'schwach' if weak else 'ruhig'}.")
    return out
