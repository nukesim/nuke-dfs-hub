from collections import Counter

import numpy as np
import pandas as pd

from nuke_showdown import SHOWDOWN_SALARY_CAP

SCRIPT_NAMES = ["Balanced", "Shootout", "Low Scoring", "Team A Controls", "Team B Controls", "Passing Spike", "Rushing Control", "Chaos"]


def _base_projection(row):
    fppg = float(row.get("Avg FPPG", 0) or 0)
    salary = float(row.get("FLEX Salary", 0) or 0)
    pos = str(row.get("Pos", "")).upper()
    salary_pts = max(0.8, salary / 1000.0 * 1.55)
    if pos in {"DST", "D"}: salary_pts *= 0.85
    if pos == "K": salary_pts *= 0.9
    return max(fppg, salary_pts)


def _script_multiplier(pos, team, script, team_a, team_b):
    pos = str(pos).upper()
    mult = 1.0
    if script == "Shootout":
        mult *= 1.18 if pos in {"QB", "WR", "TE"} else 1.06
    elif script == "Low Scoring":
        mult *= 1.12 if pos in {"DST", "D", "K"} else 0.84
    elif script == "Team A Controls":
        mult *= 1.18 if team == team_a else 0.86
        if team == team_a and pos in {"RB", "DST", "D", "K"}: mult *= 1.08
        if team == team_b and pos in {"QB", "WR", "TE"}: mult *= 1.08
    elif script == "Team B Controls":
        mult *= 1.18 if team == team_b else 0.86
        if team == team_b and pos in {"RB", "DST", "D", "K"}: mult *= 1.08
        if team == team_a and pos in {"QB", "WR", "TE"}: mult *= 1.08
    elif script == "Passing Spike":
        mult *= 1.18 if pos in {"QB", "WR", "TE"} else 0.94
    elif script == "Rushing Control":
        mult *= 1.18 if pos == "RB" else (1.07 if pos in {"DST", "D", "K"} else 0.92)
    elif script == "Chaos":
        mult *= 1.10 if pos in {"WR", "TE", "DST", "D", "K"} else 0.96
    return mult


def simulate_player_outcomes(players, teams, n_sims=5000, seed=26, boosts=None):
    rng = np.random.default_rng(int(seed))
    team_a, team_b = teams
    n = len(players)
    sims = np.zeros((int(n_sims), n), dtype=np.float32)
    scripts = rng.choice(SCRIPT_NAMES, size=int(n_sims), p=[.20,.16,.13,.12,.12,.11,.10,.06])
    base = np.array([_base_projection(r) for _, r in players.iterrows()], dtype=float)
    boosts = boosts or {}
    for i in range(len(base)):
        base[i] *= max(0.05, 1.0 + float(boosts.get(i, 0.0)) / 100.0)
    positions = players["Pos"].astype(str).str.upper().tolist()
    player_teams = players["Team"].astype(str).tolist()

    game_shock = rng.normal(0, 0.12, size=int(n_sims))
    ta_shock = rng.normal(0, 0.16, size=int(n_sims))
    tb_shock = rng.normal(0, 0.16, size=int(n_sims))
    for j in range(n):
        pos = positions[j]; team = player_teams[j]
        vol = {"QB":.27,"RB":.43,"WR":.52,"TE":.50,"K":.34,"DST":.55,"D":.55}.get(pos,.48)
        indiv = rng.normal(0, vol, size=int(n_sims))
        shared = game_shock + (ta_shock if team == team_a else tb_shock)
        vals = base[j] * np.exp(shared + indiv - 0.5 * (vol ** 2))
        for script in SCRIPT_NAMES:
            mask = scripts == script
            if mask.any(): vals[mask] *= _script_multiplier(pos, team, script, team_a, team_b)
        if pos in {"WR", "TE", "RB"}:
            zero_prob = .035 if base[j] >= 8 else .10
            vals[rng.random(int(n_sims)) < zero_prob] *= rng.uniform(.0, .25)
        sims[:, j] = np.maximum(vals, 0)
    return sims, scripts, base


