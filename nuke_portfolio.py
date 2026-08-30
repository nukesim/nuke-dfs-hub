import itertools
import numpy as np
import pandas as pd

PORTFOLIO_ENGINE_VERSION = "Portfolio Engine V5.2"


def _z(v):
    v = np.asarray(v, dtype=float)
    sd = np.std(v)
    return (v - np.mean(v)) / (sd if sd > 1e-9 else 1.0)


def _overlap(a, b):
    return len(set(a) & set(b))


def _normalize_player_preferences(player_preferences, size, default_max):
    prefs = {}
    if not player_preferences:
        return prefs
    for raw_pid, raw in player_preferences.items():
        try:
            pid = int(raw_pid)
        except Exception:
            continue
        raw = raw or {}
        boost = float(np.clip(raw.get("boost", 0.0), -3.0, 3.0))
        min_exp = float(np.clip(raw.get("min", 0.0), 0.0, 1.0))
        max_exp = float(np.clip(raw.get("max", default_max), 0.0, 1.0))
        if max_exp < min_exp:
            max_exp = min_exp
        prefs[pid] = {
            "boost": boost,
            "min": min_exp,
            "max": max_exp,
            "min_count": int(np.ceil(size * min_exp - 1e-9)),
            "max_count": int(np.floor(size * max_exp + 1e-9)),
        }
    return prefs


def _lineup_team_game_sets(players, lineup_ids):
    team_sets, game_sets = [], []
    if players is None or len(players) == 0:
        return [set() for _ in lineup_ids], [set() for _ in lineup_ids]
    for lu in lineup_ids:
        teams, games = set(), set()
        for pid in lu:
            if pid < 0 or pid >= len(players):
                continue
            p = players.iloc[int(pid)]
            team = str(getattr(p, "Team", "")).strip()
            game = str(getattr(p, "Game", "")).strip()
            if team and team.lower() != "nan":
                teams.add(team)
            if game and game.lower() != "nan":
                games.add(game)
        team_sets.append(teams)
        game_sets.append(games)
    return team_sets, game_sets


