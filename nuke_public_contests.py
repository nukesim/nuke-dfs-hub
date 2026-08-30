import pandas as pd

from nuke_contest_validation import parse_dk_lineup, normalize_results, normalize_ownership

PUBLIC_CONTESTS = {
    "2017 preseason · NFL $60K Front Four · 15,060 entries · ID 43299739": {
        "contest_id": "43299739",
        "url": "https://raw.githubusercontent.com/rogerfitz/tutorials/master/draft_kings_contests_scrape/data/contest-standings-43299739.csv",
        "source": "rogerfitz/tutorials",
        "name": "NFL $60K Front Four (Preseason)",
        "date": "2017-08-11",
        "entry_fee": 4.0,
        "advertised_prizes": 60000.0,
        "season_type": "preseason",
        "v21_eligible": False,
    },
    "2017 preseason · NFL $1K Safety · 588 entries · ID 43293784": {
        "contest_id": "43293784",
        "url": "https://raw.githubusercontent.com/rogerfitz/tutorials/master/draft_kings_contests_scrape/data/contest-standings-43293784.csv",
        "source": "rogerfitz/tutorials",
        "name": "NFL $1K Safety (Preseason)",
        "date": "2017-08-11",
        "entry_fee": 2.0,
        "advertised_prizes": 1000.0,
        "season_type": "preseason",
        "v21_eligible": False,
    },
}


def _position_map_from_lineups(lineups):
    votes = {}
    for lineup in lineups.dropna().astype(str):
        for slot, name in parse_dk_lineup(lineup):
            if slot == "FLEX":
                continue
            votes.setdefault(name, {})[slot] = votes.setdefault(name, {}).get(slot, 0) + 1
    out = {}
    for name, counts in votes.items():
        out[name] = max(counts, key=counts.get)
    return out


def parse_combined_standings(raw, contest_id):
    d = raw.copy()
    d.columns = [str(c).strip().lstrip("\ufeff") for c in d.columns]
    required = {"Rank", "EntryId", "Points", "Lineup"}
    missing = required - set(d.columns)
    if missing:
        raise ValueError(f"Public standings archive missing columns: {sorted(missing)}")

    results = pd.DataFrame({
        "contest_id": str(contest_id),
        "place": pd.to_numeric(d["Rank"], errors="coerce"),
        "entry_id": d["EntryId"],
        "points": pd.to_numeric(d["Points"], errors="coerce"),
        "lineup": d["Lineup"],
        "payout": 0.0,
    })
    results = results[results["place"].notna() & results["points"].notna()].copy()
    results = normalize_results(results)

    ownership = pd.DataFrame()
    player_col = next((c for c in d.columns if c.lower() == "player"), None)
    drafted_col = next((c for c in d.columns if c.lower() == "%drafted"), None)
    fpts_col = next((c for c in d.columns if c.lower() == "fpts"), None)
    if player_col and drafted_col:
        pos_map = _position_map_from_lineups(results["lineup"])
        o = pd.DataFrame({
            "contest_id": str(contest_id),
            "player": d[player_col],
            "drafted": d[drafted_col].astype(str).str.replace("%", "", regex=False),
            "points": d[fpts_col] if fpts_col else pd.NA,
        })
        o = o[o["player"].notna() & o["drafted"].notna()].copy()
        o["pos"] = o["player"].astype(str).str.strip().map(pos_map).fillna("UNK")
        ownership = normalize_ownership(o[["contest_id", "player", "pos", "drafted", "points"]])
    return results, ownership


def load_public_contest(label):
    cfg = PUBLIC_CONTESTS[label]
    raw = pd.read_csv(cfg["url"])
    results, ownership = parse_combined_standings(raw, cfg["contest_id"])
    return results, ownership, cfg
