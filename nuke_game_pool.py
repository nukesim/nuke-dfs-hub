import numpy as np
import pandas as pd


BOOST_LABELS = {
    -3.0: "-3 HARD FADE",
    -2.0: "-2 FADE",
    -1.0: "-1 LESS",
    0.0: "0 NEUTRAL",
    1.0: "+1 LIKE",
    2.0: "+2 LOVE",
    3.0: "+3 FLAG PLANT",
}


def _market_team_score(players):
    """Projection-free team strength score using DK salary/role market information."""
    p = players.copy()
    p["_pos_rank"] = p.groupby(["Team", "Position"])["Salary"].rank(method="first", ascending=False)
    weights = {
        ("QB", 1): 1.30,
        ("RB", 1): 1.00,
        ("RB", 2): 0.45,
        ("WR", 1): 1.00,
        ("WR", 2): 0.70,
        ("WR", 3): 0.40,
        ("TE", 1): 0.55,
    }
    p["_w"] = [weights.get((str(pos), int(rank)), 0.0) for pos, rank in zip(p.Position, p._pos_rank)]
    p["_v"] = p["Salary"].astype(float) * p["_w"]
    score = p.groupby("Team")["_v"].sum()
    if score.empty:
        return score
    lo, hi = float(score.min()), float(score.max())
    if hi <= lo:
        return pd.Series(0.5, index=score.index)
    return (score - lo) / (hi - lo)


def game_environment(players):
    """Build projection-free game/team environment table.

    Totals are market-implied proxies derived only from DraftKings salary/role information,
    not sportsbook lines. They are intentionally labeled as estimates in the SIM UI.
    """
    if players is None or players.empty:
        return pd.DataFrame()

    p = players.copy().reset_index(drop=True)
    team_strength = _market_team_score(p)
    teams = sorted([t for t in p.Team.dropna().astype(str).unique() if t])
    team_total = {t: 19.5 + 8.0 * float(team_strength.get(t, 0.5)) for t in teams}

    rows = []
    for game, g in p.groupby("Game", sort=False):
        game_teams = list(dict.fromkeys(g.Team.astype(str).tolist()))
        if len(game_teams) < 2:
            continue
        a, b = game_teams[0], game_teams[1]
        gt = float(team_total.get(a, 23.5) + team_total.get(b, 23.5))
        for team, opp in [(a, b), (b, a)]:
            rows.append({
                "Game": str(game),
                "Team": team,
                "Opponent": opp,
                "Team Total": round(float(team_total.get(team, 23.5)), 1),
                "Game Total": round(gt, 1),
            })

    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out["Team Total Rank"] = out["Team Total"].rank(method="min", ascending=False).astype(int)
    game_rank = out.groupby("Game")["Game Total"].first().rank(method="min", ascending=False).astype(int)
    out["Game Total Rank"] = out["Game"].map(game_rank).astype(int)
    return out


def rank_background(value, max_rank):
    """Return red->yellow->green background for rank 1..N."""
    try:
        rank = float(value)
        n = max(1.0, float(max_rank))
    except Exception:
        return ""
    pct = 1.0 - (rank - 1.0) / max(1.0, n - 1.0)
    if pct >= 0.67:
        return "background-color: rgba(25,195,125,.35); color: white; font-weight: 800"
    if pct >= 0.34:
        return "background-color: rgba(242,201,76,.28); color: white; font-weight: 800"
    return "background-color: rgba(255,93,93,.30); color: white; font-weight: 800"


def style_environment(df):
    if df is None or df.empty:
        return df
    max_team = int(df["Team Total Rank"].max()) if "Team Total Rank" in df else 1
    max_game = int(df["Game Total Rank"].max()) if "Game Total Rank" in df else 1
    return df.style.map(lambda v: rank_background(v, max_team), subset=["Team Total Rank"]).map(
        lambda v: rank_background(v, max_game), subset=["Game Total Rank"]
    )