def generate_showdown_candidates(players, max_candidates=12000, min_salary=42000, max_salary=SHOWDOWN_SALARY_CAP, salary_cap=SHOWDOWN_SALARY_CAP, seed=26, required_flex_indices=None):
    """Create a diverse legal Showdown candidate pool quickly using NumPy arrays."""
    rows = players.reset_index(drop=True)
    n = len(rows)
    if n < 6:
        return []

    required_flex = tuple(sorted(set(int(i) for i in (required_flex_indices or []))))
    if len(required_flex) > 5 or any(i < 0 or i >= n for i in required_flex):
        return []

    rng = np.random.default_rng(int(seed) + 7919)
    base = np.array([_base_projection(r) for _, r in rows.iterrows()], dtype=np.float32)
    flex_salary = rows["FLEX Salary"].to_numpy(dtype=np.int32)
    cpt_salary = rows["CPT Salary"].to_numpy(dtype=np.int32)
    team_codes, _ = pd.factorize(rows["Team"].astype(str), sort=False)

    cpt_score = base + flex_salary.astype(np.float32) / 5000.0
    cpt_count = min(n, max(16, min(30, n)))
    cpt_pool = np.argsort(-cpt_score)[:cpt_count].astype(np.int32)
    if required_flex:
        required_set = set(required_flex)
        cpt_pool = np.asarray([i for i in cpt_pool if int(i) not in required_set], dtype=np.int32)
        if cpt_pool.size == 0:
            return []

    flex_weight = np.maximum(base, 0.75) ** 1.15
    flex_weight = flex_weight / flex_weight.sum()

    target = int(max_candidates)
    minimum = int(min_salary)
    maximum = min(int(salary_cap), int(max_salary))
    seen = set()
    candidates = []

    # Tight salary windows can reject many random draws. Cap wasted work while still
    # giving the sampler ample room to fill normal 3k/6k/12k candidate requests.
    max_attempts = max(30000, target * 25)
    cpt_order = rng.permutation(cpt_pool).tolist()
    cpt_cursor = 0

    # Cache eligible arrays/probabilities for each Captain instead of rebuilding them.
    cached = {}
    all_idx = np.arange(n, dtype=np.int32)
    for cpt in cpt_pool:
        eligible = all_idx[all_idx != cpt]
        probs = flex_weight[eligible].astype(np.float64, copy=True)
        probs /= probs.sum()
        cached[int(cpt)] = (eligible, probs)

    for attempts in range(max_attempts):
        if len(candidates) >= target:
            break
        cpt = int(cpt_order[cpt_cursor % len(cpt_order)])
        cpt_cursor += 1
        if cpt_cursor % len(cpt_order) == 0:
            cpt_order = rng.permutation(cpt_pool).tolist()

        eligible, probs = cached[cpt]
        if required_flex:
            required_arr = np.asarray(required_flex, dtype=np.int32)
            remaining = 5 - len(required_flex)
            if remaining:
                mask = ~np.isin(eligible, required_arr)
                optional = eligible[mask]
                optional_probs = probs[mask]
                if optional.size < remaining or optional_probs.sum() <= 0:
                    continue
                optional_probs = optional_probs / optional_probs.sum()
                sampled = rng.choice(optional, size=remaining, replace=False, p=optional_probs)
                flex_arr = np.concatenate([required_arr, sampled])
            else:
                flex_arr = required_arr.copy()
        else:
            flex_arr = rng.choice(eligible, size=5, replace=False, p=probs)
        flex = tuple(sorted(map(int, flex_arr)))
        ident = (cpt, flex)
        if ident in seen:
            continue

        salary = int(cpt_salary[cpt] + flex_salary[flex_arr].sum())
        if salary < minimum or salary > maximum:
            continue

        inds = np.empty(6, dtype=np.int32)
        inds[0] = cpt
        inds[1:] = flex_arr
        if np.unique(team_codes[inds]).size < 2:
            continue

        seen.add(ident)
        candidates.append((cpt, flex, salary))

    return candidates


