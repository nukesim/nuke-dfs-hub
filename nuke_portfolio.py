import numpy as np
import pandas as pd

PORTFOLIO_ENGINE_VERSION = "Portfolio Engine V3"


def _z(v):
    v = np.asarray(v, dtype=float)
    sd = np.std(v)
    return (v - np.mean(v)) / (sd if sd > 1e-9 else 1.0)


def _overlap(a, b):
    return len(set(a) & set(b))


def build_portfolio(
    contest_results,
    size=20,
    max_overlap=7,
    path_balance=1.25,
    leverage_weight=0.0,
    max_player_exposure=0.45,
    max_qb_exposure=0.30,
):
    """Build an MME portfolio around tournament upside with exposure controls.

    V3 keeps duplication out of portfolio selection and adds explicit portfolio-management
    guardrails. Player and QB caps are hard constraints while enough eligible lineups remain;
    overlap is also enforced and only relaxed as a last resort to finish the requested portfolio.
    """
    if contest_results is None or contest_results.empty:
        return pd.DataFrame()

    x = contest_results.reset_index(drop=True).copy()
    n = len(x)
    size = max(1, min(int(size), n))
    max_overlap = int(np.clip(max_overlap, 0, 8))
    max_player_exposure = float(np.clip(max_player_exposure, 0.01, 1.0))
    max_qb_exposure = float(np.clip(max_qb_exposure, 0.01, 1.0))
    max_player_count = max(1, int(np.floor(size * max_player_exposure + 1e-9)))
    max_qb_count = max(1, int(np.floor(size * max_qb_exposure + 1e-9)))

    roi = pd.to_numeric(x.get("Sim ROI %", 0), errors="coerce").fillna(0).to_numpy(float)
    win = pd.to_numeric(x.get("1st %", 0), errors="coerce").fillna(0).to_numpy(float)
    top01 = pd.to_numeric(x.get("Top 0.1%", 0), errors="coerce").fillna(0).to_numpy(float)
    top1 = pd.to_numeric(x.get("Top 1%", 0), errors="coerce").fillna(0).to_numpy(float)
    ceiling = pd.to_numeric(x.get("Ceiling 95", 0), errors="coerce").fillna(0).to_numpy(float)
    nuke = pd.to_numeric(x.get("NUKE Score", 0), errors="coerce").fillna(0).to_numpy(float)
    path_score = pd.to_numeric(x.get("Path Score", 50), errors="coerce").fillna(50).to_numpy(float)

    base = (
        0.75 * _z(roi)
        + 0.90 * _z(win)
        + 0.75 * _z(top01)
        + 0.45 * _z(top1)
        + 0.55 * _z(ceiling)
        + 0.30 * _z(nuke)
        + 0.15 * _z(path_score)
    )

    path_series = x.get("Strongest Path", pd.Series(["UNKNOWN"] * n)).fillna("UNKNOWN").astype(str)
    qb_series = x.get("QB", pd.Series(["UNKNOWN"] * n)).fillna("UNKNOWN").astype(str)
    stack_series = x.get("Stack", pd.Series(["UNKNOWN"] * n)).fillna("UNKNOWN").astype(str)

    support_floor = max(2, int(np.ceil(size * 0.015)))
    path_support = path_series.value_counts().to_dict()
    viable_paths = [p for p, c in path_support.items() if c >= support_floor]
    if not viable_paths:
        viable_paths = list(path_support.keys()) or ["UNKNOWN"]
    target_per_path = max(1.0, size / max(1, len(viable_paths)))

    selected, path_counts, qb_counts, stack_counts, player_counts, reasons = [], {}, {}, {}, {}, {}

    def exposure_ok(i):
        lu = list(x.loc[i, "_indices"]) if "_indices" in x.columns else []
        if any(player_counts.get(int(pid), 0) >= max_player_count for pid in lu):
            return False
        qb = qb_series.iloc[i]
        if qb_counts.get(qb, 0) >= max_qb_count:
            return False
        return True

    for pick in range(size):
        best_i, best_score, best_reason = None, -1e18, ""
        for i in range(n):
            if i in selected or not exposure_ok(i):
                continue

            lu = x.loc[i, "_indices"] if "_indices" in x.columns else []
            path, qb, stack = path_series.iloc[i], qb_series.iloc[i], stack_series.iloc[i]
            overlaps = [_overlap(lu, x.loc[j, "_indices"] if "_indices" in x.columns else []) for j in selected]
            worst_overlap = max(overlaps) if overlaps else 0
            avg_overlap = float(np.mean(overlaps)) if overlaps else 0.0
            if overlaps and worst_overlap > max_overlap:
                continue

            current_path = path_counts.get(path, 0)
            if path in viable_paths:
                saturation = current_path / target_per_path
                path_adjustment = float(path_balance) * (0.55 * max(0.0, 1.0 - saturation) - 0.42 * max(0.0, saturation - 1.0) ** 2)
            else:
                path_adjustment = 0.0

            denom = max(1, len(selected))
            qb_share = qb_counts.get(qb, 0) / denom
            stack_share = stack_counts.get(stack, 0) / denom
            concentration_penalty = 0.25 * max(0.0, qb_share - 0.20) + 0.10 * max(0.0, stack_share - 0.55)
            redundancy_penalty = 0.10 * max(0.0, avg_overlap - 5.25) + 0.16 * max(0.0, worst_overlap - 6)
            score = float(base[i] + path_adjustment - concentration_penalty - redundancy_penalty)

            if score > best_score:
                best_i, best_score = i, score
                best_reason = f"GPP upside | {path} | max overlap {worst_overlap} | path adj {path_adjustment:+.2f}"

        if best_i is None:
            # First relax overlap, but keep exposure caps intact.
            remaining = [i for i in range(n) if i not in selected and exposure_ok(i)]
            if remaining:
                best_i = max(remaining, key=lambda i: base[i])
                best_reason = "Best remaining GPP upside; overlap relaxed to complete portfolio"
            else:
                # Only if the requested size cannot be achieved under the selected caps do we stop.
                break

        selected.append(best_i)
        path, qb, stack = path_series.iloc[best_i], qb_series.iloc[best_i], stack_series.iloc[best_i]
        path_counts[path] = path_counts.get(path, 0) + 1
        qb_counts[qb] = qb_counts.get(qb, 0) + 1
        stack_counts[stack] = stack_counts.get(stack, 0) + 1
        if "_indices" in x.columns:
            for pid in x.loc[best_i, "_indices"]:
                pid = int(pid)
                player_counts[pid] = player_counts.get(pid, 0) + 1
        reasons[best_i] = best_reason

    out = x.iloc[selected].copy().reset_index(drop=True)
    if not out.empty:
        out.insert(0, "Portfolio Slot", np.arange(1, len(out) + 1))
        out["Portfolio Reason"] = [reasons[i] for i in selected]
    out.attrs["requested_size"] = size
    out.attrs["max_player_exposure"] = max_player_exposure
    out.attrs["max_qb_exposure"] = max_qb_exposure
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
        "requested_lineups": int(portfolio.attrs.get("requested_size", len(portfolio))),
        "avg_roi": float(pd.to_numeric(portfolio.get("Sim ROI %", 0), errors="coerce").fillna(0).mean()),
        "paths": int(portfolio.get("Strongest Path", pd.Series(dtype=str)).nunique()),
        "qbs": int(portfolio.get("QB", pd.Series(dtype=str)).nunique()),
        "engine": PORTFOLIO_ENGINE_VERSION,
        "max_player_exposure": float(portfolio.attrs.get("max_player_exposure", 1.0)),
        "max_qb_exposure": float(portfolio.attrs.get("max_qb_exposure", 1.0)),
    }
    return path_df, stats


def portfolio_player_exposure(players, portfolio):
    if players is None or portfolio is None or portfolio.empty or "_indices" not in portfolio.columns:
        return pd.DataFrame()
    counts = {}
    for lu in portfolio["_indices"]:
        for pid in lu:
            pid = int(pid)
            counts[pid] = counts.get(pid, 0) + 1
    rows = []
    for pid, count in counts.items():
        p = players.iloc[pid]
        rows.append({
            "Player": p.Name,
            "Pos": p.Position,
            "Team": p.Team,
            "Salary": int(p.Salary),
            "Lineups": int(count),
            "Exposure %": round(100.0 * count / len(portfolio), 1),
        })
    return pd.DataFrame(rows).sort_values(["Exposure %", "Salary"], ascending=[False, False]).reset_index(drop=True)


def portfolio_qb_exposure(portfolio):
    if portfolio is None or portfolio.empty or "QB" not in portfolio.columns:
        return pd.DataFrame()
    c = portfolio["QB"].fillna("UNKNOWN").astype(str).value_counts()
    return pd.DataFrame({
        "QB": c.index,
        "Lineups": c.values,
        "Exposure %": np.round(100.0 * c.values / len(portfolio), 1),
    }).reset_index(drop=True)
