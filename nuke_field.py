import numpy as np
import pandas as pd

FIELD_ENGINE_VERSION = "Field Engine V1"

ROLE_BONUS = {
    "QB1": 0.35, "RB1": 0.55, "RB2": 0.18, "RB3": -0.30,
    "WR1": 0.48, "WR2": 0.20, "WR3": -0.05, "TE1": 0.38,
    "QB2+": -2.5, "RB4+": -0.75, "WR4+": -0.65, "TE2+": -0.45,
    "DST": 0.0,
}

# Expected roster slots per lineup after allowing for FLEX usage. These totals sum to 9.
EXPECTED_SLOTS = {"QB": 1.00, "RB": 2.30, "WR": 3.55, "TE": 1.15, "DST": 1.00}


def _z(v):
    a = np.asarray(v, dtype=float)
    if not len(a):
        return a
    sd = float(np.std(a))
    return (a - float(np.mean(a))) / (sd if sd > 1e-9 else 1.0)


def projection_free_player_ownership(players):
    """Estimate player ownership using only DraftKings market/role information.

    No fantasy-point or third-party ownership projections are used. Salary rank,
    inferred depth role, starter confidence, team salary strength and position are
    converted into expected field ownership shares whose position totals match a
    legal DK roster with realistic FLEX allocation.
    """
    p = players.reset_index(drop=True).copy()
    if p.empty:
        return pd.DataFrame(columns=["Player", "Position", "Team", "Salary", "Field Ownership %"])

    p["market_score"] = pd.to_numeric(p.get("market_score", 0.5), errors="coerce").fillna(0.5).clip(0, 1)
    p["starter_confidence"] = pd.to_numeric(p.get("starter_confidence", 1.0), errors="coerce").fillna(1.0).clip(0, 1)
    role = p.get("auto_role", pd.Series([""] * len(p))).astype(str)
    role_bonus = role.map(ROLE_BONUS).fillna(0.0).to_numpy(float)

    # Team salary strength is a projection-free proxy for how attractive an offense is to the field.
    skill = p[p.Position.isin(["QB", "RB", "WR", "TE"])].groupby("Team")["Salary"].sum()
    team_strength = p.Team.map(skill).fillna(skill.median() if len(skill) else 0).to_numpy(float)
    team_z = _z(team_strength)

    logit = 2.25 * p.market_score.to_numpy(float) + 0.75 * p.starter_confidence.to_numpy(float) + role_bonus + 0.18 * team_z
    logit = np.clip(logit, -6, 7)
    raw = np.exp(logit)

    ownership = np.zeros(len(p), dtype=float)
    for pos, slots in EXPECTED_SLOTS.items():
        ids = np.where(p.Position.astype(str).to_numpy() == pos)[0]
        if not len(ids):
            continue
        vals = raw[ids]
        vals = vals / vals.sum() if vals.sum() > 0 else np.full(len(ids), 1.0 / len(ids))
        ownership[ids] = 100.0 * float(slots) * vals

    # Individual ownership cannot exceed 100% even if a thin position pool exists.
    ownership = np.clip(ownership, 0.01, 99.5)
    out = pd.DataFrame({
        "Player": p.Name.astype(str),
        "Position": p.Position.astype(str),
        "Team": p.Team.astype(str),
        "Salary": pd.to_numeric(p.Salary, errors="coerce").fillna(0).astype(int),
        "Auto Role": role,
        "Field Ownership %": np.round(ownership, 2),
    })
    out["Ownership Rank"] = out.groupby("Position")["Field Ownership %"].rank(method="first", ascending=False).astype(int)
    return out


