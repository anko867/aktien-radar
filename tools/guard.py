"""Vorab-Check fuer geplante Laeufe: Sind die Daten schon auf dem Stand des letzten abgeschlossenen US-Handelstags?
Gibt True aus, wenn ja (dann kann der Lauf uebersprungen werden). An US-Feiertagen gibt es nie ein True, dann
laufen alle Versuche, das ist harmlos."""
import datetime as dt
import json
import zoneinfo

ny = dt.datetime.now(zoneinfo.ZoneInfo("America/New_York"))
day = ny.date() if ny.hour + ny.minute / 60 >= 17.5 else ny.date() - dt.timedelta(days=1)
while day.weekday() >= 5:  # Samstag/Sonntag -> Freitag
    day -= dt.timedelta(days=1)
try:
    with open("data/latest.json", encoding="utf-8") as f:
        print(json.load(f).get("asof") == day.isoformat())
except Exception:  # noqa: BLE001
    print(False)
