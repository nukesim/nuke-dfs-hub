import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

YEAR = int(os.environ.get("NFL_SEASON", "2026"))
WEEK = int(os.environ.get("NFL_WEEK", "1"))
KEY = os.environ.get("FANTASYPROS_API_KEY", "").strip()
OUT = Path("data/nfl_availability_current.csv")

if not KEY:
    raise SystemExit("FANTASYPROS_API_KEY is not configured")

params = urlencode({"year": YEAR, "week": WEEK, "include_probabilities": "true"})
url = f"https://api.fantasypros.com/public/v2/json/nfl/injuries?{params}"
req = Request(url, headers={"x-api-key": KEY, "User-Agent": "NUKE-DFS-Hub/1.0"})
with urlopen(req, timeout=30) as resp:
    payload = json.load(resp)

rows = []
now = datetime.now(timezone.utc).isoformat(timespec="seconds")
for r in payload.get("injuries", []):
    practice = " / ".join(str(r.get(k) or "") for k in ("practice_1", "practice_2", "practice_3") if r.get(k))
    rows.append({
        "player_id": r.get("player_id", ""),
        "name": r.get("name", ""),
        "team": r.get("team_id", ""),
        "status": r.get("status", ""),
        "status_short": r.get("status_short", ""),
        "practice": practice,
        "probability_of_playing": r.get("probability_of_playing", ""),
        "comment": r.get("comment", ""),
        "injury_type": r.get("injury_type", ""),
        "injury_update_date": r.get("injury_update_date", ""),
        "updated": now,
    })

OUT.parent.mkdir(parents=True, exist_ok=True)
with OUT.open("w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["player_id","name","team","status","status_short","practice","probability_of_playing","comment","injury_type","injury_update_date","updated"])
    w.writeheader(); w.writerows(rows)
print(f"Wrote {len(rows)} NFL availability rows to {OUT}")