def _lineup_features(results, players, player_ownership):
    r = results.reset_index(drop=True).copy()
    own = player_ownership["Field Ownership %"].to_numpy(float) / 100.0
    salary = pd.to_numeric(r["Salary"], errors="coerce").fillna(49000).to_numpy(float)
    nuke = pd.to_numeric(r.get("NUKE Score", 0), errors="coerce").fillna(0).to_numpy(float)
    ceiling = pd.to_numeric(r.get("Ceiling 95", 0), errors="coerce").fillna(0).to_numpy(float)
    stack = r.get("Stack", pd.Series([""] * len(r))).astype(str)

    log_own = np.zeros(len(r), dtype=float)
    chalk = np.zeros(len(r), dtype=float)
    max_own = np.zeros(len(r), dtype=float)
    low_owned = np.zeros(len(r), dtype=float)
    for j, lu in enumerate(r["_indices"]):
        ids = np.asarray(list(lu), dtype=int)
        vals = np.clip(own[ids], 0.001, 0.995)
        log_own[j] = float(np.sum(np.log(vals)))
        chalk[j] = float(np.sum(vals))
        max_own[j] = float(np.max(vals))
        low_owned[j] = float(np.sum(vals < 0.05))

    spent = (salary - 45000.0) / 5000.0
    stack_bonus = np.zeros(len(r), dtype=float)
    stack_bonus += np.where(stack.str.startswith("QB + 1 / 1"), 0.45, 0.0)
    stack_bonus += np.where(stack.str.startswith("QB + 2 / 1"), 0.60, 0.0)
    stack_bonus += np.where(stack.str.startswith("QB + 2 / 0"), 0.18, 0.0)
    stack_bonus += np.where(stack.str.startswith("QB + 1 / 0"), 0.08, 0.0)
    stack_bonus += np.where(stack.str.startswith("QB + 2 / 2"), 0.25, 0.0)

    return {
        "salary": salary,
        "salary_spend": spent,
        "nuke_z": _z(nuke),
        "ceiling_z": _z(ceiling),
        "log_own_z": _z(log_own),
        "chalk_z": _z(chalk),
        "max_own": max_own,
        "low_owned": low_owned,
        "stack_bonus": stack_bonus,
        "chalk_sum": chalk,
    }


def field_weights_v1(results, players):
    """Return a behavioral mixture over generated legal candidate lineups.

    The field is modeled as four overlapping populations rather than one optimizer:
    chalk-heavy public lineups, sharper correlated lineups, balanced lineups, and a
    small recreational tail. This creates more realistic salary usage, stack rates,
    chalk combinations and duplicate pressure without importing ownership projections.
    """
    r = results.reset_index(drop=True)
    if r.empty:
        return np.array([], dtype=float), {}, pd.DataFrame()

    po = projection_free_player_ownership(players)
    f = _lineup_features(r, players, po)

    chalk = 1.45 * f["log_own_z"] + 0.95 * f["salary_spend"] + 0.20 * f["stack_bonus"] + 0.10 * f["nuke_z"]
    sharp = 0.62 * f["log_own_z"] + 0.55 * f["salary_spend"] + 0.80 * f["stack_bonus"] + 0.62 * f["ceiling_z"] + 0.38 * f["nuke_z"]
    balanced = 0.82 * f["log_own_z"] + 0.65 * f["salary_spend"] + 0.38 * f["stack_bonus"] + 0.28 * f["ceiling_z"]
    recreational = 0.30 * f["log_own_z"] + 0.18 * f["salary_spend"] + 0.08 * f["stack_bonus"] - 0.10 * f["low_owned"]

    archetypes = {
        "Chalk": (0.45, chalk),
        "Sharp": (0.25, sharp),
        "Balanced": (0.20, balanced),
        "Recreational": (0.10, recreational),
    }
    mix = np.zeros(len(r), dtype=float)
    components = {}
    for name, (share, logits) in archetypes.items():
        logits = np.clip(logits, -10, 10)
        w = np.exp(logits - np.max(logits))
        w = w / w.sum() if w.sum() > 0 else np.full(len(w), 1.0 / len(w))
        components[name] = w
        mix += float(share) * w
    mix = mix / mix.sum()

    detail = pd.DataFrame({
        "Field Popularity %": np.round(100.0 * mix, 4),
        "Lineup Ownership Sum %": np.round(100.0 * f["chalk_sum"], 1),
        "Max Player Ownership %": np.round(100.0 * f["max_own"], 1),
        "Sub-5% Players": f["low_owned"].astype(int),
    })
    dominant = np.array(list(components))[np.argmax(np.stack([components[k] for k in components], axis=1), axis=1)]
    detail["Field Archetype"] = dominant

    diagnostics = {
        "engine": FIELD_ENGINE_VERSION,
        "chalk_share": 0.45,
        "sharp_share": 0.25,
        "balanced_share": 0.20,
        "recreational_share": 0.10,
    }
    return mix, diagnostics, detail
