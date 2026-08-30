from pathlib import Path
import pandas as pd

CURRENT_PATH = Path("data/nfl_odds_current.csv")
HISTORY_PATH = Path("data/nfl_odds_history.csv")


def _read_csv(path):
    try:
        if path.exists() and path.stat().st_size > 0:
            return pd.read_csv(path)
    except Exception:
        pass
    return pd.DataFrame()


def load_current_odds():
    df = _read_csv(CURRENT_PATH)
    if df.empty:
        return df
    for col in ["Spread", "Game Total", "Team Total", "Book Count", "Credits Remaining", "Credits Used", "Credits Last"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def load_odds_history():
    df = _read_csv(HISTORY_PATH)
    if df.empty:
        return df
    for col in ["Spread", "Game Total", "Team Total", "Book Count"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    if "Snapshot UTC" in df.columns:
        df["Snapshot UTC"] = pd.to_datetime(df["Snapshot UTC"], utc=True, errors="coerce")
    return df


def odds_status(current):
    if current is None or current.empty:
        return {"available": False}
    snap = current.get("Snapshot UTC", pd.Series(dtype=str)).dropna()
    remaining = pd.to_numeric(current.get("Credits Remaining", pd.Series(dtype=float)), errors="coerce").dropna()
    return {
        "available": True,
        "snapshot": str(snap.iloc[0]) if len(snap) else "",
        "credits_remaining": int(remaining.iloc[0]) if len(remaining) else None,
        "games": int(current.get("Event ID", pd.Series(dtype=str)).nunique()) if "Event ID" in current.columns else 0,
    }


def movement_for_game(history, teams):
    if history is None or history.empty or not teams or len(teams) < 2:
        return pd.DataFrame()
    a, b = str(teams[0]), str(teams[1])
    h = history[
        history["Team"].astype(str).isin([a, b])
        & history["Opponent"].astype(str).isin([a, b])
    ].copy()
    if h.empty:
        return pd.DataFrame()
    h = h.dropna(subset=["Snapshot UTC"]).sort_values("Snapshot UTC")
    if h.empty:
        return pd.DataFrame()

    game_total = h.groupby("Snapshot UTC", as_index=False)["Game Total"].median()
    tt = h.pivot_table(index="Snapshot UTC", columns="Team", values="Team Total", aggfunc="median").reset_index()
    spread = h.pivot_table(index="Snapshot UTC", columns="Team", values="Spread", aggfunc="median").reset_index()
    out = game_total.merge(tt, on="Snapshot UTC", how="left", suffixes=("", "_tt"))
    rename_tt = {}
    for team in [a, b]:
        if team in out.columns:
            rename_tt[team] = f"{team} Team Total"
    out = out.rename(columns=rename_tt)
    spread = spread.rename(columns={team: f"{team} Spread" for team in [a, b] if team in spread.columns})
    out = out.merge(spread, on="Snapshot UTC", how="left")
    out = out.rename(columns={"Snapshot UTC": "Timestamp"})
    return out.sort_values("Timestamp").reset_index(drop=True)
