import numpy as np
import pandas as pd

from nuke_field import FIELD_ENGINE_VERSION, field_weights_v1


def lineup_score_matrix(results, player_matrix):
    if results is None or results.empty:
        return np.empty((0, 0), dtype=np.float32)
    cols = [player_matrix[:, list(lu)].sum(axis=1) for lu in results["_indices"]]
    return np.stack(cols, axis=1).astype(np.float32)


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
    user_lineups=None,
    iterations=1000,
    seed=2026,
    rake=0.15,
    cash_rate=0.20,
    payouts_override=None,
    players=None,
):
    """Simulate every candidate lineup against Field Engine V1.

    Field Engine V1 is projection-free. With a player table it uses salary rank,
    inferred role and starter confidence directly. Without one it uses the salary/
    role-driven candidate pool as an ownership proxy, so existing callers remain
    compatible. `user_lineups` is retained only for backwards compatibility.
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
    rng = np.random.default_rng(int(seed))

    weights, field_diag, field_detail = field_weights_v1(r, players)
    field_model = FIELD_ENGINE_VERSION

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

    wins = np.zeros(n_candidates, dtype=float)
    top01 = np.zeros(n_candidates, dtype=float)
    top1 = np.zeros(n_candidates, dtype=float)
    cash = np.zeros(n_candidates, dtype=float)
    payout_sum = np.zeros(n_candidates, dtype=float)
    rank_sum = np.zeros(n_candidates, dtype=float)
    dup_sum = np.zeros(n_candidates, dtype=float)

    payout_cum = np.concatenate(([0.0], np.cumsum(payouts, dtype=float)))
    payout_len = len(payouts)

    for _ in range(iterations):
        sim_row = int(rng.integers(0, n_sims))
        scores = score_mat[sim_row]
        sampled = rng.choice(n_candidates, size=opp_n, replace=True, p=weights)
        field_scores = np.sort(scores[sampled])
        sampled_counts = np.bincount(sampled, minlength=n_candidates)

        left = np.searchsorted(field_scores, scores, side="left")
        right = np.searchsorted(field_scores, scores, side="right")
        tied_other = right - left
        better = opp_n - right
        rank_low = better + 1
        rank_high = better + tied_other + 1
        tie_size = tied_other + 1

        rank_sum += (rank_low + rank_high) / 2.0
        wins += np.where(rank_low == 1, 1.0 / tie_size, 0.0)
        top01 += rank_low <= top01_cut
        top1 += rank_low <= top1_cut
        cash += rank_low <= paid_places
        dup_sum += sampled_counts

        lo = np.clip(rank_low - 1, 0, payout_len)
        hi = np.clip(rank_high, 0, payout_len)
        valid = hi > lo
        prizes = np.zeros(n_candidates, dtype=float)
        prizes[valid] = (payout_cum[hi[valid]] - payout_cum[lo[valid]]) / tie_size[valid]
        payout_sum += prizes

    out = r.copy()
    out["1st %"] = np.round(100 * wins / iterations, 3)
    out["Top 0.1%"] = np.round(100 * top01 / iterations, 2)
    out["Top 1%"] = np.round(100 * top1 / iterations, 2)
    out["Cash %"] = np.round(100 * cash / iterations, 2)
    out["Avg Finish"] = np.round(rank_sum / iterations, 1)
    out["Expected Duplicates"] = np.round(dup_sum / iterations, 2)
    out["Avg Payout"] = np.round(payout_sum / iterations, 2)
    out["Sim ROI %"] = np.round(100 * ((payout_sum / iterations) - entry_fee) / entry_fee, 1)
    out["Field Popularity"] = np.round(100 * weights, 3)
    for c in field_detail.columns:
        out[c] = field_detail[c].to_numpy()

    contest_score = out["Sim ROI %"].to_numpy(float) + 12.0*out["1st %"].to_numpy(float) + 0.35*out["Top 1%"].to_numpy(float)
    order = np.argsort(-contest_score)
    out = out.iloc[order].reset_index(drop=True)
    out.insert(0, "Contest Rank", np.arange(1, len(out) + 1))

    summary = {
        "field_size": field_size,
        "entry_fee": float(entry_fee),
        "prize_pool_est": float(payouts.sum()),
        "paid_places": paid_places,
        "iterations": iterations,
        "field_model": field_model,
        "payout_model": payout_model,
        "candidate_pool": n_candidates,
        "contest_simmed_lineups": n_candidates,
        **field_diag,
    }
    return out, summary
