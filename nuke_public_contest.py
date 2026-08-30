import io
import pandas as pd

PUBLIC_CONTESTS = {
    "2017 public DraftKings NFL contest · ID 43293784": {
        "url": "https://raw.githubusercontent.com/rogerfitz/tutorials/master/draft_kings_contests_scrape/data/contest-standings-43293784.csv",
        "source": "rogerfitz/tutorials",
        "contest_id": "43293784",
        "note": "Archived DraftKings NFL contest-standings export. This is a small historical contest and is useful for validating lineup/ownership parsing and scoring behavior; it is not representative of a modern large-field Milly Maker.",
    }
}


def available_public_contests():
    return list(PUBLIC_CONTESTS)


def load_public_contest(label):
    meta = PUBLIC_CONTESTS[label]
    raw = pd.read_csv(meta["url"], encoding="utf-8-sig")
    # DraftKings contest exports combine entry rows and player ownership rows in one CSV.
    entries = raw.loc[raw["Lineup"].notna(), [c for c in ["Rank","EntryId","EntryName","Points","Lineup"] if c in raw.columns]].copy()
    entries["Rank"] = pd.to_numeric(entries.get("Rank"), errors="coerce")
    entries["Points"] = pd.to_numeric(entries.get("Points"), errors="coerce")
    entries = entries.dropna(subset=["Points","Lineup"]).reset_index(drop=True)

    ownership = raw.loc[raw["Player"].notna(), [c for c in ["Player","%Drafted","FPTS"] if c in raw.columns]].copy()
    ownership["Actual Ownership %"] = pd.to_numeric(ownership.get("%Drafted", "").astype(str).str.replace("%","",regex=False), errors="coerce")
    ownership["Actual DKFP"] = pd.to_numeric(ownership.get("FPTS"), errors="coerce")
    ownership = ownership.rename(columns={"Player":"Player"})[["Player","Actual Ownership %","Actual DKFP"]].dropna(subset=["Player"]).reset_index(drop=True)
    return entries, ownership, meta
