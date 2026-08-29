import numpy as np
import pandas as pd

DK_SLOTS = ["QB", "RB1", "RB2", "WR1", "WR2", "WR3", "TE", "FLEX", "DST"]

ROLE_ADJUST = {
    "AUTO": 0.00,
    "QB1": 0.08,
    "RB1": 0.18,
    "RB2": -0.05,
    "RB3": -0.18,
    "WR1": 0.14,
    "WR2": 0.04,
    "WR3": -0.07,
    "TE1": 0.12,
    "BACKUP": -0.20,
}

INACTIVE_STATUSES = {"OUT", "IR", "INACTIVE", "SUSPENDED"}


def _norm_pos(v):
    p = str(v).upper().strip()
    if p in {"D", "DEF", "DST"}:
        return "DST"
    return p.split("/")[0]


def prepare_slate(df):
    x = df.copy()
    aliases = {
        "Name": ["Name", "name", "Player", "player", "Name + ID"],
        "Position": ["Position", "position", "Pos", "pos", "Roster Position"],
        "Salary": ["Salary", "salary"],
        "Team": ["TeamAbbrev", "Team", "team", "team_abbrev"],
        "Game": ["Game Info", "Game", "game", "game_info", "game_id", "Game ID"],
        "ID": ["ID", "Id", "id", "player_id"],
        "Status": ["Status", "status", "Injury Status", "injury_status"],
    }
    out = pd.DataFrame(index=x.index)
    for target, opts in aliases.items():
        col = next((c for c in opts if c in x.columns), None)
        out[target] = x[col] if col else ""
    out["Name"] = out["Name"].fillna("").astype(str).str.replace(r"\s*\(\d+\)\s*$", "", regex=True)
    out["Position"] = out["Position"].map(_norm_pos)
    out["Salary"] = pd.to_numeric(out["Salary"], errors="coerce").fillna(0).astype(int)
    out["Team"] = out["Team"].fillna("").astype(str).str.upper().str.strip()
    out["Game"] = out["Game"].fillna("").astype(str).str.strip()
    out["ID"] = out["ID"].fillna("").astype(str)
    out["Status"] = out["Status"].fillna("").astype(str).str.upper().str.strip()
    out = out[out["Position"].isin(["QB", "RB", "WR", "TE", "DST"]) & (out["Salary"] > 0)].reset_index(drop=True)
    out = out[~out["Status"].isin(INACTIVE_STATUSES)].reset_index(drop=True)
    out["market_score"] = out.groupby("Position")["Salary"].rank(pct=True).fillna(.5)
    out["role_override"] = "AUTO"
    out["usage_multiplier"] = 1.0
    return out


def _sample_points(row, rng, mode="NUKEM"):
    salary = float(row.Salary)
    pos = row.Position
    base = {"QB": 13.0, "RB": 8.0, "WR": 7.0, "TE": 5.0, "DST": 5.5}[pos]
    slope = {"QB": .00115, "RB": .00155, "WR": .00145, "TE": .00135, "DST": .00055}[pos]
    mean = base + max(0, salary - 2500) * slope
    sigma = {"QB": 6.2, "RB": 7.2, "WR": 7.8, "TE": 6.5, "DST": 5.5}[pos]

    usage = float(getattr(row, "usage_multiplier", 1.0) or 1.0)
    usage = float(np.clip(usage, 0.25, 2.25))
    role = str(getattr(row, "role_override", "AUTO") or "AUTO").upper().strip()
    role_adj = ROLE_ADJUST.get(role, 0.0)

    if pos != "DST":
        mean *= usage * (1.0 + role_adj)
        sigma *= float(np.clip(np.sqrt(usage), .70, 1.45))

    if mode == "NUKEM":
        market = float(getattr(row, "market_score", .5))
        boom_prob = .06 + .12 * market
        if role in {"RB1", "WR1", "TE1", "QB1"}:
            boom_prob += .03
        boom_prob *= float(np.clip(.8 + .2 * usage, .65, 1.30))
        if rng.random() < min(.32, boom_prob):
            mean += rng.gamma(2.2, 4.0) * float(np.clip(usage, .7, 1.5))
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
    unique_teams = sorted(set(team_keys))

    for s in range(n_sims):
        game_factor = {g: rng.normal(0, 2.8) for g in unique_games}
        team_factor = {t: rng.normal(0, 1.8) for t in unique_teams}
        for i, row in enumerate(players.itertuples(index=False)):
            pts = _sample_points(row, rng, mode)
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
    return (
        counts.get("QB", 0) == 1
        and counts.get("RB", 0) >= 2
        and counts.get("WR", 0) >= 3
        and counts.get("TE", 0) >= 1
        and counts.get("DST", 0) == 1
    )


