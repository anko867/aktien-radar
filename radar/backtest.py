"""Backtest der Kursregeln (Filter 1, 3, 4). Die Analystenregel (Filter 2) ist mit Gratis-Daten nicht testbar."""
import math

import numpy as np
import pandas as pd

from .config import CFG
from .metrics import ann_vol, forward_outcomes, rsi


def decluster(mask, gap):
    """Pro Aktie hoechstens ein Signal je `gap` Handelstage (sonst zaehlt dieselbe Situation mehrfach)."""
    arr = mask.to_numpy()
    out = np.zeros_like(arr, dtype=bool)
    for j in range(arr.shape[1]):
        i, n = 0, arr.shape[0]
        col = arr[:, j]
        while i < n:
            if col[i]:
                out[i, j] = True
                i += gap
            else:
                i += 1
    return pd.DataFrame(out, index=mask.index, columns=mask.columns)


def rowmask(mask, series_bool):
    """Maske zusaetzlich auf bestimmte Handelstage (Zeilen) beschraenken."""
    return mask.mul(series_bool.astype(int).to_numpy(), axis=0).astype(bool)


def _stats(fo, mask):
    sel = pd.concat({k: fo[k].where(mask).stack() for k in ("hit", "ret_end", "max_gain", "min_gain")}, axis=1)
    sel = sel.dropna(subset=["hit"]).astype(float)
    n = len(sel)
    if n == 0:
        return {"n": 0}
    sel = {k: sel[k] for k in sel.columns}
    return {
        "n": int(n),
        "hit_rate": float(sel["hit"].mean()),
        "ret_end_mean": float(sel["ret_end"].mean()),
        "ret_end_median": float(sel["ret_end"].median()),
        "ret_end_p10": float(sel["ret_end"].quantile(0.10)),
        "ret_end_worst": float(sel["ret_end"].min()),
        "min_gain_mean": float(sel["min_gain"].mean()),
        "share_end_positive": float((sel["ret_end"] > 0).mean()),
    }


def run(prices, index_close, cfg=CFG):
    c, h, o, v = prices["Close"], prices["High"], prices["Open"], prices["Volume"]
    hz, tg = cfg["horizon"], cfg["target"]
    hi = h.rolling(252, min_periods=240).max()
    dd = 1 - c / hi
    sma20 = c.rolling(20).mean()
    r = rsi(c)
    rec = (c > sma20) | ((r.rolling(10).min() < 30) & (r > r.shift(1)))
    liquid = (c >= cfg["min_price"]) & ((c * v).rolling(20).mean() >= cfg["min_turnover"]) & hi.notna()
    vol = ann_vol(c)
    fo = forward_outcomes(o, c, hz, tg)
    valid = fo["hit"].notna()

    m_base = liquid & valid
    m_dd = decluster(liquid & valid & (dd >= cfg["min_dd"]), hz)
    m_sig = decluster(liquid & valid & (dd >= cfg["min_dd"]) & rec, hz)
    m_rand = decluster(m_base, hz)  # zufaellige Tage mit gleicher Behandlung

    res = {
        "asof": str(c.index[-1].date()),
        "period": [str(c.index[252].date()), str(fo["hit"].dropna(how="all").index[-1].date())],
        "n_tickers": int(c.shape[1]),
        "horizon": hz, "target": tg,
        "rules": {"min_dd": cfg["min_dd"], "min_price": cfg["min_price"], "min_turnover": cfg["min_turnover"]},
        "baseline_all": _stats(fo, m_rand),
        "dd_only": _stats(fo, m_dd),
        "signal": _stats(fo, m_sig),
    }

    # Nach Jahr und Zeitraum
    yrs = pd.Series(c.index.year, index=c.index)
    by_year = {}
    for y in sorted(set(c.index.year)):
        yr = _stats(fo, rowmask(m_sig, yrs == y))
        if yr["n"] >= 20:
            yr["baseline_hit_rate"] = _stats(fo, rowmask(m_rand, yrs == y)).get("hit_rate")
            by_year[str(y)] = yr
    res["by_year"] = by_year
    res["without_2020"] = _stats(fo, rowmask(m_sig, yrs != 2020))
    res["old_period"] = _stats(fo, rowmask(m_sig, yrs <= 2021))
    res["new_period"] = _stats(fo, rowmask(m_sig, yrs >= 2022))

    # Marktlage zum Signaltag: Index selbst >= 10 % unter seinem 52-Wochen-Hoch?
    ic = index_close.reindex(c.index).ffill()
    idd = 1 - ic / ic.rolling(252, min_periods=200).max()
    weak = (idd >= 0.10) & idd.notna()
    res["market_weak"] = _stats(fo, rowmask(m_sig, weak))
    res["market_calm"] = _stats(fo, rowmask(m_sig, ~weak & idd.notna()))
    res["baseline_market_weak"] = _stats(fo, rowmask(m_rand, weak))
    res["baseline_market_calm"] = _stats(fo, rowmask(m_rand, ~weak & idd.notna()))
    res["baseline_without_2020"] = _stats(fo, rowmask(m_rand, yrs != 2020))
    res["market_weak_share_of_days"] = float(weak[idd.notna()].mean())

    # Kalibrierung des Zufallsmodells: steigt die Trefferquote mit der Modellchance?
    z = np.log(1 + tg) / (vol * np.sqrt(hz / 252))
    prob = pd.DataFrame(np.vectorize(math.erfc)(z.to_numpy() / math.sqrt(2)), index=vol.index, columns=vol.columns)
    calib = {}
    for lo, hi_, label in [(0, .05, "unter 5 %"), (.05, .10, "5 bis 10 %"), (.10, .20, "10 bis 20 %"), (.20, 1.01, "über 20 %")]:
        bm = m_sig & ((prob >= lo) & (prob < hi_))
        st = _stats(fo, bm)
        if st["n"] >= 10:
            st["avg_model_prob"] = float(prob.where(bm).stack().dropna().mean())
            calib[label] = st
    res["calibration"] = calib

    # Der Index selbst als Vergleich: wie oft +20 % in 20 Handelstagen?
    io = index_close  # nur Schlusskurse vorhanden -> Einstieg zum Schlusskurs als Naeherung
    fmax = io.rolling(hz).max().shift(-hz)
    ih = (fmax >= io * (1 + tg)).where(fmax.notna())
    res["index_hit_rate"] = float(ih.dropna().mean())
    res["n_signal_days"] = int(m_sig.any(axis=1).sum())
    return res
