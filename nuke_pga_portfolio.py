"""PGA candidate generation and hard-constrained portfolio selection."""
from itertools import combinations

import numpy as np
import pandas as pd
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_matrix


class PortfolioError(ValueError):
    """The requested portfolio could not be completed under its rules."""

    def __init__(self, message, retryable=False):
        super().__init__(message)
        self.retryable = retryable


def wave_lineup_targets(target, wave_mix):
    if not np.isclose(sum(wave_mix.values()), 100):
        raise PortfolioError("Wave mix must total 100% before building a portfolio.")
    raw = {k: target * float(v) / 100 for k, v in wave_mix.items()}
    quotas = {k: int(np.floor(v)) for k, v in raw.items()}
    for k in sorted(raw, key=lambda k: raw[k] - quotas[k], reverse=True)[:target-sum(quotas.values())]:
        quotas[k] += 1
    return quotas


def automatic_exposure_caps(salaries, projections, cut_prob, ownership):
    """Conservative allocation heuristics, not calibrated win probabilities.

    A salary-tier ceiling limits concentration; relative projection/cut strength
    and estimated ownership set a lower cap inside that tier.
    """
    salary = np.asarray(salaries, dtype=float)
    def rank(values):
        return pd.Series(values).rank(pct=True).to_numpy()
    strength = .55 * rank(cut_prob) + .45 * rank(projections)
    low = np.select([salary < 7000, salary < 8000, salary < 9000], [10., 15., 20.], default=25.)
    high = np.select([salary < 7000, salary < 8000, salary < 9000], [18., 25., 35.], default=50.)
    # Ownership is only a modest allocation signal because it is estimated.
    own = np.clip(np.asarray(ownership, dtype=float), 0, 100)
    caps = low + (high-low) * (.85*strength + .15*np.clip(own/20., 0, 1))
    return np.floor(caps).astype(int)


def generate_pga_candidates(ids, salaries, projections, ownership, n, min_salary,
                            seed, locked_ids=(), excluded_ids=(), waves=None,
                            wave_targets=None):
    """Fill the last roster spot from its legal salary/wave range.

    This avoids rejecting hundreds of fully random rosters for each legal one
    when the salary floor is close to $50K. Wave buckets receive their own
    candidate budgets so a rare requested construction isn't starved.
    """
    ids = np.asarray(ids, dtype=int)
    salaries = np.asarray(salaries, dtype=int)
    own = np.asarray(ownership, dtype=float)
    rng = np.random.default_rng(seed)
    locked_ids, excluded_ids = set(locked_ids), set(excluded_ids)
    if locked_ids & excluded_ids or not locked_ids.issubset(set(ids)):
        raise PortfolioError("A locked golfer is excluded or missing from the slate.")
    active = np.array([pid not in excluded_ids for pid in ids])
    locked = np.flatnonzero(np.isin(ids, list(locked_ids)))
    avail = np.flatnonzero(active & ~np.isin(ids, list(locked_ids)))
    need = 6-len(locked)
    if need < 0 or len(avail) < need:
        raise PortfolioError("The pool needs six included golfers and at most six locks.")
    value = np.asarray(projections)/np.maximum(salaries, 1)*1000
    z = (value-value.mean())/(value.std()+1e-9)
    weights = np.exp(np.clip(.45*z, -2, 2))
    wave = np.asarray(waves) if waves is not None else np.full(len(ids), "TBD")
    if wave_targets:
        if np.any(active & ~np.isin(wave, ["AM", "PM"])):
            raise PortfolioError("Wave mix needs AM/PM tee times for every included golfer.")
        quotas = {k: v for k, v in wave_targets.items() if v > 0}
        budgets = wave_lineup_targets(n, {k: v/sum(quotas.values())*100 for k, v in quotas.items()})
    else:
        budgets = {None: n}
    seen, out = set(), []
    locked_salary = int(salaries[locked].sum())
    locked_am = int(np.sum(wave[locked] == "AM"))
    for am_total, budget in budgets.items():
        if am_total is not None:
            am_need = am_total-locked_am
            if not 0 <= am_need <= need:
                continue
            if np.sum(wave[avail] == "AM") < am_need or np.sum(wave[avail] == "PM") < need-am_need:
                continue
        added = 0
        for _ in range(max(2000, budget*40)):
            if added >= budget:
                break
            if need == 0:
                pick = np.array([], dtype=int)
            else:
                if am_total is None:
                    first = rng.choice(avail, size=need-1, replace=False, p=weights[avail]/weights[avail].sum())
                    last_wave = None
                else:
                    # Randomize which wave supplies the salary-constrained final spot.
                    labels = np.array(["AM"]*am_need + ["PM"]*(need-am_need))
                    rng.shuffle(labels)
                    parts = []
                    for label in ["AM", "PM"]:
                        pool = avail[wave[avail] == label]
                        count = int(np.sum(labels[:-1] == label))
                        if count:
                            parts.extend(rng.choice(pool, size=count, replace=False, p=weights[pool]/weights[pool].sum()))
                    first = np.asarray(parts, dtype=int)
                    last_wave = labels[-1]
                remaining_salary = locked_salary + int(salaries[first].sum())
                legal = avail[~np.isin(avail, first)]
                legal = legal[(salaries[legal] >= min_salary-remaining_salary) &
                              (salaries[legal] <= 50000-remaining_salary)]
                if last_wave is not None:
                    legal = legal[wave[legal] == last_wave]
                if not len(legal):
                    continue
                final = rng.choice(legal, p=weights[legal]/weights[legal].sum())
                pick = np.append(first, final)
            idx = np.concatenate([locked, pick]).astype(int)
            salary = int(salaries[idx].sum())
            if salary < min_salary or salary > 50000:
                continue
            key = tuple(sorted(ids[idx]))
            if key in seen:
                if need == 0:
                    break
                continue
            seen.add(key)
            out.append({"idx": idx, "salary": salary,
                        "own_product": float(np.prod(np.clip(own[idx]/100, .002, .99)))})
            added += 1
    return out


