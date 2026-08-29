import re
import numpy as np
import pandas as pd


RANK_KEYS = ["rank", "place", "position", "finishing position", "finish"]
PAYOUT_KEYS = ["payout", "prize", "winnings", "cash", "amount"]


def _norm_col(c):
    return re.sub(r"\s+", " ", str(c).strip().lower().replace("_", " "))


def _money(v):
    if pd.isna(v):
        return np.nan
    s = str(v).strip().replace("$", "").replace(",", "")
    s = re.sub(r"[^0-9.\-]", "", s)
    try:
        return float(s)
    except Exception:
        return np.nan


def _rank_range(v):
    if pd.isna(v):
        return None
    s = str(v).strip().lower().replace(",", "")
    nums = [int(x) for x in re.findall(r"\d+", s)]
    if not nums:
        return None
    if len(nums) == 1:
        return nums[0], nums[0]
    return min(nums[0], nums[1]), max(nums[0], nums[1])


def parse_payout_dataframe(df):
    """Parse a DK-style payout table into one payout value per paid rank.

    Accepts flexible rank columns such as Rank/Place/Position and payout columns such as
    Payout/Prize/Winnings. Rank ranges like `11-20` or `11th - 20th` are expanded.
    """
    if df is None or df.empty:
        raise ValueError("Contest payout file is empty.")

    cols = {_norm_col(c): c for c in df.columns}
    rank_col = next((cols[k] for k in RANK_KEYS if k in cols), None)
    payout_col = next((cols[k] for k in PAYOUT_KEYS if k in cols), None)

    if rank_col is None or payout_col is None:
        # Try fuzzy containment for exports with longer header names.
        for norm, orig in cols.items():
            if rank_col is None and any(k in norm for k in RANK_KEYS):
                rank_col = orig
            if payout_col is None and any(k in norm for k in PAYOUT_KEYS):
                payout_col = orig

    if rank_col is None or payout_col is None:
        raise ValueError("Could not find payout columns. Need a rank/place column and payout/prize column.")

    paid = {}
    for _, row in df.iterrows():
        rr = _rank_range(row[rank_col])
        amount = _money(row[payout_col])
        if rr is None or not np.isfinite(amount) or amount <= 0:
            continue
        lo, hi = rr
        if lo < 1 or hi - lo > 100000:
            continue
        for rank in range(lo, hi + 1):
            paid[rank] = float(amount)

    if not paid:
        raise ValueError("No paid ranks could be parsed from this file.")

    max_rank = max(paid)
    payouts = np.zeros(max_rank, dtype=float)
    for rank, amount in paid.items():
        payouts[rank - 1] = amount

    # DK payout ladders should be non-increasing. Preserve user data but fill tiny gaps with 0.
    info = {
        "paid_places": int(np.count_nonzero(payouts > 0)),
        "last_paid_rank": int(max_rank),
        "first_prize": float(payouts[0]) if len(payouts) else 0.0,
        "listed_prize_pool": float(payouts.sum()),
        "rank_column": str(rank_col),
        "payout_column": str(payout_col),
    }
    return payouts, info


def parse_payout_upload(uploaded_file):
    name = str(getattr(uploaded_file, "name", "")).lower()
    if name.endswith(".xlsx") or name.endswith(".xls"):
        df = pd.read_excel(uploaded_file)
    else:
        df = pd.read_csv(uploaded_file)
    return parse_payout_dataframe(df)
