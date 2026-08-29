import numpy as np
import pandas as pd


def lineup_score_matrix(results, player_matrix):
    """Return sims x candidate-lineups score matrix in current results order."""
    if results is None or results.empty:
        return np.empty((0, 0), dtype=np.float32)
    cols = []
    for lu in results["_indices"]:
        cols.append(player_matrix[:, list(lu)].sum(axis=1))
    return np.stack(cols, axis=1).astype(np.float32)


def _field_weights(results):
    """Projection-free proxy for how often the public might land on each candidate."""
    r = results.reset_index(drop=True)
    salary = pd.to_numeric(r["Salary"], errors="coerce").fillna(49000).to_numpy(float)
    nuke = pd.to_numeric(r["NUKE Score"], errors="coerce").fillna(0).to_numpy(float)
    ceiling = pd.to_numeric(r["Ceiling 95"], errors="coerce").fillna(0).to_numpy(float)

    def z(v):
        sd = np.std(v)
        return (v - np.mean(v)) / (sd if sd > 1e-9 else 1.0)

    # Public construction proxy: spends salary and gravitates toward stronger market-like builds.
    logit = 0.95 * z(salary) + 0.45 * z(nuke) + 0.25 * z(ceiling)
    # Slightly reward common QB+1 constructions vs exotic stack shapes.
    stack = r.get("Stack", pd.Series([""] * len(r))).astype(str)
    logit += np.where(stack.str.startswith("QB + 1"), 0.18, 0.0)
    logit = np.clip(logit, -6, 6)
    w = np.exp(logit)
    return w / w.sum()


def _payout_curve(field_size, entry_fee, first_prize=None, rake=0.15, cash_rate=0.20):
    """Create a smooth top-heavy synthetic GPP payout curve.

    This is explicitly an estimate until an actual contest payout CSV is supplied.
    """
    field_size = max(2, int(field_size))
    entry_fee = max(0.01, float(entry_fee))
    prize_pool = field_size * entry_fee * (1.0 - float(rake))
    paid = max(1, int(round(field_size * float(cash_rate))))
    if first_prize is None or first_prize <= 0:
        first_prize = min(prize_pool * 0.18, max(entry_fee * 25, prize_pool * 0.10))
    first_prize = min(float(first_prize), prize_pool * 0.60)

    # Rank weights decay steeply, but reserve enough money for min-cash payouts.
    min_cash = entry_fee * 1.5
    base_pool = paid * min_cash
    bonus_pool = max(0.0, prize_pool - base_pool)
    ranks = np.arange(1, paid + 1, dtype=float)
    weights = 1.0 / np.power(ranks, 0.72)
    weights /= weights.sum()
    payouts = min_cash + bonus_pool * weights

    # Force first to user-selected prize, then renormalize the remaining paid positions.
    if paid == 1:
        return np.array([prize_pool], dtype=float)
    remaining = max(0.0, prize_pool - first_prize)
    tail = payouts[1:]
    tail *= remaining / tail.sum() if tail.sum() > 0 else 0
    payouts[0] = first_prize
    payouts[1:] = tail
    payouts = np.maximum.accumulate(payouts[::-1])[::-1]
    return payouts


