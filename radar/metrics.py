"""Kennzahlen aus Kursdaten: Schwankung, RSI, Zufallsmodell, Vorwaertsergebnisse."""
import math

import numpy as np
import pandas as pd


def phi(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def touch_prob(sigma, target=0.20, days=20):
    """Zufallsmodell ohne Trend: Chance, dass der Kurs innerhalb von `days` Handelstagen mind. einmal
    `target` ueber dem Start liegt (Spiegelungsprinzip). sigma = Schwankung pro Jahr (z. B. 0.4)."""
    if sigma is None or not np.isfinite(sigma) or sigma <= 0:
        return None
    s = sigma * math.sqrt(days / 252)
    return 2 * (1 - phi(math.log(1 + target) / s))


def rsi(close, n=14):
    d = close.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    rs = up / dn
    return 100 - 100 / (1 + rs)


def ann_vol(close, n=252):
    return np.log(close).diff().rolling(n, min_periods=n // 2).std() * math.sqrt(252)


def forward_outcomes(open_, close, horizon=20, target=0.20):
    """Fuer jeden Signaltag t (Schlusskurs bekannt): Einstieg = Eroeffnung t+1, Fenster = Schlusskurse t+1..t+horizon.
    Liefert DataFrames gleicher Form wie `close`."""
    entry = open_.shift(-1)
    fmax = close.rolling(horizon).max().shift(-horizon)
    fmin = close.rolling(horizon).min().shift(-horizon)
    end = close.shift(-horizon)
    valid = entry.notna() & fmax.notna() & (entry > 0)
    return {
        "entry": entry,
        "hit": ((fmax >= entry * (1 + target)) & valid).astype(float).where(valid),
        "ret_end": (end / entry - 1).where(valid),
        "max_gain": (fmax / entry - 1).where(valid),
        "min_gain": (fmin / entry - 1).where(valid),
    }


def pct(x, nd=1):
    return None if x is None or not np.isfinite(x) else round(float(x) * 100, nd)
