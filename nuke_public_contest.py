import pandas as pd

PUBLIC_CONTESTS = {
    "2017 preseason · NFL $60K Front Four · 15,060 entries · ID 43299739": {
        "url": "https://raw.githubusercontent.com/rogerfitz/tutorials/master/draft_kings_contests_scrape/data/contest-standings-43299739.csv",
        "source": "rogerfitz/tutorials",
        "contest_id": "43299739",
        "name": "NFL $60K Front Four (Preseason)",
        "date": "2017-08-11",
        "entry_fee": 4.0,
        "advertised_prizes": 60000.0,
        "season_type": "preseason",
        "note": "Large preserved DraftKings preseason field. Excellent for contest structure, ownership, duplication, and rank-distribution validation. Do not use it as evidence that the regular-season Football Engine V2.1 is calibrated for preseason football.",
    },
    "2017 preseason · NFL $1K Safety · 588 entries · ID 43293784": {
        "url": "https://raw.githubusercontent.com/rogerfitz/tutorials/master/draft_kings_contests_scrape/data/contest-standings-43293784.csv",
        "source": "rogerfitz/tutorials",
        "contest_id": "43293784",
        "name": "NFL $1K Safety (Preseason)",
        "date": "2017-08-11",
        "entry_fee": 2.0,
        "advertised_prizes": 1000.0,
        "season_type": "preseason",
        "note": "Small preserved DraftKings preseason field, retained as a parser/diagnostic sample.",
    },
}


def available_public_contests():
    return list(PUBLIC_CONTESTS)


def load_public_contest(label):
    meta = PUBLIC_CONTESTS[label]
    raw = pd.read_csv(meta["url"], encoding="utf-8-sig")
    entries = raw.loc[raw["Lineup"].notna(), [c for c in ["Rank","EntryId","EntryName","Points","Lineup"] if c in raw.columns]].copy()
    entries["Rank"] = pd.to_numeric(entries.get("Rank"), errors="coerce")
    entries["Points"] = pd.to_numeric(entries.get("Points"), errors="coerce")
    entries = entries.dropna(subset=["Points","Lineup"]).reset_index(drop=True)

    ownership = raw.loc[raw["Player"].notna(), [c for c in ["Player","%Drafted","FPTS"] if c in raw.columns]].copy()
    ownership["Actual Ownership %"] = pd.to_numeric(ownership.get("%Drafted", "").astype(str).str.replace("%","",regex=False), errors="coerce")
    ownership["Actual DKFP"] = pd.to_numeric(ownership.get("FPTS"), errors="coerce")
    ownership = ownership[["Player","Actual Ownership %","Actual DKFP"]].dropna(subset=["Player"]).reset_index(drop=True)
    return entries, ownership, meta
