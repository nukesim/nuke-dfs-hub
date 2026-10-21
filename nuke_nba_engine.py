"""Minutes-driven NBA Classic projections, correlated sims and GPP portfolio.

Ownership and synthetic-field metrics are *model estimates*, not sportsbook odds,
observed contest ownership, or calibrated probabilities of winning first place.
"""

from __future__ import annotations

import csv
import io
import math
import random
from collections import Counter, defaultdict
from datetime import datetime

from nuke_nba_data import DK_SLOTS, standardized_status

CAP = 50000
AVAILABILITY = {"ACTIVE": 1.0, "P": 0.90, "Q": 0.65, "DOUBTFUL": 0.16, "OUT": 0.0}


def project_players(players, *, rotation_depth=11, minutes_overrides=None,
                    status_overrides=None, excluded_ids=None, included_questionable=False):
    """Produce per-team 240-minute rotations with separately labeled play risk."""
    overrides = {str(k): v for k, v in (minutes_overrides or {}).items()}
    statuses = {str(k): v for k, v in (status_overrides or {}).items()}
    excluded = {str(x) for x in (excluded_ids or ())}
    modeled = [dict(p) for p in players]
    by_team = defaultdict(list)
    for p in modeled:
        p["status"] = standardized_status(statuses.get(p["id"], p.get("status", p.get("dk_status", ""))))
        p["play_prob"] = AVAILABILITY[p["status"]]
        p["excluded"] = p["id"] in excluded or p["status"] == "OUT"
        if not included_questionable and p["status"] in {"Q", "DOUBTFUL"}:
            p["excluded"] = True
        p["minutes"] = 0.0
        by_team[p["team"]].append(p)

    for team, roster in by_team.items():
        active = [p for p in roster if not p["excluded"]]
        # A previous-year rotation is only a prior; each team's expected playing
        # time must be allocated anew after injury changes.
        for p in active:
            baseline = float(p.get("minutes_base", 0) or 0)
            if p.get("starter") == "CONFIRMED":
                baseline = max(baseline, 29.0)
            elif p.get("starter") == "EXPECTED":
                baseline = max(baseline, 25.0)
            # A *confirmed* team five should alter actual expected rotation
            # share, not merely turn the badge green. Weight starters more and
            # bench less, keeping all team minutes normalized to 240.
            # This is a moderate prior, not a substitute for team-specific
            # coach rotations or exact on/off-court usage rates.
            news_weight = (1.18 if p.get("starter") == "CONFIRMED" else
                           0.87 if p.get("confirmed_team") else 1.0)
            p["rotation_weight"] = max(0.0, baseline) ** 1.6 * news_weight
        order = sorted(active, key=lambda p: (
            p.get("starter") == "CONFIRMED", p.get("starter") == "EXPECTED",
            p["rotation_weight"], p["salary"]), reverse=True)
        rotation = order[:max(8, min(13, int(rotation_depth)))]
        if rotation:
            weights = {p["id"]: p["rotation_weight"] for p in rotation}
            # Fixed user overrides survive the normalization. A deliberate zero
            # removes a player from the available rotation budget.
            fixed = {p["id"]: max(0.0, min(42.0, float(overrides[p["id"]])))
                     for p in rotation if p["id"] in overrides}
            if sum(fixed.values()) > 240.0:
                scale = 240.0 / sum(fixed.values())
                fixed = {identifier: value * scale for identifier, value in fixed.items()}
                for p in roster:
                    p["minutes_warning"] = "Manual minutes exceeded the team's 240 minutes and were scaled."
            remaining = max(0.0, 240.0 - sum(fixed.values()))
            free = [p for p in rotation if p["id"] not in fixed]
            allocated = {p["id"]: fixed[p["id"]] for p in rotation if p["id"] in fixed}
            # Water-fill; the 42-minute cap prevents impossible rotations.
            while free:
                total = sum(weights[p["id"]] for p in free)
                if total <= 0:
                    break
                saturated = [p for p in free if remaining * weights[p["id"]] / total > 42.0]
                if not saturated:
                    for p in free:
                        allocated[p["id"]] = remaining * weights[p["id"]] / total
                    break
                for p in saturated:
                    allocated[p["id"]] = 42.0
                    remaining -= 42.0
                    free.remove(p)
            for p in rotation:
                p["minutes"] = round(allocated.get(p["id"], 0.0), 1)

        for p in roster:
            pace = p.get("game_total")
            pace_factor = min(1.08, max(0.92, 1.0 + (float(pace) - 226) / 1100)) if pace else 1.0
            p["conditional_projection"] = round(p["minutes"] * p["fppm_base"] * pace_factor, 2)
            p["projection"] = round(p["conditional_projection"] * p["play_prob"], 2)
            p["value"] = round(p["projection"] / max(p["salary"], 1) * 1000, 2)
            p["rotation"] = p["minutes"] >= 8.0
    return modeled