def generate_lineups(players, n_lineups=600, min_salary=49400, seed=26):
    """Generate legal DK lineups with at least one QB pass-catcher stack."""
    rng = np.random.default_rng(seed)
    p = players.reset_index(drop=True)
    if p.empty:
        return []

    pos_arr = p["Position"].astype(str).to_numpy()
    team_arr = p["Team"].astype(str).to_numpy()
    salaries = p["Salary"].to_numpy(int)
    market = p["market_score"].to_numpy(float)
    usage = p["usage_multiplier"].to_numpy(float) if "usage_multiplier" in p.columns else np.ones(len(p))
    roles = p["role_override"].astype(str).str.upper().map(ROLE_ADJUST).fillna(0).to_numpy(float) if "role_override" in p.columns else np.zeros(len(p))

    # Moderate market weighting keeps strong players favored without pushing every
    # random lineup over the $50k cap. The previous exponent (6.0) was too steep.
    base_w = np.power(.08 + market, 3.0)
    base_w *= np.clip(usage, .35, 2.25)
    base_w *= np.clip(1.0 + roles, .45, 1.55)
    base_w = np.clip(base_w, 1e-8, None)

    pools = {pos: np.where(pos_arr == pos)[0] for pos in ["QB", "RB", "WR", "TE", "DST"]}
    if any(len(v) == 0 for v in pools.values()):
        return []
    flex = np.where(np.isin(pos_arr, ["RB", "WR", "TE"]))[0]

    pool_probs = {}
    for pos, ids in pools.items():
        w = base_w[ids]
        pool_probs[pos] = w / w.sum()

    qb_mates = {}
    for qb in pools["QB"]:
        ids = np.where((team_arr == team_arr[qb]) & np.isin(pos_arr, ["WR", "TE"]))[0]
        qb_mates[int(qb)] = ids

    seen, result = set(), []
    attempts = 0
    target_attempts = max(30000, int(n_lineups) * 180)

    while len(result) < int(n_lineups) and attempts < target_attempts:
        attempts += 1
        qb = int(rng.choice(pools["QB"], p=pool_probs["QB"]))
        mates = qb_mates.get(qb, np.array([], dtype=int))
        if len(mates) == 0:
            continue
        mw = base_w[mates]
        mw = mw / mw.sum()
        mate = int(rng.choice(mates, p=mw))
        chosen = [qb, mate]

        need = {
            "RB": 2,
            "WR": 3 - (1 if pos_arr[mate] == "WR" else 0),
            "TE": 1 - (1 if pos_arr[mate] == "TE" else 0),
            "DST": 1,
        }
        failed = False
        for pos, count in need.items():
            if count <= 0:
                continue
            ids = pools[pos][~np.isin(pools[pos], np.asarray(chosen, dtype=int))]
            if len(ids) < count:
                failed = True
                break
            w = base_w[ids]
            w = w / w.sum()
            chosen += list(map(int, rng.choice(ids, count, replace=False, p=w)))
        if failed:
            continue

        available_flex = flex[~np.isin(flex, np.asarray(chosen, dtype=int))]
        if len(available_flex) == 0:
            continue
        fw = base_w[available_flex]
        fw = fw / fw.sum()
        chosen += [int(rng.choice(available_flex, p=fw))]

        salary = int(salaries[np.asarray(chosen, dtype=int)].sum())
        if salary < int(min_salary) or salary > 50000:
            continue
        key = tuple(sorted(chosen))
        if key in seen:
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
    rows = []
    for j, lu in enumerate(lineups):
        roster = players.iloc[lu]
        s = scores[:, j]
        salary = int(roster.Salary.sum())
        rows.append({
            "Rank": 0,
            "NUKE Score": round(float(np.mean(s) + .65 * np.std(s) + .25 * np.quantile(s, .95)), 2),
            "Median": round(float(np.median(s)), 2),
            "Ceiling 95": round(float(np.quantile(s, .95)), 2),
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
    out["Rank"] = np.arange(1, len(out) + 1)
    return out


def exposure_table(players, results, top_n=50):
    if results is None or results.empty:
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
        rows.append({
            "Player": r.Name,
            "Pos": r.Position,
            "Team": r.Team,
            "Salary": int(r.Salary),
            "Role": getattr(r, "role_override", "AUTO"),
            "Usage x": round(float(getattr(r, "usage_multiplier", 1.0)), 2),
            "Exposure %": round(100 * count / denom, 1),
        })
    return pd.DataFrame(rows).sort_values(["Exposure %", "Salary"], ascending=[False, False]).reset_index(drop=True)