def select_pga_portfolio(results, cands, golfers, target, max_player, max_pair,
                         max_triple, personal_min, personal_max, auto_caps,
                         locked_ids=(), wave_targets=None, time_limit=20):
    """Select exactly target unique lineups with joint exposure/wave constraints.

    Binary golfer-use variables enforce zero-or-at-least-two appearances for
    portfolios of ten or more lineups. A feasible solver incumbent is validated
    even if optimizing the score reaches its time budget.
    """
    if target < 1:
        raise PortfolioError("Request at least one lineup.")
    ids = golfers["ID"].astype(int).to_numpy()
    waves = golfers.get("Wave", pd.Series("TBD", index=golfers.index)).to_numpy()
    locked = set(locked_ids)
    records, seen = [], set()
    for _, row in results.iterrows():
        j = int(row["_candidate"])
        idx = np.asarray(cands[j]["idx"], dtype=int)
        key = tuple(sorted(ids[idx]))
        if len(set(key)) != 6 or not locked.issubset(key) or key in seen:
            continue
        seen.add(key)
        am = int(np.sum(waves[idx] == "AM"))
        if wave_targets is not None and wave_targets.get(am, 0) == 0:
            continue
        records.append((row, key, am))
    if len(records) < target:
        raise PortfolioError(f"Need {target} unique eligible candidates; only {len(records)} are available. Expand the pool or lower the salary floor.", retryable=True)
    player_rows = {int(pid): [] for pid in ids}
    pair_rows, triple_rows = {}, {}
    for j, (_, key, _) in enumerate(records):
        for pid in key:
            player_rows[pid].append(j)
        for combo in combinations(key, 2):
            pair_rows.setdefault(combo, []).append(j)
        for combo in combinations(key, 3):
            triple_rows.setdefault(combo, []).append(j)
    caps, mins = {}, {}
    for i, pid in enumerate(ids):
        pid = int(pid)
        min_count = int(np.ceil(target*personal_min.get(pid, 0)/100-1e-9))
        manual = float(personal_max.get(pid, 100))
        if pid in locked:
            cap_pct = manual
            min_count = target
        else:
            # An explicit per-golfer max overrides the automatic tier cap.
            allocation = manual if manual < 100 else max(float(auto_caps[i]), float(personal_min.get(pid, 0)))
            cap_pct = min(float(max_player), manual, allocation)
        caps[pid] = max(1, int(np.floor(target*cap_pct/100+1e-9))) if cap_pct > 0 else 0
        mins[pid] = min_count
        if min_count > caps[pid]:
            name = str(golfers.iloc[i]["Name"])
            raise PortfolioError(f"{name}: minimum/lock requires {min_count} appearances, but the exposure cap permits {caps[pid]}.")
        if min_count > len(player_rows[pid]):
            raise PortfolioError(f"{golfers.iloc[i]['Name']}: minimum requires {min_count} appearances, but only {len(player_rows[pid])} eligible candidates contain this golfer.", retryable=True)
    if sum(min(caps[p], len(rows)) for p, rows in player_rows.items()) < target*6:
        raise PortfolioError(f"Golfer caps cannot supply {target*6} roster spots. Increase golfer caps or expand the pool.")
    if sum(mins.values()) > target*6:
        raise PortfolioError(f"Golfer minimums require more than {target*6} roster spots.")
    if wave_targets is not None:
        for am, count in wave_targets.items():
            available = sum(rec[2] == am for rec in records)
            if available < count:
                raise PortfolioError(f"Wave mix requires {count} lineups with {am} AM golfers; only {available} eligible candidates match. Change the wave mix, pool, or salary floor.", retryable=True)
    n = len(records)
    used_players = [pid for pid, rows in player_rows.items() if rows]
    total_vars = n+len(used_players)
    rr, cc, vv, lows, highs = [], [], [], [], []
    def constraint(columns, values, lo, hi):
        r = len(lows)
        rr.extend([r]*len(columns)); cc.extend(columns); vv.extend(values)
        lows.append(lo); highs.append(hi)
    constraint(list(range(n)), [1]*n, target, target)
    for k, pid in enumerate(used_players):
        rows = player_rows[pid]
        y = n+k
        constraint(rows+[y], [1]*len(rows)+[-caps[pid]], -np.inf, 0)
        minimum_used = max(2 if target >= 10 else 1, mins[pid])
        constraint(rows+[y], [1]*len(rows)+[-minimum_used], 0, np.inf)
        if mins[pid]:
            constraint([y], [1], 1, 1)
    for rows_by_combo, percent in [(pair_rows, max_pair), (triple_rows, max_triple)]:
        cap = max(1, int(np.floor(target*percent/100+1e-9))) if percent > 0 else 0
        for rows in rows_by_combo.values():
            if len(rows) > cap:
                constraint(rows, [1]*len(rows), -np.inf, cap)
    if wave_targets is not None:
        for am, count in wave_targets.items():
            columns = [j for j, rec in enumerate(records) if rec[2] == am]
            constraint(columns, [1]*len(columns), count, count)
    matrix = coo_matrix((vv, (rr, cc)), shape=(len(lows), total_vars)).tocsc()
    scores = np.array([float(rec[0]["NUKE Score"]) for rec in records])
    scores = np.nan_to_num(scores)
    objective = np.concatenate([-scores, np.zeros(len(used_players))])
    solved = milp(objective, integrality=np.ones(total_vars), bounds=Bounds(0, 1),
                  constraints=LinearConstraint(matrix, lows, highs),
                  options={"time_limit": time_limit, "mip_rel_gap": .02})
    if solved.x is None:
        if solved.status == 2:
            raise PortfolioError("No complete portfolio exists in these candidates under the combined golfer caps/minimums, pair/triple caps, and exact wave quotas. Increase caps, expand the pool, or change the wave mix; no partial portfolio was saved.", retryable=True)
        raise PortfolioError("Portfolio search reached its time budget without a complete valid solution. Retry with more candidates or loosen exposure/wave constraints; no partial portfolio was saved.", retryable=True)
    binary = np.rint(solved.x)
    actual = matrix @ binary
    if np.any(np.abs(solved.x-binary) > 1e-5) or np.any(actual < np.asarray(lows)-1e-5) or np.any(actual > np.asarray(highs)+1e-5):
        raise PortfolioError("Portfolio search did not produce a fully valid solution; no partial portfolio was saved.")
    chosen = np.flatnonzero(binary[:n])
    portfolio = pd.DataFrame([records[j][0] for j in chosen]).sort_values("NUKE Score", ascending=False).reset_index(drop=True)
    if len(portfolio) != target:
        raise PortfolioError(f"Expected {target} lineups, got {len(portfolio)}; no partial portfolio was saved.")
    portfolio.attrs["exposure_caps"] = caps
    return portfolio
