import math
import numpy as np
import pandas as pd

DK_SLOTS = ["QB", "RB1", "RB2", "WR1", "WR2", "WR3", "TE", "FLEX", "DST"]


def _norm_pos(v):
    p = str(v).upper().strip()
    if p in {"D", "DEF", "DST"}:
        return "DST"
    return p.split("/")[0]


def prepare_slate(df):
    x = df.copy()
    aliases = {
        "Name": ["Name", "name", "Player", "player", "Name + ID"],
        "Position": ["Position", "position", "Pos", "pos"],
        "Salary": ["Salary", "salary"],
        "Team": ["TeamAbbrev", "Team", "team", "team_abbrev"],
        "Game": ["Game Info", "Game", "game", "game_info"],
        "ID": ["ID", "Id", "id", "player_id"],
    }
    out = pd.DataFrame(index=x.index)
    for target, opts in aliases.items():
        col = next((c for c in opts if c in x.columns), None)
        out[target] = x[col] if col else ""
    out["Name"] = out["Name"].astype(str).str.replace(r"\s*\(\d+\)\s*$", "", regex=True)
    out["Position"] = out["Position"].map(_norm_pos)
    out["Salary"] = pd.to_numeric(out["Salary"], errors="coerce").fillna(0).astype(int)
    out["Team"] = out["Team"].astype(str).str.upper().str.strip()
    out["Game"] = out["Game"].astype(str)
    out["ID"] = out["ID"].astype(str)
    out = out[out["Position"].isin(["QB", "RB", "WR", "TE", "DST"]) & (out["Salary"] > 0)].reset_index(drop=True)
    out["market_score"] = out.groupby("Position")["Salary"].rank(pct=True).fillna(.5)
    return out


def _sample_points(row, rng, mode="NUKEM"):
    salary = float(row.Salary)
    pos = row.Position
    base = {"QB": 13.0, "RB": 8.0, "WR": 7.0, "TE": 5.0, "DST": 5.5}[pos]
    slope = {"QB": .00115, "RB": .00155, "WR": .00145, "TE": .00135, "DST": .00055}[pos]
    mean = base + max(0, salary - 2500) * slope
    sigma = {"QB": 6.2, "RB": 7.2, "WR": 7.8, "TE": 6.5, "DST": 5.5}[pos]
    if mode == "NUKEM":
        # Heavy-tailed outcome model: salary is a market/depth signal, not a fantasy projection.
        boom = rng.random() < (.06 + .12 * float(row.market_score))
        if boom:
            mean += rng.gamma(2.2, 4.0)
        if rng.random() < .055:
            mean *= rng.uniform(.05, .45)
    return max(-4.0 if pos == "DST" else 0.0, rng.normal(mean, sigma))


def simulate_player_matrix(players, n_sims=1500, seed=26, mode="NUKEM"):
    rng = np.random.default_rng(seed)
    n = len(players)
    mat = np.zeros((n_sims, n), dtype=np.float32)
    game_keys = players["Game"].fillna("").astype(str).tolist()
    team_keys = players["Team"].fillna("").astype(str).tolist()
    unique_games = sorted(set(game_keys))
    for s in range(n_sims):
        game_factor = {g: rng.normal(0, 2.8) for g in unique_games}
        team_factor = {t: rng.normal(0, 1.8) for t in set(team_keys)}
        for i, row in enumerate(players.itertuples(index=False)):
            pts = _sample_points(row, rng, mode)
            # Shared game/team shocks create useful correlation without hard-coded projections.
            if row.Position != "DST":
                pts += .55 * game_factor.get(row.Game, 0) + .35 * team_factor.get(row.Team, 0)
            else:
                pts -= .25 * game_factor.get(row.Game, 0)
            mat[s, i] = max(-6 if row.Position == "DST" else 0, pts)
    return mat


def _valid_lineup(indices, p, min_salary, max_salary=50000):
    if len(indices) != 9 or len(set(indices)) != 9:
        return False
    rows = p.iloc[indices]
    sal = int(rows.Salary.sum())
    if sal < min_salary or sal > max_salary:
        return False
    counts = rows.Position.value_counts().to_dict()
    return counts.get("QB", 0) == 1 and counts.get("RB", 0) >= 2 and counts.get("WR", 0) >= 3 and counts.get("TE", 0) >= 1 and counts.get("DST", 0) == 1