def simulate_contest(
    results,
    player_matrix,
    field_size=470,
    entry_fee=25.0,
    first_prize=2500.0,
    user_lineups=50,
    iterations=1000,
    seed=2026,
    rake=0.15,
    cash_rate=0.20,
):
    """Simulate candidate lineups against a generated opponent field.

    Field lineups are sampled from the candidate universe using projection-free public-build
    weights. Duplicate counts arise naturally from sampling with replacement. Metrics are
    estimates, not guarantees and are most useful for comparing lineups to one another.
    """
    if results is None or results.empty:
        return pd.DataFrame(), {}

    r = results.reset_index(drop=True).copy()
    score_mat = lineup_score_matrix(r, player_matrix)
    if score_mat.size == 0:
        return pd.DataFrame(), {}

    n_sims, n_candidates = score_mat.shape
    field_size = max(2, int(field_size))
    opp_n = field_size - 1
    iterations = max(50, int(iterations))
    user_n = max(1, min(int(user_lineups), n_candidates))
    user_idx = np.arange(user_n)
    rng = np.random.default_rng(int(seed))
    weights = _field_weights(r)
    payouts = _payout_curve(field_size, entry_fee, first_prize, rake, cash_rate)
    paid_places = len(payouts)
    top01_cut = max(1, int(np.ceil(field_size * 0.001)))
    top1_cut = max(1, int(np.ceil(field_size * 0.01)))

    wins = np.zeros(user_n, dtype=float)
    top01 = np.zeros(user_n, dtype=float)
    top1 = np.zeros(user_n, dtype=float)
    cash = np.zeros(user_n, dtype=float)
    payout_sum = np.zeros(user_n, dtype=float)
    rank_sum = np.zeros(user_n, dtype=float)
    dup_sum = np.zeros(user_n, dtype=float)

    # Approx expected duplicates from field-generation probabilities.
    expected_dups = opp_n * weights[user_idx]

    for _ in range(iterations):
        sim_row = int(rng.integers(0, n_sims))
        scores = score_mat[sim_row]
        sampled = rng.choice(n_candidates, size=opp_n, replace=True, p=weights)
        field_scores = scores[sampled]
        # Counts let us split tied prizes among duplicate copies of the exact lineup.
        sampled_counts = np.bincount(sampled, minlength=n_candidates)

        for j, idx in enumerate(user_idx):
            s = scores[idx]
            better = int(np.sum(field_scores > s))
            tied_other = int(np.sum(field_scores == s))
            rank_low = better + 1
            rank_high = better + tied_other + 1
            avg_rank = (rank_low + rank_high) / 2.0
            rank_sum[j] += avg_rank
            if rank_low == 1:
                wins[j] += 1.0 / (tied_other + 1.0)
            if rank_low <= top01_cut:
                top01[j] += 1
            if rank_low <= top1_cut:
                top1[j] += 1
            if rank_low <= paid_places:
                cash[j] += 1

            lo = max(1, rank_low)
            hi = min(paid_places, rank_high)
            if lo <= hi:
                prize_slice = payouts[lo - 1:hi]
                # Split the occupied tied-rank prize pool across all tied entries.
                prize = float(prize_slice.sum()) / float(tied_other + 1)
                payout_sum[j] += prize
            dup_sum[j] += sampled_counts[idx]

    out = r.iloc[:user_n].copy()
    out["1st %"] = np.round(100 * wins / iterations, 3)
    out["Top 0.1%"] = np.round(100 * top01 / iterations, 2)
    out["Top 1%"] = np.round(100 * top1 / iterations, 2)
    out["Cash %"] = np.round(100 * cash / iterations, 2)
    out["Avg Finish"] = np.round(rank_sum / iterations, 1)
    out["Expected Duplicates"] = np.round(dup_sum / iterations, 2)
    out["Avg Payout"] = np.round(payout_sum / iterations, 2)
    out["Sim ROI %"] = np.round(100 * ((payout_sum / iterations) - entry_fee) / entry_fee, 1)
    out["Field Popularity"] = np.round(100 * weights[user_idx], 3)

    # Contest-first ranking: ROI with smaller nudges for first-place and top-1% access.
    roi = out["Sim ROI %"].to_numpy(float)
    win = out["1st %"].to_numpy(float)
    t1 = out["Top 1%"].to_numpy(float)
    contest_score = roi + 12.0 * win + 0.35 * t1
    order = np.argsort(-contest_score)
    out = out.iloc[order].reset_index(drop=True)
    out.insert(0, "Contest Rank", np.arange(1, len(out) + 1))

    summary = {
        "field_size": field_size,
        "entry_fee": float(entry_fee),
        "prize_pool_est": float(field_size * entry_fee * (1-rake)),
        "paid_places": paid_places,
        "iterations": iterations,
        "field_model": "Projection-free generated field",
        "payout_model": "Synthetic GPP payout curve",
        "candidate_pool": n_candidates,
    }
    return out, summary