def evaluate_candidates(players, candidates, sims, scripts):
    """Score candidates in vectorized batches rather than one lineup at a time."""
    if not candidates:
        return pd.DataFrame()

    n_candidates = len(candidates)
    cpts = np.fromiter((int(x[0]) for x in candidates), dtype=np.int32, count=n_candidates)
    flexes = np.asarray([x[1] for x in candidates], dtype=np.int32)
    salaries = np.fromiter((int(x[2]) for x in candidates), dtype=np.int32, count=n_candidates)

    means = np.empty(n_candidates, dtype=np.float32)
    ceilings = np.empty(n_candidates, dtype=np.float32)
    p95s = np.empty(n_candidates, dtype=np.float32)
    top1s = np.empty(n_candidates, dtype=np.float32)
    script_values = {name: np.empty(n_candidates, dtype=np.float32) for name in SCRIPT_NAMES}
    script_masks = {name: np.asarray(scripts == name) for name in SCRIPT_NAMES}

    # 256 x 5,000 float32 scores is only ~5 MB, keeping memory modest on Streamlit Cloud.
    batch_size = 256
    for lo in range(0, n_candidates, batch_size):
        hi = min(n_candidates, lo + batch_size)
        bcpt = cpts[lo:hi]
        bflex = flexes[lo:hi]
        scores = 1.5 * sims[:, bcpt].T
        scores += sims[:, bflex].sum(axis=2).T

        means[lo:hi] = scores.mean(axis=1)
        qs = np.quantile(scores, [0.90, 0.95, 0.99], axis=1)
        ceilings[lo:hi] = qs[0]
        p95s[lo:hi] = qs[1]
        top1s[lo:hi] = qs[2]
        for name, mask in script_masks.items():
            if mask.any():
                script_values[name][lo:hi] = scores[:, mask].mean(axis=1)
            else:
                script_values[name][lo:hi] = 0.0

    data = {
        "_cpt": cpts,
        "_flex": [tuple(map(int, row)) for row in flexes],
        "Salary": salaries,
        "Mean": means,
        "Ceiling": ceilings,
        "P95": p95s,
        "Top 1% Score": top1s,
    }
    data.update(script_values)
    df = pd.DataFrame(data)
    for col in ["Mean", "Ceiling", "P95", "Top 1% Score"]:
        std = float(df[col].std())
        df[f"_{col}"] = (df[col] - df[col].mean()) / (std if std and not np.isnan(std) else 1.0)
    df["NUKE Score"] = 100 + 12 * (
        .25 * df["_Mean"] + .30 * df["_Ceiling"] + .20 * df["_P95"] + .25 * df["_Top 1% Score"]
    )
    return df.sort_values(["NUKE Score", "Top 1% Score"], ascending=False).reset_index(drop=True)


def _construction_label_fast(cpt, flex, team_values):
    inds = (int(cpt),) + tuple(map(int, flex))
    counts = Counter(team_values[i] for i in inds)
    ordered = counts.most_common()
    if not ordered:
        return "Unknown"
    if len(ordered) == 2 and ordered[0][1] == ordered[1][1]:
        return "3-3 Even"
    major_team, major_count = ordered[0]
    minor_count = ordered[1][1] if len(ordered) > 1 else 0
    return f"{major_team} {major_count}-{minor_count}"


def _construction_label(cpt, flex, players):
    teams = players.reset_index(drop=True)["Team"].astype(str).to_numpy()
    return _construction_label_fast(cpt, flex, teams)