def build_portfolio(
    contest_results,
    size=20,
    max_overlap=7,
    path_balance=1.25,
    leverage_weight=0.0,
    max_player_exposure=0.45,
    max_qb_exposure=0.30,
    player_preferences=None,
    players=None,
    max_team_exposure=1.0,
    max_game_exposure=1.0,
):
    """Build an MME portfolio around GPP upside with portfolio-level controls.

    V5.2 keeps player/team/game caps and adds soft repeated pair / 3-player core control while retaining soft
    path/concentration penalties. Team/game exposure means the share of portfolio lineups
    containing at least one player from that team/game. These controls shape portfolio
    construction only and do not alter football outcomes.
    """
    if contest_results is None or contest_results.empty:
        return pd.DataFrame()

    x = contest_results.reset_index(drop=True).copy()
    n = len(x)
    size = max(1, min(int(size), n))
    max_overlap = int(np.clip(max_overlap, 0, 8))
    max_player_exposure = float(np.clip(max_player_exposure, 0.01, 1.0))
    max_qb_exposure = float(np.clip(max_qb_exposure, 0.01, 1.0))
    max_team_exposure = float(np.clip(max_team_exposure, 0.01, 1.0))
    max_game_exposure = float(np.clip(max_game_exposure, 0.01, 1.0))
    global_max_player_count = max(1, int(np.floor(size * max_player_exposure + 1e-9)))
    max_qb_count = max(1, int(np.floor(size * max_qb_exposure + 1e-9)))
    max_team_count = max(1, int(np.floor(size * max_team_exposure + 1e-9)))
    max_game_count = max(1, int(np.floor(size * max_game_exposure + 1e-9)))
    prefs = _normalize_player_preferences(player_preferences, size, max_player_exposure)

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
    lineup_ids = [list(map(int, lu)) for lu in x["_indices"]] if "_indices" in x.columns else [[] for _ in range(n)]
    lineup_teams, lineup_games = _lineup_team_game_sets(players, lineup_ids)

    preference_adjustment = np.zeros(n, dtype=float)
    for i, lu in enumerate(lineup_ids):
        preference_adjustment[i] = sum(0.42 * prefs.get(pid, {}).get("boost", 0.0) for pid in lu)

    support_floor = max(2, int(np.ceil(size * 0.015)))
    path_support = path_series.value_counts().to_dict()
    viable_paths = [p for p, c in path_support.items() if c >= support_floor]
    if not viable_paths:
        viable_paths = list(path_support.keys()) or ["UNKNOWN"]
    target_per_path = max(1.0, size / max(1, len(viable_paths)))

    selected, path_counts, qb_counts, stack_counts = [], {}, {}, {}
    player_counts, team_counts, game_counts, reasons = {}, {}, {}, {}
    pair_counts, triple_counts = {}, {}

    def lineup_pairs(lu):
        return [tuple(sorted(x)) for x in itertools.combinations(sorted(set(lu)), 2)]

    def lineup_triples(lu):
        return [tuple(sorted(x)) for x in itertools.combinations(sorted(set(lu)), 3)]

    def player_max_count(pid):
        return prefs.get(pid, {}).get("max_count", global_max_player_count)

    def exposure_ok(i):
        lu = lineup_ids[i]
        if any(player_counts.get(pid, 0) >= player_max_count(pid) for pid in lu):
            return False
        qb = qb_series.iloc[i]
        if qb_counts.get(qb, 0) >= max_qb_count:
            return False
        if any(team_counts.get(team, 0) >= max_team_count for team in lineup_teams[i]):
            return False
        if any(game_counts.get(game, 0) >= max_game_count for game in lineup_games[i]):
            return False
        return True

    for pick in range(size):
        best_i, best_score, best_reason = None, -1e18, ""
        slots_left_after_pick = size - pick - 1
        for i in range(n):
            if i in selected or not exposure_ok(i):
                continue

            lu = lineup_ids[i]
            path, qb, stack = path_series.iloc[i], qb_series.iloc[i], stack_series.iloc[i]
            overlaps = [_overlap(lu, lineup_ids[j]) for j in selected]
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

            # V5.1 marginal path-value control. This is deliberately a SOFT guard, not a
            # forced quota: a dominant path can still earn more portfolio slots when its
            # lineup quality is sufficiently better than alternatives. But after 45% of
            # the portfolio, every additional lineup from that same path must overcome a
            # rapidly increasing concentration cost.
            next_path_share = (current_path + 1) / max(1, len(selected) + 1)
            dominance_penalty = 0.0
            if path in viable_paths and next_path_share > 0.45:
                excess_units = (next_path_share - 0.45) / 0.10
                dominance_penalty = float(path_balance) * (0.90 * excess_units + 0.50 * excess_units ** 2)

            denom = max(1, len(selected))
            qb_share = qb_counts.get(qb, 0) / denom
            stack_share = stack_counts.get(stack, 0) / denom
            concentration_penalty = 0.25 * max(0.0, qb_share - 0.20) + 0.10 * max(0.0, stack_share - 0.55)
            redundancy_penalty = 0.10 * max(0.0, avg_overlap - 5.25) + 0.16 * max(0.0, worst_overlap - 6)

            # V5.2 core diversity: individual exposures can look healthy while the same
            # 2- and 3-player cores quietly repeat across many lineups. Penalize the
            # marginal repetition of those cores without hard-banning strong combinations.
            lu_pairs = lineup_pairs(lu)
            lu_triples = lineup_triples(lu)
            max_pair_repeat = max((pair_counts.get(core, 0) for core in lu_pairs), default=0)
            max_triple_repeat = max((triple_counts.get(core, 0) for core in lu_triples), default=0)
            pair_repeat_load = sum(max(0, pair_counts.get(core, 0) - 4) for core in lu_pairs)
            triple_repeat_load = sum(max(0, triple_counts.get(core, 0) - 2) for core in lu_triples)
            core_penalty = (
                0.035 * pair_repeat_load
                + 0.075 * triple_repeat_load
                + 0.08 * max(0, max_pair_repeat - 10) ** 1.35
                + 0.16 * max(0, max_triple_repeat - 6) ** 1.45
            )

            min_bonus = 0.0
            for pid in lu:
                need = max(0, prefs.get(pid, {}).get("min_count", 0) - player_counts.get(pid, 0))
                if need:
                    urgency = need / max(1, slots_left_after_pick + 1)
                    min_bonus += 1.10 + 2.40 * urgency

            score = float(base[i] + preference_adjustment[i] + min_bonus + path_adjustment - dominance_penalty - concentration_penalty - redundancy_penalty - core_penalty)
            if score > best_score:
                best_i, best_score = i, score
                takes = sum(1 for pid in lu if abs(prefs.get(pid, {}).get("boost", 0.0)) > 1e-9 or prefs.get(pid, {}).get("min", 0.0) > 0)
                best_reason = f"GPP upside | {path} | player takes {takes} | max overlap {worst_overlap} | pair repeat {max_pair_repeat} | 3-core repeat {max_triple_repeat}"

        if best_i is None:
            remaining = [i for i in range(n) if i not in selected and exposure_ok(i)]
            if remaining:
                best_i = max(remaining, key=lambda i: base[i] + preference_adjustment[i])
                best_reason = "Best remaining GPP upside; overlap relaxed to complete portfolio"
            else:
                break

        selected.append(best_i)
        path, qb, stack = path_series.iloc[best_i], qb_series.iloc[best_i], stack_series.iloc[best_i]
        path_counts[path] = path_counts.get(path, 0) + 1
        qb_counts[qb] = qb_counts.get(qb, 0) + 1
        stack_counts[stack] = stack_counts.get(stack, 0) + 1
        for pid in lineup_ids[best_i]:
            player_counts[pid] = player_counts.get(pid, 0) + 1
        for team in lineup_teams[best_i]:
            team_counts[team] = team_counts.get(team, 0) + 1
        for game in lineup_games[best_i]:
            game_counts[game] = game_counts.get(game, 0) + 1
        for core in lineup_pairs(lineup_ids[best_i]):
            pair_counts[core] = pair_counts.get(core, 0) + 1
        for core in lineup_triples(lineup_ids[best_i]):
            triple_counts[core] = triple_counts.get(core, 0) + 1
        reasons[best_i] = best_reason

    out = x.iloc[selected].copy().reset_index(drop=True)
    if not out.empty:
        out.insert(0, "Portfolio Slot", np.arange(1, len(out) + 1))
        out["Portfolio Reason"] = [reasons[i] for i in selected]
    out.attrs["requested_size"] = size
    out.attrs["max_player_exposure"] = max_player_exposure
    out.attrs["max_qb_exposure"] = max_qb_exposure
    out.attrs["max_team_exposure"] = max_team_exposure
    out.attrs["max_game_exposure"] = max_game_exposure
    out.attrs["path_soft_cap"] = 0.45
    out.attrs["player_preferences"] = prefs
    out.attrs["max_pair_repeat"] = max(pair_counts.values(), default=0)
    out.attrs["max_triple_repeat"] = max(triple_counts.values(), default=0)
    unmet = {}
    for pid, pref in prefs.items():
        actual = player_counts.get(pid, 0)
        if actual < pref["min_count"]:
            unmet[pid] = {"requested": pref["min_count"], "actual": actual}
    out.attrs["unmet_minimums"] = unmet
    return out


