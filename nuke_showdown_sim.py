import itertools
from collections import Counter

import numpy as np
import pandas as pd

from nuke_showdown import SHOWDOWN_SALARY_CAP

SCRIPT_NAMES = ["Balanced", "Shootout", "Low Scoring", "Team A Controls", "Team B Controls", "Passing Spike", "Rushing Control", "Chaos"]


def _base_projection(row):
    fppg = float(row.get("Avg FPPG", 0) or 0)
    salary = float(row.get("FLEX Salary", 0) or 0)
    pos = str(row.get("Pos", "")).upper()
    # Salary is the fallback signal when DK's FPPG field is sparse/new-season data.
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


def simulate_player_outcomes(players, teams, n_sims=5000, seed=26):
    rng = np.random.default_rng(int(seed))
    team_a, team_b = teams
    n = len(players)
    sims = np.zeros((int(n_sims), n), dtype=np.float32)
    scripts = rng.choice(SCRIPT_NAMES, size=int(n_sims), p=[.20,.16,.13,.12,.12,.11,.10,.06])
    base = np.array([_base_projection(r) for _, r in players.iterrows()], dtype=float)
    positions = players["Pos"].astype(str).str.upper().tolist()
    player_teams = players["Team"].astype(str).tolist()

    # Shared game/team shocks create useful single-game correlation without paid projections.
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
        # Small zero/near-zero tail for volatile skill players.
        if pos in {"WR", "TE", "RB"}:
            zero_prob = .035 if base[j] >= 8 else .10
            vals[rng.random(int(n_sims)) < zero_prob] *= rng.uniform(.0, .25)
        sims[:, j] = np.maximum(vals, 0)
    return sims, scripts, base


def generate_showdown_candidates(players, max_candidates=12000, min_salary=42000):
    rows = players.reset_index(drop=True)
    candidates = []
    n = len(rows)
    # Candidate search is salary/role aware: prioritize plausible pool while retaining cheap values.
    priority = rows.assign(_score=rows.apply(_base_projection, axis=1) + rows["FLEX Salary"] / 3500.0, axis=1)
    keep = priority.sort_values("_score", ascending=False).head(min(n, 30)).index.tolist()
    cheap = rows.sort_values("FLEX Salary").head(min(n, 12)).index.tolist()
    pool = sorted(set(keep + cheap))
    for cpt in pool:
        cpt_salary = int(rows.iloc[cpt]["CPT Salary"])
        others = [x for x in pool if x != cpt]
        for flex in itertools.combinations(others, 5):
            salary = cpt_salary + int(rows.iloc[list(flex)]["FLEX Salary"].sum())
            if salary > SHOWDOWN_SALARY_CAP or salary < int(min_salary): continue
            teams = set(rows.iloc[[cpt] + list(flex)]["Team"].astype(str))
            if len(teams) < 2: continue
            candidates.append((cpt, flex, salary))
            if len(candidates) >= int(max_candidates): return candidates
    return candidates


def evaluate_candidates(players, candidates, sims, scripts):
    if not candidates: return pd.DataFrame()
    out = []
    for cpt, flex, salary in candidates:
        scores = 1.5 * sims[:, cpt] + sims[:, list(flex)].sum(axis=1)
        row = {
            "_cpt": cpt, "_flex": tuple(flex), "Salary": salary,
            "Mean": float(scores.mean()), "Ceiling": float(np.quantile(scores,.90)),
            "P95": float(np.quantile(scores,.95)), "Top 1% Score": float(np.quantile(scores,.99)),
        }
        for script in SCRIPT_NAMES:
            mask = scripts == script
            row[script] = float(scores[mask].mean()) if mask.any() else 0.0
        out.append(row)
    df = pd.DataFrame(out)
    for col in ["Mean","Ceiling","P95","Top 1% Score"]:
        s = df[col].std()
        df[f"_{col}"] = (df[col] - df[col].mean()) / (s if s and not np.isnan(s) else 1)
    df["NUKE Score"] = 100 + 12*(.25*df["_Mean"] + .30*df["_Ceiling"] + .20*df["_P95"] + .25*df["_Top 1% Score"])
    return df.sort_values(["NUKE Score","Top 1% Score"], ascending=False).reset_index(drop=True)


def add_lineup_labels(results, players):
    if results.empty: return results
    rows = players.reset_index(drop=True)
    out = results.copy()
    out.insert(0, "CPT", [rows.iloc[i]["Name"] for i in out["_cpt"]])
    for k in range(5):
        out.insert(k+1, f"FLEX{k+1}", [rows.iloc[list(x)[k]]["Name"] for x in out["_flex"]])
    splits=[]
    for _, r in out.iterrows():
        inds=[r["_cpt"]]+list(r["_flex"]); counts=Counter(rows.iloc[inds]["Team"].astype(str)); splits.append("-".join(map(str,sorted(counts.values(),reverse=True))))
    out.insert(6,"Split",splits)
    return out


def build_portfolio(results, players, count=20, max_player_pct=.75, max_cpt_pct=.35):
    if results.empty: return results
    target=max(1,int(count)); max_player=max(1,int(np.ceil(target*float(max_player_pct)))); max_cpt=max(1,int(np.ceil(target*float(max_cpt_pct))))
    player_counts=Counter(); cpt_counts=Counter(); chosen=[]
    # Require different game-script strengths by using a broad high-quality candidate band.
    band=results.head(min(len(results),2500))
    for _, r in band.iterrows():
        inds=[int(r["_cpt"])]+list(map(int,r["_flex"]))
        if cpt_counts[inds[0]] >= max_cpt: continue
        if any(player_counts[i] >= max_player for i in inds): continue
        chosen.append(r); cpt_counts[inds[0]]+=1; player_counts.update(inds)
        if len(chosen)>=target: break
    return pd.DataFrame(chosen).reset_index(drop=True) if chosen else results.head(target).copy()


def exposure_table(portfolio, players):
    if portfolio.empty: return pd.DataFrame(), pd.DataFrame()
    rows=players.reset_index(drop=True); n=len(portfolio); pc=Counter(); cc=Counter()
    for _,r in portfolio.iterrows():
        c=int(r["_cpt"]); flex=list(map(int,r["_flex"])); cc[c]+=1; pc.update([c]+flex)
    def make(counter):
        return pd.DataFrame([{"Player":rows.iloc[i]["Name"],"Team":rows.iloc[i]["Team"],"Pos":rows.iloc[i]["Pos"],"Lineups":c,"Exposure %":round(100*c/n,1)} for i,c in counter.most_common()])
    return make(pc), make(cc)