def estimate_ownership(players):
    """Capacity-normalized 800% ownership prior, inferred from model/value."""
    eligible = [p for p in players if not p.get("excluded") and p.get("minutes", 0) >= 6]
    if not eligible:
        return players
    def z(value, values):
        avg = sum(values) / len(values)
        sd = math.sqrt(sum((x - avg)**2 for x in values) / len(values)) or 1.0
        return max(-2.4, min(2.4, (value-avg)/sd))
    values = [p["value"] for p in eligible]
    projections = [p["projection"] for p in eligible]
    raw = []
    for p in eligible:
        score = (0.93 * z(p["value"], values) + 0.48 * z(p["projection"], projections)
                 + (0.15 if p.get("starter") != "UNKNOWN" else 0.0))
        raw.append(math.exp(max(-4, min(4, score))))
    # Iterative capped allocation preserves approximately eight total roster spots.
    own = [0.0] * len(eligible)
    open_ids = set(range(len(eligible)))
    remaining = 800.0
    while open_ids:
        total = sum(raw[i] for i in open_ids)
        if total <= 0:
            break
        too_high = [i for i in open_ids if remaining * raw[i] / total > 62.0]
        if not too_high:
            for i in open_ids:
                own[i] = remaining * raw[i] / total
            break
        for i in too_high:
            own[i] = 62.0
            remaining -= 62.0
            open_ids.remove(i)
    by_id = {p["id"]: round(own[i], 1) for i, p in enumerate(eligible)}
    for p in players:
        p["ownership"] = by_id.get(p["id"], 0.0)
        p["leverage"] = round(p["projection"] / max(p["ownership"], 3.0), 2)
    return players


def simulate_slate(players, simulations=2500, seed=20261020):
    """Correlated game/team shocks + player/minutes volatility + status risk."""
    import numpy as np
    rng = np.random.default_rng(int(seed))
    simulations = int(simulations)
    n = len(players)
    shocks = np.zeros((n, simulations), dtype=np.float32)
    games = {game: rng.normal(0, 0.06, simulations) for game in {p["game"] for p in players}}
    teams = {team: rng.normal(0, 0.04, simulations) for team in {p["team"] for p in players}}
    for idx, p in enumerate(players):
        conditional = float(p.get("conditional_projection", 0))
        if conditional <= 0 or p.get("excluded"):
            continue
        individual = rng.normal(0, 0.21, simulations)
        minutes_noise = rng.normal(0, 0.095 if p["minutes"] >= 25 else 0.16, simulations)
        total = 1 + games[p["game"]] + teams[p["team"]] + individual + minutes_noise
        outcomes = np.maximum(0, conditional * total)
        if p.get("play_prob", 1) < 1:
            outcomes *= (rng.random(simulations) < p["play_prob"])
        shocks[idx, :] = outcomes.astype(np.float32)
        p["p90"] = round(float(np.percentile(outcomes, 90)), 1)
        p["p99"] = round(float(np.percentile(outcomes, 99)), 1)
        p["hit_20"] = round(float(np.mean(outcomes >= 20) * 100), 1)
        p["hit_6x"] = round(float(np.mean(outcomes >= 6 * p["salary"] / 1000) * 100), 1)
    for p in players:
        p.setdefault("p90", 0.0)
        p.setdefault("p99", 0.0)
        p.setdefault("hit_20", 0.0)
        p.setdefault("hit_6x", 0.0)
    return shocks


def validate_lineup(lineup, players, min_salary=0, max_team=8):
    if len(lineup) != len(DK_SLOTS) or len(set(lineup)) != len(DK_SLOTS):
        return False
    salary = sum(players[i]["salary"] for i in lineup)
    if not min_salary <= salary <= CAP:
        return False
    teams = Counter(players[i]["team"] for i in lineup)
    return all(DK_SLOTS[k] in players[i]["eligible"] and not players[i].get("excluded")
               for k, i in enumerate(lineup)) and max(teams.values()) <= max_team