def portfolio_summary(portfolio):
    if portfolio is None or portfolio.empty:
        return pd.DataFrame(), {}
    path = portfolio.get("Strongest Path", pd.Series(["UNKNOWN"] * len(portfolio))).value_counts()
    path_df = pd.DataFrame({"Path": path.index, "Lineups": path.values, "Portfolio %": np.round(100 * path.values / len(portfolio), 1)}).reset_index(drop=True)
    dominant_path = str(path.index[0]) if len(path) else "UNKNOWN"
    dominant_path_pct = float(100.0 * path.iloc[0] / len(portfolio)) if len(path) else 0.0
    shares = path.to_numpy(float) / max(1, len(portfolio))
    path_hhi = float(np.sum(shares ** 2)) if len(shares) else 0.0
    stats = {
        "lineups": len(portfolio),
        "requested_lineups": int(portfolio.attrs.get("requested_size", len(portfolio))),
        "avg_roi": float(pd.to_numeric(portfolio.get("Sim ROI %", 0), errors="coerce").fillna(0).mean()),
        "paths": int(portfolio.get("Strongest Path", pd.Series(dtype=str)).nunique()),
        "qbs": int(portfolio.get("QB", pd.Series(dtype=str)).nunique()),
        "engine": PORTFOLIO_ENGINE_VERSION,
        "max_player_exposure": float(portfolio.attrs.get("max_player_exposure", 1.0)),
        "max_qb_exposure": float(portfolio.attrs.get("max_qb_exposure", 1.0)),
        "max_team_exposure": float(portfolio.attrs.get("max_team_exposure", 1.0)),
        "max_game_exposure": float(portfolio.attrs.get("max_game_exposure", 1.0)),
        "unmet_minimums": portfolio.attrs.get("unmet_minimums", {}),
        "dominant_path": dominant_path,
        "dominant_path_pct": dominant_path_pct,
        "path_hhi": path_hhi,
        "path_soft_cap": float(portfolio.attrs.get("path_soft_cap", 0.45)),
        "max_pair_repeat": int(portfolio.attrs.get("max_pair_repeat", 0)),
        "max_triple_repeat": int(portfolio.attrs.get("max_triple_repeat", 0)),
    }
    return path_df, stats


