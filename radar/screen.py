"""Auswahlregeln, Punktwert und +20-%-Einschaetzung."""
import numpy as np
import pandas as pd

from .config import CFG
from .metrics import ann_vol, forward_outcomes, rsi, touch_prob


def price_metrics(prices, cfg=CFG):
    """Stufe A: Kennzahlen aller Aktien, nur aus Kursdaten. Eine Zeile pro Ticker."""
    c, h, o, v = prices["Close"], prices["High"], prices["Open"], prices["Volume"]
    n = len(c)
    hi52 = h.iloc[-252:].max()
    last = c.iloc[-1]
    r = rsi(c)
    sma = {k: c.rolling(k).mean().iloc[-1] for k in (20, 50, 200)}
    rows = pd.DataFrame({
        "price": last,
        "prev_close": c.iloc[-2],
        "hi52": hi52,
        "lo52": prices["Low"].iloc[-252:].min(),
        "dd": 1 - last / hi52,
        "sma20": sma[20], "sma50": sma[50], "sma200": sma[200],
        "rsi": r.iloc[-1],
        "rsi_min10": r.iloc[-10:].min(),
        "rsi_prev": r.iloc[-2],
        "ret5": last / c.iloc[-6] - 1,
        "ret20": last / c.iloc[-21] - 1,
        "ret60": last / c.iloc[-61] - 1 if n > 61 else np.nan,
        "ret120": last / c.iloc[-121] - 1 if n > 121 else np.nan,
        "ret250": last / c.iloc[-251] - 1 if n > 251 else np.nan,
        "turnover20": (c * v).iloc[-20:].mean(),
        "vol": ann_vol(c).iloc[-1],
        "bars": c.iloc[-252:].notna().sum(),
    })
    rows["day_chg"] = rows["price"] / rows["prev_close"] - 1
    rows["f_liquid_price"] = (rows["price"] >= cfg["min_price"]) & (rows["turnover20"] >= cfg["min_turnover"]) & (
        rows["bars"] >= 240)
    rows["recovery"] = (rows["price"] > rows["sma20"]) | ((rows["rsi_min10"] < 30) & (rows["rsi"] > rows["rsi_prev"]))
    rows["model_prob"] = rows["vol"].map(lambda s: touch_prob(s, cfg["target"], cfg["horizon"]))
    return rows


def history_hit_rate(prices, tickers, years=5, cfg=CFG):
    """Wie oft erreichte die Aktie in den letzten `years` Jahren innerhalb des Fensters +20 % (Start: jeder Handelstag)."""
    out = {}
    tickers = list(dict.fromkeys(tickers))  # Duplikate entfernen
    c, o = prices["Close"], prices["Open"]
    cut = c.index[-1] - pd.DateOffset(years=years)
    fo = forward_outcomes(o[tickers], c[tickers], cfg["horizon"], cfg["target"])
    hit = fo["hit"].loc[cut:]
    mg, re_ = fo["min_gain"].loc[cut:], fo["ret_end"].loc[cut:]
    for t in tickers:
        s = hit[t].dropna()
        ok = len(s) > 100
        out[t] = {"freq": float(s.mean()) if ok else None, "days": int(len(s)),
                  "hits": int(s.sum()) if len(s) else 0,
                  "loss10": float((mg[t].dropna() <= -0.10).mean()) if ok else None,
                  "worst_end": float(re_[t].dropna().min()) if ok else None,
                  "median_end": float(re_[t].dropna().median()) if ok else None}
    return out


