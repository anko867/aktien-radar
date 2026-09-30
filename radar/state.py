"""Gedaechtnis des Radars: Tagesauswahl, Vergleich mit gestern, Bilanz der Empfehlungen."""
import json

import pandas as pd

from .config import CFG, DATA

PICKS = DATA / "picks.json"
SNAP_DIR = DATA / "snapshots"


# ---------------------------------------------------------------- Tagesauswahl / Vergleich
def previous_snapshot(asof):
    files = sorted(p for p in SNAP_DIR.glob("*.json") if p.stem < str(asof.date()))
    return json.loads(files[-1].read_text(encoding="utf-8")) if files else None


def save_snapshot(asof, top, watch, df):
    SNAP_DIR.mkdir(parents=True, exist_ok=True)
    snap = {
        "asof": str(asof.date()),
        "top": list(top.index),
        "watch": list(watch.index),
        "score": {t: round(float(df.loc[t, "score"]), 1) for t in list(top.index) + list(watch.index)},
    }
    (SNAP_DIR / f"{asof.date()}.json").write_text(json.dumps(snap, ensure_ascii=False, indent=1), encoding="utf-8")
    return snap


def diff_with_previous(prev, top, watch, df, names):
    """Was ist seit dem letzten Lauf neu in der Top-Liste, was ist herausgefallen (und warum)?"""
    if not prev:
        return None
    new_top = [t for t in top.index if t not in prev["top"]]
    dropped = []
    for t in prev["top"]:
        if t in top.index:
            continue
        if t not in df.index:
            why = "keine Kursdaten mehr"
        else:
            r = df.loc[t]
            if r["passed"]:
                why = "Platz außerhalb der Top-Liste"
            else:
                why = "Filter nicht mehr erfüllt: " + ", ".join(r["fail_list"])
        dropped.append({"ticker": t, "name": names.get(t, t), "why": why})
    return {
        "prev_date": prev["asof"],
        "new_top": new_top,
        "dropped": dropped,
        "new_watch": [t for t in watch.index if t not in prev["watch"] and t not in prev["top"]],
        "left_watch": [t for t in prev["watch"] if t not in watch.index and t not in top.index],
    }


# ---------------------------------------------------------------- Bilanz
def load_picks():
    return json.loads(PICKS.read_text(encoding="utf-8")) if PICKS.exists() else []


def add_new_picks(picks, top, asof, names, df):
    open_tickers = {p["ticker"] for p in picks if p["status"] != "abgeschlossen"}
    for t in top.index:
        if t in open_tickers:
            continue
        picks.append({
            "ticker": t, "name": names.get(t, t), "signal_date": str(asof.date()),
            "score": round(float(df.loc[t, "score"]), 1), "price_at_signal": round(float(df.loc[t, "price"]), 4),
            "entry_date": None, "entry_open": None, "status": "wartet", "days": 0,
            "hit": False, "hit_date": None, "days_to_hit": None,
            "last_gain": None, "max_gain": None, "min_gain": None, "sp_gain": None,
        })
    return picks


def update_picks(picks, prices, index_close, cfg=CFG):
    """Wertet alle offenen Empfehlungen mit den aktuellen Kursen aus (Fenster = 20 Handelstage ab Einstieg)."""
    c, o = prices["Close"], prices["Open"]
    hz, tg = cfg["horizon"], cfg["target"]
    for p in picks:
        if p["status"] == "abgeschlossen" or p["ticker"] not in c.columns:
            continue
        sig = pd.Timestamp(p["signal_date"])
        after = c.index[c.index > sig]
        if len(after) == 0:
            p["status"] = "wartet"
            continue
        entry_day = after[0]
        entry = float(o.loc[entry_day, p["ticker"]])
        p["entry_date"], p["entry_open"] = str(entry_day.date()), round(entry, 4)
        win = c.loc[entry_day:, p["ticker"]].iloc[:hz].dropna()
        gains = win / entry - 1
        p["days"] = int(len(win))
        p["last_gain"] = float(gains.iloc[-1])
        p["max_gain"] = float(gains.max())
        p["min_gain"] = float(gains.min())
        hits = gains[gains >= tg]
        p["hit"] = bool(len(hits))
        if p["hit"]:
            p["hit_date"] = str(hits.index[0].date())
            p["days_to_hit"] = int(list(win.index).index(hits.index[0]) + 1)
        ic = index_close.reindex(c.index).ffill()
        p["sp_gain"] = float(ic.loc[win.index[-1]] / ic.loc[sig] - 1)
        p["status"] = "abgeschlossen" if len(win) >= hz else "läuft"
    return picks


def summarize(picks):
    done = [p for p in picks if p["status"] == "abgeschlossen"]
    running = [p for p in picks if p["status"] == "läuft"]
    waiting = [p for p in picks if p["status"] == "wartet"]
    s = {"total": len(picks), "done": len(done), "running": len(running), "waiting": len(waiting)}
    if done:
        s["hits"] = sum(p["hit"] for p in done)
        s["hit_rate"] = s["hits"] / len(done)
        s["avg_end"] = sum(p["last_gain"] for p in done) / len(done)
        s["avg_sp"] = sum(p["sp_gain"] for p in done) / len(done)
        s["worst_end"] = min(p["last_gain"] for p in done)
        s["avg_min"] = sum(p["min_gain"] for p in done) / len(done)
    s["running_hits"] = sum(p["hit"] for p in running)
    return s


def save_picks(picks):
    PICKS.write_text(json.dumps(picks, ensure_ascii=False, indent=1), encoding="utf-8")
