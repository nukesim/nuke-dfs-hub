import numpy as np
import pandas as pd


def _z(v):
    v = np.asarray(v, dtype=float)
    sd = np.std(v)
    return (v - np.mean(v)) / (sd if sd > 1e-9 else 1.0)


def _overlap(a, b):
    sa, sb = set(a), set(b)
    return len(sa & sb)


def build_portfolio(contest_results, size=20, max_overlap=7, path_balance=1.25, leverage_weight=0.35):
    """Greedy portfolio selection using contest quality + path diversity + lineup uniqueness.

    Path diversification is intentionally *soft*, not a hard equal-allocation rule. The selector
    still prefers the best simulated lineups, but a path that is already heavily represented
    receives an increasing saturation penalty while underrepresented viable paths receive a
    bonus. This keeps one structural archetype from swallowing an MME portfolio simply because
    its raw contest score is modestly higher.
    """
    if contest_results is None or contest_results.empty:
        return pd.DataFrame()

    x = contest_results.reset_index(drop=True).copy()
    n = len(x)
    size = max(1, min(int(size), n))
    max_overlap = int(np.clip(max_overlap, 0, 8))

    roi = pd.to_numeric(x.get("Sim ROI %", 0), errors="coerce").fillna(0).to_numpy(float)
    win = pd.to_numeric(x.get("1st %", 0), errors="coerce").fillna(0).to_numpy(float)
    top1 = pd.to_numeric(x.get("Top 1%", 0), errors="coerce").fillna(0).to_numpy(float)
    dup = pd.to_numeric(x.get("Expected Duplicates", 0), errors="coerce").fillna(0).to_numpy(float)
    path_score = pd.to_numeric(x.get("Path Score", 50), errors="coerce").fillna(50).to_numpy(float)

    base = 1.0*_z(roi) + .65*_z(win) + .35*_z(top1) + .20*_z(path_score) - float(leverage_weight)*_z(dup)

    if "Strongest Path" in x.columns:
        path_series = x["Strongest Path"].fillna("UNKNOWN").astype(str)
    else:
        path_series = pd.Series(["UNKNOWN"] * n)

    # Only paths with enough candidate support are treated as real portfolio alternatives.
    # A single weird lineup should not force representation, while a genuine path should.
    support_floor = max(2, int(np.ceil(size * 0.015)))
    path_support = path_series.value_counts().to_dict()
    viable_paths = [p for p, c in path_support.items() if c >= support_floor]
    if not viable_paths:
        viable_paths = list(path_support.keys()) or ["UNKNOWN"]

    # Equal share is only a reference point for the *penalty curve*; it is not a quota.
    target_per_path = max(1.0, size / max(1, len(viable_paths)))

    selected = []
    path_counts = {}
    reasons = {}

    for pick in range(size):
        best_i, best_score, best_reason = None, -1e18, ""
        for i in range(n):
            if i in selected:
                continue

            lu = x.loc[i, "_indices"] if "_indices" in x.columns else []
            path = path_series.iloc[i]

            overlaps = []
            for j in selected:
                other = x.loc[j, "_indices"] if "_indices" in x.columns else []
                overlaps.append(_overlap(lu, other))
            worst_overlap = max(overlaps) if overlaps else 0
            avg_overlap = float(np.mean(overlaps)) if overlaps else 0.0

            if overlaps and worst_overlap > max_overlap:
                continue

            current = path_counts.get(path, 0)
            if path in viable_paths:
                saturation = current / target_per_path
                underrep_bonus = float(path_balance) * max(0.0, 1.0 - saturation)
                saturation_penalty = float(path_balance) * 1.45 * (saturation ** 2)
                path_adjustment = underrep_bonus - saturation_penalty
            else:
                # Rare/unsupported paths can still make the portfolio if their raw quality is great,
                # but they do not receive a diversification subsidy.
                path_adjustment = 0.0

            uniqueness_bonus = .16 * (9.0 - avg_overlap)
            score = float(base[i] + path_adjustment + uniqueness_bonus)

            if score > best_score:
                best_i = i
                best_score = score
                best_reason = (
                    f"{path} | max overlap {worst_overlap} | "
                    f"path adj {path_adjustment:+.2f}"
                )

        if best_i is None:
            # Relax overlap only when the requested portfolio cannot otherwise be filled.
            remaining = [i for i in range(n) if i not in selected]
            if not remaining:
                break

            def relaxed_score(i):
                path = path_series.iloc[i]
                current = path_counts.get(path, 0)
                if path in viable_paths:
                    saturation = current / target_per_path
                    return base[i] - float(path_balance) * 1.45 * (saturation ** 2)
                return base[i]

            best_i = max(remaining, key=relaxed_score)
            best_reason = "Overlap constraint relaxed to complete portfolio"

        selected.append(best_i)
        path = path_series.iloc[best_i]
        path_counts[path] = path_counts.get(path, 0) + 1
        reasons[best_i] = best_reason

    out = x.iloc[selected].copy().reset_index(drop=True)
    out.insert(0, "Portfolio Slot", np.arange(1, len(out) + 1))
    out["Portfolio Reason"] = [reasons[i] for i in selected]
    return out


def portfolio_summary(portfolio):
    if portfolio is None or portfolio.empty:
        return pd.DataFrame(), {}
    path = portfolio.get("Strongest Path", pd.Series(["UNKNOWN"] * len(portfolio))).value_counts()
    path_df = pd.DataFrame({
        "Path": path.index,
        "Lineups": path.values,
        "Portfolio %": np.round(100 * path.values / len(portfolio), 1),
    }).reset_index(drop=True)
    stats = {
        "lineups": len(portfolio),
        "avg_roi": float(pd.to_numeric(portfolio.get("Sim ROI %", 0), errors="coerce").fillna(0).mean()),
        "avg_dup": float(pd.to_numeric(portfolio.get("Expected Duplicates", 0), errors="coerce").fillna(0).mean()),
        "paths": int(portfolio.get("Strongest Path", pd.Series(dtype=str)).nunique()),
    }
    return path_df, stats