def optimize_once(players, player_weights, *, min_salary=47500, max_team=4,
                  forced_ids=None, banned_ids=None, previous=None, time_limit=0.65):
    """Exact positional binary MILP; returns slot-index tuple or None."""
    import numpy as np
    from scipy.optimize import Bounds, LinearConstraint, milp
    from scipy.sparse import coo_matrix

    forced_ids = {str(x) for x in (forced_ids or ())}
    banned_ids = {str(x) for x in (banned_ids or ())}
    pairs = [(i, k) for i, p in enumerate(players) for k, slot in enumerate(DK_SLOTS)
             if slot in p["eligible"] and not p.get("excluded") and p.get("minutes", 0) > 0
             and p["id"] not in banned_ids]
    if not pairs:
        return None
    rows, cols, values, lower, upper = [], [], [], [], []
    def constraint(picks, lb, ub):
        idx = len(lower)
        for column, amount in picks:
            rows.append(idx); cols.append(column); values.append(float(amount))
        lower.append(lb); upper.append(ub)
    by_player = defaultdict(list)
    by_slot = defaultdict(list)
    by_team = defaultdict(list)
    for column, (i, k) in enumerate(pairs):
        by_player[i].append(column)
        by_slot[k].append(column)
        by_team[players[i]["team"]].append(column)
    for k in range(8):
        if not by_slot[k]:
            return None
        constraint(((j, 1) for j in by_slot[k]), 1, 1)
    for i, group in by_player.items():
        constraint(((j, 1) for j in group), 1 if players[i]["id"] in forced_ids else 0, 1)
    if any(fid not in {players[i]["id"] for i in by_player} for fid in forced_ids):
        return None
    constraint(((j, players[i]["salary"]) for j, (i, k) in enumerate(pairs)), min_salary, CAP)
    for group in by_team.values():
        constraint(((j, 1) for j in group), 0, int(max_team))
    for old in (previous or [])[-30:]:
        prior_ids = {players[i]["id"] for i in old}
        constraint(((j, 1) for j, (i, k) in enumerate(pairs) if players[i]["id"] in prior_ids), 0, 7)
    matrix = coo_matrix((values, (rows, cols)), shape=(len(lower), len(pairs))).tocsr()
    # A tiny late-game tiebreak puts late games into UTIL/G/F where possible.
    costs = []
    for i, k in pairs:
        flexible = 1 if DK_SLOTS[k] in {"UTIL", "G", "F"} else 0
        late = players[i]["start"].timestamp() / 1000000000
        costs.append(-float(player_weights[i]) - flexible * late * 0.002)
    result = milp(np.array(costs), integrality=np.ones(len(pairs)),
                  bounds=Bounds(0, 1),
                  constraints=LinearConstraint(matrix, lower, upper),
                  options={"time_limit": time_limit, "mip_rel_gap": 0.02})
    if result.x is None:
        return None
    chosen = [None] * 8
    for val, (i, k) in zip(result.x, pairs):
        if val > 0.5:
            chosen[k] = i
    if any(i is None for i in chosen) or not validate_lineup(chosen, players, min_salary, max_team):
        return None
    return tuple(chosen)


def _field_lineups(players, count, seed, min_salary=44000):
    rng = random.Random(seed)
    groups = {slot: [i for i, p in enumerate(players) if slot in p["eligible"] and
                      not p.get("excluded") and p.get("minutes", 0) > 0] for slot in DK_SLOTS}
    samples = []
    order = (4, 0, 1, 2, 3, 5, 6, 7)
    for _ in range(count * 160):
        if len(samples) >= count:
            break
        roster, used, salary = [None]*8, set(), 0
        for k in order:
            candidates = [i for i in groups[DK_SLOTS[k]] if i not in used and salary+players[i]["salary"] <= CAP]
            if not candidates:
                break
            weights = [(max(1.0, players[i].get("ownership", 1)) ** 1.3) *
                       (max(0.2, players[i]["salary"] / 5500)**0.5) for i in candidates]
            pick = rng.choices(candidates, weights=weights, k=1)[0]
            roster[k] = pick; used.add(pick); salary += players[pick]["salary"]
        if None not in roster and salary >= min_salary:
            samples.append(tuple(roster))
    return samples