def add_lineup_labels(results, players):
    if results.empty:
        return results
    rows = players.reset_index(drop=True)
    names = rows["Name"].astype(str).to_numpy()
    teams = rows["Team"].astype(str).to_numpy()
    out = results.copy()
    out.insert(0, "CPT", [names[int(i)] for i in out["_cpt"]])
    for k in range(5):
        out.insert(k + 1, f"FLEX{k+1}", [names[int(x[k])] for x in out["_flex"]])
    out.insert(6, "Construction", [
        _construction_label_fast(r["_cpt"], r["_flex"], teams) for _, r in out.iterrows()
    ])
    return out


def build_portfolio(results, players, count=20, max_player_pct=.75, max_cpt_pct=.35,
                    player_mins=None, player_maxes=None, captain_mins=None, captain_maxes=None,
                    construction_mins=None, construction_maxes=None):
    """Select exactly count lineups while enforcing every player, CPT and build limit.

    A binary mixed-integer optimizer replaces the previous greedy picker, which
    rewarded minimum-exposure deficits but never guaranteed they were met.
    Explicit per-player/CPT maximums override the global default for that player.
    """
    from scipy.optimize import Bounds, LinearConstraint, milp
    from scipy.sparse import coo_matrix, vstack

    target = max(1, int(count))
    if results is None or len(results) < target:
        raise ValueError(
            f"Need at least {target} candidate lineups, but only "
            f"{0 if results is None else len(results)} were generated. "
            "Run the SIM with more candidate lineups."
        )

    player_mins = player_mins or {}
    player_maxes = player_maxes or {}
    captain_mins = captain_mins or {}
    captain_maxes = captain_maxes or {}
    construction_mins = construction_mins or {}
    construction_maxes = construction_maxes or {}
    roster = players.reset_index(drop=True)
    n_players = len(roster)

    def min_count(pct):
        return int(np.ceil(target * max(0., min(1., float(pct))) - 1e-9))

    def max_count(pct):
        return int(np.floor(target * max(0., min(1., float(pct))) + 1e-9))

    p_min = np.array([min_count(player_mins.get(i, 0)) for i in range(n_players)], dtype=int)
    p_max = np.array([
        max_count(player_maxes.get(i, max_player_pct)) for i in range(n_players)
    ], dtype=int)
    c_min = np.array([min_count(captain_mins.get(i, 0)) for i in range(n_players)], dtype=int)
    c_max = np.array([
        max_count(captain_maxes.get(i, max_cpt_pct)) for i in range(n_players)
    ], dtype=int)

    names = roster["Name"].astype(str).tolist()
    for i in range(n_players):
        if p_min[i] > p_max[i]:
            raise ValueError(f"{names[i]}: player minimum exceeds player maximum.")
        if c_min[i] > c_max[i]:
            raise ValueError(f"{names[i]}: captain minimum exceeds captain maximum.")
        if c_min[i] > p_max[i]:
            raise ValueError(f"{names[i]}: captain minimum exceeds total player maximum.")
    if int(p_min.sum()) > 6 * target or int(p_max.sum()) < 6 * target:
        raise ValueError("Player exposure bounds must accommodate six players per lineup (600% total).")
    if int(c_min.sum()) > target or int(c_max.sum()) < target:
        raise ValueError("Captain exposure bounds must accommodate one captain per lineup (100% total).")

    # Include the complete scored pool, not just the first 6,000 lineups:
    # lower-exposure players often require candidates further down the ranks.
    band = results.reset_index(drop=True)
    n_choices = len(band)
    teams = roster["Team"].astype(str).to_numpy()
    member_r, member_c, cpt_r, cpt_c = [], [], [], []
    construction_labels = []
    for j, row in enumerate(band.itertuples(index=False, name=None)):
        # Pandas may rename private columns in itertuples, so access by position.
        cpt = int(row[band.columns.get_loc("_cpt")])
        flex = tuple(map(int, row[band.columns.get_loc("_flex")]))
        inds = (cpt,) + flex
        member_r.extend(inds)
        member_c.extend([j] * len(inds))
        cpt_r.append(cpt)
        cpt_c.append(j)
        construction_labels.append(_construction_label_fast(cpt, flex, teams))

    members = coo_matrix(
        (np.ones(len(member_r)), (member_r, member_c)),
        shape=(n_players, n_choices),
    ).tocsr()
    captains = coo_matrix(
        (np.ones(n_choices), (cpt_r, cpt_c)),
        shape=(n_players, n_choices),
    ).tocsr()
    labels = sorted(set(construction_mins) | set(construction_maxes))
    label_index = {label: idx for idx, label in enumerate(labels)}
    construction_r = [label_index[label] for label in construction_labels if label in label_index]
    construction_c = [j for j, label in enumerate(construction_labels) if label in label_index]
    builds = coo_matrix(
        (np.ones(len(construction_r)), (construction_r, construction_c)),
        shape=(len(labels), n_choices),
    ).tocsr()
    b_min = np.array([min_count(construction_mins.get(s, 0)) for s in labels], dtype=int)
    b_max = np.array([max_count(construction_maxes.get(s, 1)) for s in labels], dtype=int)
    if np.any(b_min > b_max):
        raise ValueError("A construction minimum exceeds its maximum.")
    if len(labels) and (b_min.sum() > target or b_max.sum() < target):
        raise ValueError("Construction ranges cannot add up to the requested portfolio size.")

    if np.any(p_min > np.asarray(members.getnnz(axis=1))):
        raise ValueError("A player minimum needs more candidate lineups than this SIM produced.")
    if np.any(c_min > np.asarray(captains.getnnz(axis=1))):
        raise ValueError("A captain minimum needs more candidate lineups than this SIM produced.")
    if len(labels) and np.any(b_min > np.asarray(builds.getnnz(axis=1))):
        raise ValueError("A construction minimum needs more candidate lineups than this SIM produced.")

    matrix = vstack(
        [coo_matrix(np.ones((1, n_choices))), members, captains, builds],
        format="csc",
    )
    lower = np.concatenate(([target], p_min, c_min, b_min))
    upper = np.concatenate(([target], p_max, c_max, b_max))
    score = np.nan_to_num(
        band["NUKE Score"].to_numpy(dtype=float), nan=-1000., neginf=-1000., posinf=1000.
    )
    cost = (score.max() - score) / max(1., float(np.ptp(score)))
    solution = milp(
        c=cost,
        integrality=np.ones(n_choices, dtype=np.int32),
        bounds=Bounds(np.zeros(n_choices), np.ones(n_choices)),
        constraints=LinearConstraint(matrix, lower, upper),
        options={"time_limit": 20.0, "mip_rel_gap": 0.025},
    )
    if solution.x is None:
        raise ValueError(
            "No complete portfolio satisfies all the player, captain and construction "
            "Min/Max limits in the current candidate pool. Loosen conflicting ranges "
            "or rerun the SIM with more candidates."
        )
    selected = np.flatnonzero(solution.x > 0.5)
    observed = matrix @ (solution.x > 0.5).astype(float)
    if (len(selected) != target or np.any(observed < lower - 1e-6)
            or np.any(observed > upper + 1e-6)):
        raise ValueError("Could not verify a complete portfolio meeting every exposure limit.")
    return band.iloc[selected].sort_values(
        ["NUKE Score", "Top 1% Score"], ascending=False
    ).reset_index(drop=True)

def exposure_table(portfolio, players):
    if portfolio.empty: return pd.DataFrame(), pd.DataFrame()
    rows=players.reset_index(drop=True); n=len(portfolio); pc=Counter(); cc=Counter()
    for _,r in portfolio.iterrows():
        c=int(r["_cpt"]); flex=list(map(int,r["_flex"])); cc[c]+=1; pc.update([c]+flex)
    def make(counter):
        return pd.DataFrame([{"Player":rows.iloc[i]["Name"],"Team":rows.iloc[i]["Team"],"Pos":rows.iloc[i]["Pos"],"Lineups":c,"Exposure %":round(100*c/n,1)} for i,c in counter.most_common()])
    return make(pc), make(cc)
