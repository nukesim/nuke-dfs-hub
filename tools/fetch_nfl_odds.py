import os
from pathlib import Path
from datetime import datetime, timezone, timedelta
from statistics import median
import requests
import pandas as pd

API_URL = "https://api.the-odds-api.com/v4/sports/americanfootball_nfl/odds"
CURRENT_PATH = Path("data/nfl_odds_current.csv")
HISTORY_PATH = Path("data/nfl_odds_history.csv")

TEAM_ABBR = {
    "Arizona Cardinals":"ARI","Atlanta Falcons":"ATL","Baltimore Ravens":"BAL","Buffalo Bills":"BUF",
    "Carolina Panthers":"CAR","Chicago Bears":"CHI","Cincinnati Bengals":"CIN","Cleveland Browns":"CLE",
    "Dallas Cowboys":"DAL","Denver Broncos":"DEN","Detroit Lions":"DET","Green Bay Packers":"GB",
    "Houston Texans":"HOU","Indianapolis Colts":"IND","Jacksonville Jaguars":"JAX","Kansas City Chiefs":"KC",
    "Las Vegas Raiders":"LV","Los Angeles Chargers":"LAC","Los Angeles Rams":"LAR","Miami Dolphins":"MIA",
    "Minnesota Vikings":"MIN","New England Patriots":"NE","New Orleans Saints":"NO","New York Giants":"NYG",
    "New York Jets":"NYJ","Philadelphia Eagles":"PHI","Pittsburgh Steelers":"PIT","San Francisco 49ers":"SF",
    "Seattle Seahawks":"SEA","Tampa Bay Buccaneers":"TB","Tennessee Titans":"TEN","Washington Commanders":"WAS",
}


def _market(bookmaker, key):
    for m in bookmaker.get("markets", []):
        if m.get("key") == key:
            return m
    return None


def _spread_for_team(market, team_name):
    if not market:
        return None
    for out in market.get("outcomes", []):
        if out.get("name") == team_name and out.get("point") is not None:
            return float(out["point"])
    return None


def _total(market):
    if not market:
        return None
    vals = [float(o["point"]) for o in market.get("outcomes", []) if o.get("name") == "Over" and o.get("point") is not None]
    return vals[0] if vals else None


def fetch():
    api_key = os.getenv("THE_ODDS_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("THE_ODDS_API_KEY is not configured")
    r = requests.get(API_URL, params={
        "apiKey": api_key,
        "regions": "us",
        "markets": "spreads,totals",
        "oddsFormat": "american",
        "dateFormat": "iso",
    }, timeout=30)
    r.raise_for_status()
    data = r.json()
    headers = {
        "Credits Remaining": r.headers.get("x-requests-remaining"),
        "Credits Used": r.headers.get("x-requests-used"),
        "Credits Last": r.headers.get("x-requests-last"),
    }
    snap = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    rows = []
    for event in data:
        home = event.get("home_team")
        away = event.get("away_team")
        if home not in TEAM_ABBR or away not in TEAM_ABBR:
            continue
        spreads = {home: [], away: []}
        totals = []
        books = []
        for book in event.get("bookmakers", []):
            sm = _market(book, "spreads")
            tm = _market(book, "totals")
            hs = _spread_for_team(sm, home)
            aws = _spread_for_team(sm, away)
            gt = _total(tm)
            if hs is not None:
                spreads[home].append(hs)
            if aws is not None:
                spreads[away].append(aws)
            if gt is not None:
                totals.append(gt)
            if hs is not None or aws is not None or gt is not None:
                books.append(str(book.get("title", book.get("key", ""))))
        if not totals:
            continue
        game_total = float(median(totals))
        for team_name, opp_name in [(home, away), (away, home)]:
            if not spreads[team_name]:
                continue
            spread = float(median(spreads[team_name]))
            implied = game_total / 2.0 - spread / 2.0
            row = {
                "Snapshot UTC": snap,
                "Event ID": str(event.get("id", "")),
                "Commence Time UTC": str(event.get("commence_time", "")),
                "Team": TEAM_ABBR[team_name],
                "Opponent": TEAM_ABBR[opp_name],
                "Home/Away": "HOME" if team_name == home else "AWAY",
                "Spread": round(spread, 2),
                "Game Total": round(game_total, 2),
                "Team Total": round(implied, 2),
                "Book Count": len(set(books)),
                "Books": " | ".join(sorted(set(books))),
                **headers,
            }
            rows.append(row)
    return pd.DataFrame(rows)


def persist(df):
    CURRENT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(CURRENT_PATH, index=False)
    if HISTORY_PATH.exists() and HISTORY_PATH.stat().st_size > 0:
        try:
            hist = pd.read_csv(HISTORY_PATH)
        except Exception:
            hist = pd.DataFrame()
    else:
        hist = pd.DataFrame()
    hist = pd.concat([hist, df], ignore_index=True)
    hist = hist.drop_duplicates(subset=["Snapshot UTC", "Event ID", "Team"], keep="last")
    if "Snapshot UTC" in hist.columns:
        ts = pd.to_datetime(hist["Snapshot UTC"], utc=True, errors="coerce")
        cutoff = datetime.now(timezone.utc) - timedelta(days=45)
        hist = hist[ts.ge(cutoff) | ts.isna()].copy()
    hist.to_csv(HISTORY_PATH, index=False)


if __name__ == "__main__":
    frame = fetch()
    if frame.empty:
        print("No NFL odds returned; leaving existing files unchanged.")
    else:
        persist(frame)
        remaining = frame["Credits Remaining"].iloc[0] if "Credits Remaining" in frame else "?"
        print(f"Saved {len(frame)} team rows across {frame['Event ID'].nunique()} games. Credits remaining: {remaining}")