def evaluate(rows, info, cfg=CFG):
    """Stufe B: Analystendaten dazu, Filter und Punktwert berechnen."""
    df = rows.copy()
    for k in ["mcap", "rec", "n_an", "t_mean", "t_med", "t_low", "t_high"]:
        df[k] = np.nan
    for t, i in info.items():
        if not i or t not in df.index:
            continue
        df.loc[t, "mcap"] = i.get("marketCap") or np.nan
        df.loc[t, "rec"] = i.get("recommendationMean") or np.nan
        df.loc[t, "n_an"] = i.get("numberOfAnalystOpinions") or np.nan
        df.loc[t, "t_mean"] = i.get("targetMeanPrice") or np.nan
        df.loc[t, "t_med"] = i.get("targetMedianPrice") or np.nan
        df.loc[t, "t_low"] = i.get("targetLowPrice") or np.nan
        df.loc[t, "t_high"] = i.get("targetHighPrice") or np.nan
    df["upside"] = df["t_mean"] / df["price"] - 1
    # Unplausible Kursziele (z. B. Waehrungs-Mismatch) nicht fuer Filter/Punkte verwenden
    df["target_suspect"] = (df["upside"] > 1.5) | (df["upside"] < -0.8)
    df.loc[df["target_suspect"], "upside"] = np.nan

    df["f1"] = df["f_liquid_price"] & (df["mcap"] >= cfg["min_mcap"])
    df["f2"] = (df["n_an"] >= cfg["min_analysts"]) & (df["rec"] <= cfg["max_rec"]) & (df["upside"] >= cfg["min_upside"])
    df["f3"] = df["dd"] >= cfg["min_dd"]
    df["f4"] = df["recovery"]
    df["passed"] = df[["f1", "f2", "f3", "f4"]].all(axis=1)
    df["n_fail"] = 4 - df[["f1", "f2", "f3", "f4"]].sum(axis=1)

    def fails(r):
        names = {"f1": "Handelbarkeit/Größe", "f2": "Analysten", "f3": "Abstand zum Hoch", "f4": "Erholungssignal"}
        return [names[k] for k in ("f1", "f2", "f3", "f4") if not r[k]]

    df["fail_list"] = df.apply(fails, axis=1)

    w = cfg["weights"]
    cl = lambda x: np.clip(x, 0, 1)  # noqa: E731
    c_up = cl(df["upside"] / 0.6)
    c_depth = cl((df["dd"] - cfg["loose_dd"]) / 0.35)
    c_cons = cl((3 - df["rec"]) / 2) * (0.5 + 0.5 * np.minimum(df["n_an"], 20) / 20)
    c_rec = (0.4 * (df["price"] > df["sma20"]) + 0.3 * ((df["rsi_min10"] < 35) & (df["rsi"] > df["rsi_prev"]))
             + 0.3 * (df["ret5"] > 0)).astype(float)
    c_vol = cl(df["model_prob"].astype(float) / 0.30)
    df["c_upside"], df["c_depth"], df["c_cons"], df["c_rec"], df["c_vol"] = c_up, c_depth, c_cons, c_rec, c_vol
    df["score"] = 100 * (w["upside"] * c_up.fillna(0) + w["depth"] * c_depth.fillna(0) + w["consensus"] * c_cons.fillna(0)
                         + w["recovery"] * c_rec.fillna(0) + w["vol"] * c_vol.fillna(0))
    return df


def realism(row, hist):
    """Vier Kriterien -> Einstufung. Schwellen sind vorlaeufig (Kalibrierung durch Backtest)."""
    crit = {
        "model": (row["model_prob"] is not None and row["model_prob"] >= 0.10),
        "history": (hist is not None and hist["freq"] is not None and hist["freq"] >= 0.10),
        "target": bool(pd.notna(row["upside"]) and row["upside"] >= 0.20),
        "room": bool((row["hi52"] / row["price"] - 1) >= 0.20),
    }
    n = sum(crit.values())
    label = "realistisch" if n == 4 else "möglich" if n == 3 else "unwahrscheinlich"
    return {"criteria": crit, "met": n, "label": label}


def select(df, cfg=CFG):
    """Top-N (alle vier Filter bestanden, nach Punktwert), danach Beobachtungsliste (knapp gescheitert)."""
    ok = df[df["passed"]].sort_values("score", ascending=False)
    top = ok.head(cfg["n_top"])
    rest = df[~df.index.isin(top.index) & df["f1"] & df["dd"].ge(cfg["loose_dd"])]
    # `rest` enthaelt schon die Aktien, die alle Filter bestehen, aber nicht mehr in die Top-N passen (n_fail == 0)
    watch_pool = rest[rest["n_fail"] <= 1].sort_values("score", ascending=False)
    watch = watch_pool.head(cfg["n_watch"])
    assert not watch.index.duplicated().any() and not set(watch.index) & set(top.index)
    return top, watch