def portfolio_player_exposure(players, portfolio):
    if players is None or portfolio is None or portfolio.empty or "_indices" not in portfolio.columns:
        return pd.DataFrame()
    counts = {}
    for lu in portfolio["_indices"]:
        for pid in lu:
            pid = int(pid); counts[pid] = counts.get(pid, 0) + 1
    rows = []
    prefs = portfolio.attrs.get("player_preferences", {})
    for pid, count in counts.items():
        p = players.iloc[pid]; pref = prefs.get(pid, {})
        rows.append({
            "Player": p.Name, "Pos": p.Position, "Team": p.Team, "Salary": int(p.Salary),
            "Lineups": int(count), "Exposure %": round(100.0 * count / len(portfolio), 1),
            "Boost": pref.get("boost", 0.0), "Min %": round(100 * pref.get("min", 0.0), 1),
            "Max %": round(100 * pref.get("max", portfolio.attrs.get("max_player_exposure", 1.0)), 1),
        })
    return pd.DataFrame(rows).sort_values(["Exposure %", "Salary"], ascending=[False, False]).reset_index(drop=True)


def portfolio_qb_exposure(portfolio):
    if portfolio is None or portfolio.empty or "QB" not in portfolio.columns:
        return pd.DataFrame()
    c = portfolio["QB"].fillna("UNKNOWN").astype(str).value_counts()
    return pd.DataFrame({"QB": c.index, "Lineups": c.values, "Exposure %": np.round(100.0 * c.values / len(portfolio), 1)}).reset_index(drop=True)