def build_portfolio(players, scores, *, entries=20, simulations=2500, seed=20261020,
                    min_salary=47500, max_team=4, max_exposure=40,
                    field_size=10000, forced_ids=None, banned_ids=None):
    import numpy as np
    if entries < 1 or entries > 150:
        raise ValueError("Entries must be between 1 and 150.")
    rng = np.random.default_rng(int(seed) + 431)
    forced_ids = {str(x) for x in (forced_ids or ())}
    max_counts = {p["id"]: entries if p["id"] in forced_ids else
                  max(1, int(math.ceil(entries * max_exposure / 100))) for p in players}
    seen, selected, exposure = set(), [], Counter()
    base = np.array([p["projection"] for p in players])
    upside = np.array([p["p90"] - p["projection"] for p in players])
    own = np.array([p.get("ownership", 0) for p in players])
    stdev = scores.std(axis=1)
    for j in range(entries):
        banned = set(banned_ids or ()) | {pid for pid, count in exposure.items() if count >= max_counts[pid]}
        lineup = None
        for attempt in range(7):
            archetype = (j + attempt) % 4
            if archetype == 0:  # Star-led, high-ceiling combinations
                weights = base + .68 * upside + rng.normal(0, stdev * .45)
            elif archetype == 1:  # Differentiation without giving up all projection
                weights = base + .47 * upside - .15 * own + rng.normal(0, stdev * .65)
            elif archetype == 2:  # A coherent simulated slate outcome
                path = int(rng.integers(scores.shape[1]))
                weights = .42 * base + .58 * scores[:, path] - .08 * own
            else:  # Balanced, more reliable minutes/value
                weights = base + .28 * upside - .055 * own + rng.normal(0, stdev * .4)
            # A soft exposure toll discourages using the same core early.
            toll = np.array([exposure[p["id"]] / max(1, j) for p in players])
            weights = weights - (6.5 * toll)
            lineup = optimize_once(players, weights, min_salary=min_salary, max_team=max_team,
                                   forced_ids=forced_ids, banned_ids=banned,
                                   previous=selected, time_limit=0.7)
            if lineup and frozenset(lineup) not in seen:
                break
            lineup = None
        if lineup is None:
            break
        seen.add(frozenset(lineup)); selected.append(lineup)
        exposure.update(players[i]["id"] for i in lineup)

    if not selected:
        return [], [], {"reason": "No feasible NBA Classic lineup. Lower the minimum salary or relax locks/caps."}
    # A real contest's field/ownership is unavailable; the following is a
    # finite-sample benchmark, not a literal first-place probability.
    field_target = min(1000, max(350, int(math.sqrt(max(100, field_size)) * 5)))
    field = _field_lineups(players, field_target, seed+31)
    simulated_field = np.stack([scores[list(x)].sum(axis=0) for x in field]) if field else None
    field_max = simulated_field.max(axis=0) if field else None
    field_top_one = np.percentile(simulated_field, 99, axis=0) if field else None
    results = []
    for slot_indices in selected:
        index = list(slot_indices)
        outcomes = scores[index].sum(axis=0)
        members = [players[i] for i in index]
        salary = sum(p["salary"] for p in members)
        chalk = sum(p["ownership"] for p in members)
        beat = float(np.mean(outcomes > field_max)) * 100 if field_max is not None else 0.0
        top_one = float(np.mean(outcomes > field_top_one)) * 100 if field_top_one is not None else 0.0
        # Expected duplicate entries are deliberately an *index* of risk.
        duplicate_index = float(field_size) * math.prod(max(0.003, p["ownership"] / 100) for p in members)
        gpp_score = (float(np.percentile(outcomes, 99)) * .5 + beat * 1.1 + top_one * 0.15
                     + float(np.mean(outcomes >= 300)) * 300 - math.log1p(duplicate_index) * 1.7)
        results.append({
            "lineup": slot_indices, "salary": salary,
            "projection": round(sum(p["projection"] for p in members), 1),
            "p90": round(float(np.percentile(outcomes, 90)), 1),
            "p99": round(float(np.percentile(outcomes, 99)), 1),
            "field_beat_proxy": round(beat, 2),
            "top_one_proxy": round(top_one, 2),
            "chalk_sum": round(chalk, 1),
            "duplication_index": round(duplicate_index, 3),
            "gpp_score": round(gpp_score, 2),
        })
    results.sort(key=lambda r: r["gpp_score"], reverse=True)
    exposure_list = sorted(({"name": p["name"], "team": p["team"],
                              "own": p["ownership"], "count": exposure[p["id"]],
                              "exposure": round(100*exposure[p["id"]]/len(selected), 1)}
                             for p in players if exposure[p["id"]]),
                            key=lambda r: r["exposure"], reverse=True)
    meta = {"requested": entries, "generated": len(results), "field_samples": len(field),
            "simulations": int(simulations), "min_salary": min_salary}
    return results, exposure_list, meta


def export_dk_csv(results, players):
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(DK_SLOTS)
    for lineup in results:
        writer.writerow([f'{players[i]["name"]} ({players[i]["id"]})' for i in lineup["lineup"]])
    return buffer.getvalue()
