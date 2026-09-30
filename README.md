# Mein Aktien-Radar

Täglich aktualisierte Webseite mit Aktien-Kandidaten (Analysten-Kaufempfehlung, deutlich unter dem Hoch,
Chance auf +20 % in ca. 4 Wochen). Keine Anlageberatung.

## Ablauf eines Laufs (`run_daily.py`)
1. Aktienlisten (S&P 500, Nasdaq-100, DAX, MDAX) von Wikipedia laden
2. Kurse (Yahoo Finance) für alle Aktien holen
3. Kursfilter, dann Analystendaten nur für Kandidaten
4. Auswahl: alle vier Filter bestanden, sortiert nach Punktwert (Top 15); knapp Gescheiterte kommen in die Beobachtungsliste
5. Verlauf (`data/snapshots`), Bilanz (`data/picks.json`) fortschreiben, Seite nach `docs/index.html` schreiben

`run_backtest.py` testet die Kursregeln mit ca. 10 Jahren Kursdaten (Ergebnis `data/backtest.json`).

## Lokal ausprobieren
```
pip install -r requirements.txt
python run_daily.py        # ca. 1-3 Minuten, schreibt docs/index.html
python run_backtest.py     # ca. 2-5 Minuten
```

## Schwellen ändern
Alle Startwerte stehen in `radar/config.py`.

## Automatik
`.github/workflows/daily.yml` startet `run_daily.py` Dienstag bis Samstag gegen 7 Uhr deutscher Zeit und speichert
das Ergebnis im Repository. GitHub Pages veröffentlicht den Ordner `docs/`.
Optionales Secret `SEC_CONTACT` (Kontakt-E-Mail), damit die SEC-Insiderdaten abgerufen werden dürfen.
