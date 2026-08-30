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
    p = players.copy()
    p["_pos_rank"] = p.groupby(["Team", "Position"])["Salary"].rank(method="first", ascending=False)
    weights = {("QB",1):1.30,("RB",1):1.00,("RB",2):0.45,("WR",1):1.00,("WR",2):0.70,("WR",3):0.40,("TE",1):0.55}
    p["_w"] = [weights.get((str(pos), int(rank)), 0.0) for pos, rank in zip(p.Position, p._pos_rank)]
    p["_v"] = p["Salary"].astype(float) * p["_w"]
    score = p.groupby("Team")["_v"].sum()
    if score.empty:
        return score
    lo, hi = float(score.min()), float(score.max())
    if hi <= lo:
        return pd.Series(0.5, index=score.index)
    return (score - lo) / (hi - lo)


def _sportsbook_row(odds, team, opp):
    if odds is None or odds.empty or "Team" not in odds.columns or "Opponent" not in odds.columns:
        return None
    m = odds[odds["Team"].astype(str).eq(str(team)) & odds["Opponent"].astype(str).eq(str(opp))].copy()
    if m.empty:
        return None
    if "Snapshot UTC" in m.columns:
        m["_snapshot"] = pd.to_datetime(m["Snapshot UTC"], utc=True, errors="coerce")
        m = m.sort_values("_snapshot", ascending=False)
    return m.iloc[0]


def game_environment(players, odds=None):
    """Use sportsbook consensus when available; otherwise use the DK salary-market fallback."""
    if players is None or players.empty:
        return pd.DataFrame()
    p = players.copy().reset_index(drop=True)
    team_strength = _market_team_score(p)
    teams = sorted([t for t in p.Team.dropna().astype(str).unique() if t])
    fallback_total = {t: 19.5 + 8.0 * float(team_strength.get(t, 0.5)) for t in teams}
    rows = []
    for game, g in p.groupby("Game", sort=False):
        game_teams = list(dict.fromkeys(g.Team.astype(str).tolist()))
        if len(game_teams) < 2:
            continue
        a, b = game_teams[0], game_teams[1]
        oa, ob = _sportsbook_row(odds, a, b), _sportsbook_row(odds, b, a)
        have_book = oa is not None and ob is not None
        fallback_gt = float(fallback_total.get(a, 23.5) + fallback_total.get(b, 23.5))
        for team, opp, orow in [(a,b,oa),(b,a,ob)]:
            if have_book and orow is not None:
                team_total = float(pd.to_numeric(orow.get("Team Total"), errors="coerce"))
                game_total = float(pd.to_numeric(orow.get("Game Total"), errors="coerce"))
                spread = float(pd.to_numeric(orow.get("Spread"), errors="coerce"))
                books_val = pd.to_numeric(orow.get("Book Count", 0), errors="coerce")
                books = int(books_val) if pd.notna(books_val) else 0
                updated = str(orow.get("Snapshot UTC", ""))
                source = "Sportsbook Consensus"
            else:
                team_total, game_total, spread, books, updated, source = float(fallback_total.get(team,23.5)), fallback_gt, np.nan, 0, "", "DK Salary Estimate"
            rows.append({"Game":str(game),"Team":team,"Opponent":opp,"Spread":spread,"Team Total":round(team_total,1),"Game Total":round(game_total,1),"Books":books,"Source":source,"Last Update":updated})
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out["Team Total Rank"] = out["Team Total"].rank(method="min", ascending=False).astype(int)
    game_rank = out.groupby("Game")["Game Total"].first().rank(method="min", ascending=False).astype(int)
    out["Game Total Rank"] = out["Game"].map(game_rank).astype(int)
    return out


def rank_background(value, max_rank=None):
    try:
        rank = int(float(value))
    except Exception:
        return ""
    if rank <= 3:
        return "background-color: rgba(25,195,125,.35); color: white; font-weight: 800"
    if rank <= 7:
        return "background-color: rgba(242,201,76,.28); color: white; font-weight: 800"
    return "background-color: rgba(255,93,93,.30); color: white; font-weight: 800"


def style_environment(df, slate_max_team_rank=None, slate_max_game_rank=None):
    if df is None or df.empty:
        return df
    fmt = {"Team Total":"{:.1f}","Game Total":"{:.1f}","Spread":"{:+.1f}"}
    fmt = {k:v for k,v in fmt.items() if k in df.columns}
    styled = df.style.format(fmt, na_rep="—")
    if "Team Total Rank" in df.columns:
        styled = styled.map(rank_background, subset=["Team Total Rank"])
    if "Game Total Rank" in df.columns:
        styled = styled.map(rank_background, subset=["Game Total Rank"])
    return styled
