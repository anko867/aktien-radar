"""Zentrale Einstellungen. Alle Schwellen sind Startwerte (siehe Umsetzungsplan)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DOCS = ROOT / "docs"
CACHE = ROOT / "cache"

UA = {"User-Agent": "Mozilla/5.0 (AktienRadar private research project)"}

CFG = {
    # Filter 1: Handelbarkeit (in Landeswaehrung der Aktie)
    "min_price": 5.0,
    "min_turnover": 10e6,  # durchschnittlicher Tagesumsatz der letzten 20 Handelstage
    "min_mcap": 2e9,
    # Filter 2: Analysten
    "min_analysts": 10,
    "max_rec": 2.0,  # 1 = Strong Buy ... 5 = Sell
    "min_upside": 0.25,  # mittleres Kursziel mind. 25 % ueber Kurs
    # Filter 3: Abstand zum 52-Wochen-Hoch
    "min_dd": 0.25,
    "loose_dd": 0.15,  # ab hier werden Analystendaten geholt (fuer Beobachtungsliste)
    # Ziel
    "target": 0.20,
    "horizon": 20,  # Handelstage (ca. 4 Wochen)
    "n_top": 15,
    "n_watch": 25,
    "hist_years": 5,
    # Score-Gewichte
    "weights": {"upside": 0.25, "depth": 0.20, "consensus": 0.20, "recovery": 0.20, "vol": 0.15},
}
