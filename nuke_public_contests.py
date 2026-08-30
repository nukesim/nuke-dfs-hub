import pandas as pd

from nuke_contest_validation import parse_dk_lineup, normalize_results, normalize_ownership

PUBLIC_CONTESTS = {
    "2017 DK archive · contest 43293784": {
        "contest_id": "43293784",
        "url": "https://raw.githubusercontent.com/rogerfitz/tutorials/master/draft_kings_contests_scrape/data/contest-standings-43293784.csv",
        "source": "rogerfitz/tutorials",
    },
    "2017 DK archive · contest 43299739 (large)": {
        "contest_id": "43299739",
        "url": "https://raw.githubusercontent.com/rogerfitz/tutorials/master/draft_kings_contests_scrape/data/contest-standings-43299739.csv",
        "source": "rogerfitz/tutorials",
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
    """Convert an old DraftKings combined standings export into NUKE validation tables.

    Older DK standings CSVs put entry results in the left-hand columns and the
    contest ownership table in the right-hand columns of the same file.
    """
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
        # These archived standings files do not preserve payout amounts.
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