def portfolio_team_game_exposure(players, portfolio):
    if players is None or portfolio is None or portfolio.empty or "_indices" not in portfolio.columns:
        return pd.DataFrame(), pd.DataFrame()
    lineup_ids = [list(map(int, lu)) for lu in portfolio["_indices"]]
    team_sets, game_sets = _lineup_team_game_sets(players, lineup_ids)
    team_counts, game_counts = {}, {}
    for teams in team_sets:
        for team in teams:
            team_counts[team] = team_counts.get(team, 0) + 1
    for games in game_sets:
        for game in games:
            game_counts[game] = game_counts.get(game, 0) + 1
    team_df = pd.DataFrame([
        {"Team": k, "Lineups": v, "Exposure %": round(100.0 * v / len(portfolio), 1)}
        for k, v in team_counts.items()
    ]).sort_values(["Exposure %", "Team"], ascending=[False, True]).reset_index(drop=True) if team_counts else pd.DataFrame(columns=["Team", "Lineups", "Exposure %"])
    game_df = pd.DataFrame([
        {"Game": k, "Lineups": v, "Exposure %": round(100.0 * v / len(portfolio), 1)}
        for k, v in game_counts.items()
    ]).sort_values(["Exposure %", "Game"], ascending=[False, True]).reset_index(drop=True) if game_counts else pd.DataFrame(columns=["Game", "Lineups", "Exposure %"])
    return team_df, game_df


def portfolio_stack_exposure(portfolio):
    if portfolio is None or portfolio.empty:
        return pd.DataFrame()
    qb = portfolio.get("QB", pd.Series(["UNKNOWN"] * len(portfolio))).fillna("UNKNOWN").astype(str)
    stack = portfolio.get("Stack", pd.Series(["UNKNOWN"] * len(portfolio))).fillna("UNKNOWN").astype(str)
    d = pd.DataFrame({"QB": qb, "Stack": stack})
    c = d.value_counts(["QB", "Stack"]).reset_index(name="Lineups")
    c["Exposure %"] = np.round(100.0 * c["Lineups"] / len(portfolio), 1)
    return c.sort_values(["Exposure %", "QB"], ascending=[False, True]).reset_index(drop=True)


def portfolio_health(players, portfolio):
    if players is None or portfolio is None or portfolio.empty or "_indices" not in portfolio.columns:
        return {"flags": [], "top_core": pd.DataFrame(), "core_count": 0}
    team_df, game_df = portfolio_team_game_exposure(players, portfolio)
    player_df = portfolio_player_exposure(players, portfolio)
    lineup_ids = [tuple(sorted(map(int, lu))) for lu in portfolio["_indices"]]
    core_counts = {}
    for lu in lineup_ids:
        for core in itertools.combinations(lu, 3):
            core_counts[core] = core_counts.get(core, 0) + 1
    rows = []
    for core, count in sorted(core_counts.items(), key=lambda kv: kv[1], reverse=True)[:25]:
        names = [str(players.iloc[pid].Name) for pid in core]
        rows.append({"3-Player Core": " + ".join(names), "Lineups": count, "Exposure %": round(100.0 * count / len(portfolio), 1)})
    core_df = pd.DataFrame(rows)
    flags = []
    if not player_df.empty and float(player_df.iloc[0]["Exposure %"]) >= 45:
        flags.append(f"Player concentration: {player_df.iloc[0]['Player']} appears in {player_df.iloc[0]['Exposure %']:.1f}% of lineups.")
    if not team_df.empty and float(team_df.iloc[0]["Exposure %"]) >= 65:
        flags.append(f"Team concentration: {team_df.iloc[0]['Team']} appears in {team_df.iloc[0]['Exposure %']:.1f}% of lineups.")
    if not game_df.empty and float(game_df.iloc[0]["Exposure %"]) >= 55:
        flags.append(f"Game concentration: {game_df.iloc[0]['Game']} appears in {game_df.iloc[0]['Exposure %']:.1f}% of lineups.")
    if not core_df.empty and float(core_df.iloc[0]["Exposure %"]) >= 25:
        flags.append(f"Core concentration: {core_df.iloc[0]['3-Player Core']} appears together in {core_df.iloc[0]['Exposure %']:.1f}% of lineups.")
    return {"flags": flags, "top_core": core_df, "core_count": len(core_counts)}