def generate_lineups(players, n_lineups=600, min_salary=49400, seed=26):
    rng = np.random.default_rng(seed)
    p = players.reset_index(drop=True)
    pools = {pos: p.index[p.Position.eq(pos)].to_numpy() for pos in ["QB", "RB", "WR", "TE", "DST"]}
    flex = p.index[p.Position.isin(["RB", "WR", "TE"])].to_numpy()
    seen, result = set(), []
    attempts = 0
    target_attempts = max(25000, n_lineups * 120)
    while len(result) < n_lineups and attempts < target_attempts:
        attempts += 1
        if any(len(pools[k]) == 0 for k in pools):
            break
        chosen = [int(rng.choice(pools["QB"]))]
        chosen += list(map(int, rng.choice(pools["RB"], 2, replace=False)))
        chosen += list(map(int, rng.choice(pools["WR"], 3, replace=False)))
        chosen += [int(rng.choice(pools["TE"]))]
        chosen += [int(rng.choice(pools["DST"]))]
        available_flex = np.array([i for i in flex if i not in chosen], dtype=int)
        if len(available_flex) == 0:
            continue
        # Bias flex toward stronger salary-market signal while retaining randomness.
        weights = (.25 + p.loc[available_flex, "market_score"].to_numpy()) ** 2
        weights = weights / weights.sum()
        chosen += [int(rng.choice(available_flex, p=weights))]
        key = tuple(sorted(chosen))
        if key in seen or not _valid_lineup(chosen, p, min_salary):
            continue
        seen.add(key)
        result.append(chosen)
    return result


def _stack_label(rows):
    qb = rows[rows.Position.eq("QB")]
    if qb.empty:
        return "NO QB"
    team = qb.iloc[0].Team
    game = qb.iloc[0].Game
    mates = rows[(rows.Team.eq(team)) & (rows.Position.isin(["WR", "TE"]))]
    opp = rows[(rows.Game.eq(game)) & (~rows.Team.eq(team)) & (rows.Position.ne("DST"))]
    return f"QB + {len(mates)} / {len(opp)}"


def evaluate_lineups(players, lineups, player_matrix):
    if not lineups:
        return pd.DataFrame()
    scores = np.stack([player_matrix[:, lu].sum(axis=1) for lu in lineups], axis=1)
    thresholds = np.quantile(scores, [.50, .90, .99], axis=0)
    rows = []
    for j, lu in enumerate(lineups):
        roster = players.iloc[lu]
        s = scores[:, j]
        q99 = float(thresholds[2, j])
        top1 = float((s >= q99).mean() * 100)
        salary = int(roster.Salary.sum())
        rows.append({
            "Rank": 0,
            "NUKE Score": round(float(np.mean(s) + .65*np.std(s) + .25*np.quantile(s,.95)), 2),
            "Median": round(float(np.median(s)), 2),
            "Ceiling 95": round(float(np.quantile(s, .95)), 2),
            "Top 1% Rate": round(top1, 2),
            "Salary": salary,
            "Stack": _stack_label(roster),
            "QB": " / ".join(roster.loc[roster.Position.eq("QB"), "Name"].tolist()),
            "RB": " / ".join(roster.loc[roster.Position.eq("RB"), "Name"].tolist()),
            "WR": " / ".join(roster.loc[roster.Position.eq("WR"), "Name"].tolist()),
            "TE": " / ".join(roster.loc[roster.Position.eq("TE"), "Name"].tolist()),
            "DST": " / ".join(roster.loc[roster.Position.eq("DST"), "Name"].tolist()),
            "_indices": lu,
        })
    out = pd.DataFrame(rows).sort_values(["NUKE Score", "Ceiling 95"], ascending=False).reset_index(drop=True)
    out["Rank"] = np.arange(1, len(out)+1)
    return out


def exposure_table(players, results, top_n=50):
    if results.empty:
        return pd.DataFrame()
    sample = results.head(min(top_n, len(results)))
    counts = {}
    for lu in sample["_indices"]:
        for idx in lu:
            counts[idx] = counts.get(idx, 0) + 1
    rows = []
    denom = len(sample)
    for idx, count in counts.items():
        r = players.iloc[idx]
        rows.append({"Player": r.Name, "Pos": r.Position, "Team": r.Team, "Salary": int(r.Salary), "Exposure %": round(100*count/denom,1)})
    return pd.DataFrame(rows).sort_values(["Exposure %", "Salary"], ascending=[False, False]).reset_index(drop=True)
