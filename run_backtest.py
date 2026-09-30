"""Backtest der Kursregeln ueber ca. 10 Jahre. Ergebnis: data/backtest.json"""
import json
import sys

import pandas as pd
import yfinance as yf

from radar import backtest, data, universe
from radar.config import DATA

use_cache = "--cache" in sys.argv
uni, notes = universe.build()
prices = data.download_prices(list(uni), "11y", use_cache=use_cache)
prices, asof = data.trim_to_asof(prices)
idx = yf.download("^GSPC", period="11y", interval="1d", auto_adjust=True, progress=False)["Close"].squeeze()
idx.index = idx.index.tz_localize(None) if idx.index.tz is not None else idx.index
res = backtest.run(prices, idx.loc[:asof])
(DATA / "backtest.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(res, ensure_ascii=False, indent=1))
