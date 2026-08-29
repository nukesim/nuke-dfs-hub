import numpy as np
import pandas as pd


def lineup_score_matrix(results, player_matrix):
    if results is None or results.empty:
        return np.empty((0, 0), dtype=np.float32)
    cols = [player_matrix[:, list(lu)].sum(axis=1) for lu in results["_indices"]]
    return np.stack(cols, axis=1).astype(np.float32)


def _field_weights(results):
    r = results.reset_index(drop=True)
    salary = pd.to_numeric(r["Salary"], errors="coerce").fillna(49000).to_numpy(float)
    nuke = pd.to_numeric(r["NUKE Score"], errors="coerce").fillna(0).to_numpy(float)
    ceiling = pd.to_numeric(r["Ceiling 95"], errors="coerce").fillna(0).to_numpy(float)

    def z(v):
        sd = np.std(v)
        return (v - np.mean(v)) / (sd if sd > 1e-9 else 1.0)

    logit = 0.95 * z(salary) + 0.45 * z(nuke) + 0.25 * z(ceiling)
    stack = r.get("Stack", pd.Series([""] * len(r))).astype(str)
    logit += np.where(stack.str.startswith("QB + 1"), 0.18, 0.0)
    logit = np.clip(logit, -6, 6)
    w = np.exp(logit)
    return w / w.sum()


def _payout_curve(field_size, entry_fee, first_prize=None, rake=0.15, cash_rate=0.20):
    field_size = max(2, int(field_size))
    entry_fee = max(0.01, float(entry_fee))
    prize_pool = field_size * entry_fee * (1.0 - float(rake))
    paid = max(1, int(round(field_size * float(cash_rate))))
    if first_prize is None or first_prize <= 0:
        first_prize = min(prize_pool * 0.18, max(entry_fee * 25, prize_pool * 0.10))
    first_prize = min(float(first_prize), prize_pool * 0.60)
    min_cash = entry_fee * 1.5
    bonus_pool = max(0.0, prize_pool - paid * min_cash)
    ranks = np.arange(1, paid + 1, dtype=float)
    weights = 1.0 / np.power(ranks, 0.72)
    weights /= weights.sum()
    payouts = min_cash + bonus_pool * weights
    if paid == 1:
        return np.array([prize_pool], dtype=float)
    remaining = max(0.0, prize_pool - first_prize)
    tail = payouts[1:]
    tail *= remaining / tail.sum() if tail.sum() > 0 else 0
    payouts[0] = first_prize
    payouts[1:] = tail
    return np.maximum.accumulate(payouts[::-1])[::-1]


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
    payouts_override=None,
):
    """Simulate lineups against a generated field using synthetic or imported payouts."""
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

    if payouts_override is not None:
        payouts = np.asarray(payouts_override, dtype=float)
        payouts = payouts[np.isfinite(payouts)]
        if len(payouts) == 0 or np.max(payouts) <= 0:
            raise ValueError("Imported payout ladder does not contain positive payouts.")
        if len(payouts) > field_size:
            payouts = payouts[:field_size]
        payout_model = "Imported DraftKings payout ladder"
    else:
        payouts = _payout_curve(field_size, entry_fee, first_prize, rake, cash_rate)
        payout_model = "Synthetic GPP payout curve"

    paid_places = int(np.count_nonzero(payouts > 0))
    top01_cut = max(1, int(np.ceil(field_size * 0.001)))
    top1_cut = max(1, int(np.ceil(field_size * 0.01)))

    wins = np.zeros(user_n, dtype=float)
    top01 = np.zeros(user_n, dtype=float)
    top1 = np.zeros(user_n, dtype=float)
    cash = np.zeros(user_n, dtype=float)
    payout_sum = np.zeros(user_n, dtype=float)
    rank_sum = np.zeros(user_n, dtype=float)
    dup_sum = np.zeros(user_n, dtype=float)

    for _ in range(iterations):
        sim_row = int(rng.integers(0, n_sims))
        scores = score_mat[sim_row]
        sampled = rng.choice(n_candidates, size=opp_n, replace=True, p=weights)
        field_scores = scores[sampled]
        sampled_counts = np.bincount(sampled, minlength=n_candidates)

        for j, idx in enumerate(user_idx):
            s = scores[idx]
            better = int(np.sum(field_scores > s))
            tied_other = int(np.sum(field_scores == s))
            rank_low = better + 1
            rank_high = better + tied_other + 1
            rank_sum[j] += (rank_low + rank_high) / 2.0
            if rank_low == 1:
                wins[j] += 1.0 / (tied_other + 1.0)
            if rank_low <= top01_cut:
                top01[j] += 1
            if rank_low <= top1_cut:
                top1[j] += 1
            if rank_low <= paid_places:
                cash[j] += 1

            lo = max(1, rank_low)
            hi = min(len(payouts), rank_high)
            if lo <= hi:
                prize_slice = payouts[lo - 1:hi]
                payout_sum[j] += float(prize_slice.sum()) / float(tied_other + 1)
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

    contest_score = out["Sim ROI %"].to_numpy(float) + 12.0 * out["1st %"].to_numpy(float) + 0.35 * out["Top 1%"].to_numpy(float)
    order = np.argsort(-contest_score)
    out = out.iloc[order].reset_index(drop=True)
    out.insert(0, "Contest Rank", np.arange(1, len(out) + 1))

    summary = {
        "field_size": field_size,
        "entry_fee": float(entry_fee),
        "prize_pool_est": float(payouts.sum()),
        "paid_places": paid_places,
        "iterations": iterations,
        "field_model": "Projection-free generated field",
        "payout_model": payout_model,
        "candidate_pool": n_candidates,
    }
    return out, summary
