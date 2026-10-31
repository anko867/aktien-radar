"""Vorab-Check fuer geplante Laeufe: Gibt True aus, wenn der Lauf uebersprungen werden kann.

Ein Lauf ist noetig, wenn
  1. die Daten noch nicht auf dem Stand des letzten abgeschlossenen US-Handelstags sind, oder
  2. beim letzten Lauf noch Aktien ohne Tageskurs waren (Yahoo schliesst die deutschen Tagesdaten erst gegen 08:45 UTC
     ab) und der letzte Lauf vor 09:05 UTC lag, jetzt aber 09:05 UTC schon vorbei ist (einmaliger Nachlauf pro Tag).
An US-Feiertagen gibt es nie ein True fuer Punkt 1, dann laufen alle Versuche, das ist harmlos."""
import datetime as dt
import json
import zoneinfo

def can_skip(j, now_utc):
    """True, wenn dieser Versuch uebersprungen werden kann. j = Inhalt von data/latest.json."""
    ny = now_utc.astimezone(zoneinfo.ZoneInfo("America/New_York"))
    day = ny.date() if ny.hour + ny.minute / 60 >= 17.5 else ny.date() - dt.timedelta(days=1)
    while day.weekday() >= 5:  # Samstag/Sonntag -> Freitag
        day -= dt.timedelta(days=1)
    if j.get("asof") != day.isoformat():
        return False
    if j.get("stale_count", 0) > 0 and j.get("run_utc"):
        last = dt.datetime.strptime(j["run_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
        cutoff = now_utc.replace(hour=9, minute=5, second=0, microsecond=0)
        if now_utc >= cutoff and last < cutoff:
            return False
    return True


if __name__ == "__main__":
    try:
        with open("data/latest.json", encoding="utf-8") as f:
            print(can_skip(json.load(f), dt.datetime.now(dt.timezone.utc)))
    except Exception:  # noqa: BLE001
        print(False)
