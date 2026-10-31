"""Stable-ID NFL group rules, constructive candidates, and audited portfolio quotas."""
from dataclasses import dataclass
from collections import defaultdict
from itertools import combinations
import math
import time

import numpy as np
import pandas as pd
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_matrix


class RuleError(ValueError):
    """A rule cannot be applied safely; surface the reason to the user."""


@dataclass(frozen=True)
class CompiledRule:
    key: str
    label: str
    anchor: int | None
    members: frozenset
    minimum: int
    maximum: int
    share: float

    def counts(self, lineup):
        s = set(lineup)
        triggered = self.anchor is None or self.anchor in s
        count = len(s & self.members)
        return triggered, self.minimum <= count <= self.maximum


def active_rules(rules):
    return [r for r in (rules or []) if r.get("enabled", True)]


def rule_sentence(rule, names=None):
    names = names or rule.get("names", {})
    name = lambda pid: str(names.get(str(pid), str(pid)))
    anchor = rule.get("anchor_id")
    share = float(rule.get("share", 100))
    when = (f"When {name(anchor)} is used" if anchor else "Across the portfolio")
    how = "every lineup" if share == 100 else f"at least {share:g}% of {'their' if anchor else 'all'} lineups"
    lo, hi = int(rule.get("min_count", 1)), int(rule.get("max_count", 1))
    count = f"exactly {lo}" if lo == hi else f"{lo}–{hi}"
    members = ", ".join(name(pid) for pid in rule.get("member_ids", []))
    return f"{when}, {how} must include {count} {'other ' if anchor else ''}player{'s' if hi != 1 else ''} from {members}."


def compile_rules(players, rules):
    lookup = {str(pid): i for i, pid in enumerate(players.ID)}
    compiled = []
    for number, raw in enumerate(active_rules(rules), 1):
        label = str(raw.get("label") or f"Rule {number}")
        members = list(dict.fromkeys(str(x) for x in raw.get("member_ids", [])))
        anchor_id = str(raw["anchor_id"]) if raw.get("anchor_id") else None
        try:
            lo, hi = int(raw.get("min_count", 1)), int(raw.get("max_count", 1))
            share = float(raw.get("share", 100)) / 100
        except (TypeError, ValueError) as exc:
            raise RuleError(f"{label}: enter whole-player counts and a percentage.") from exc
        if not members or not (0 <= lo <= hi <= len(members)) or hi > (8 if anchor_id else 9):
            raise RuleError(f"{label}: choose a group and valid minimum / maximum counts.")
        if not math.isfinite(share) or not 0 < share <= 1:
            raise RuleError(f"{label}: share must be between 1% and 100%.")
        if anchor_id in members:
            raise RuleError(f"{label}: the anchor is separate and cannot also belong to its group.")
        if anchor_id and anchor_id not in lookup:
            raise RuleError(f"{label}: the anchor is not in the active pool. Include them, edit the rule, or pause it.")
        available = frozenset(lookup[p] for p in members if p in lookup)
        if lo > len(available):
            raise RuleError(f"{label}: needs {lo} group players, but only {len(available)} are in the active pool.")
        compiled.append(CompiledRule(str(raw.get("id", number)), label, lookup.get(anchor_id), available, lo, hi, share))
    for i, a in enumerate(compiled):
        for b in compiled[i + 1:]:
            if a.anchor == b.anchor and a.members == b.members and a.share == b.share == 1:
                if max(a.minimum, b.minimum) > min(a.maximum, b.maximum):
                    raise RuleError(f"{a.label} conflicts with {b.label}: the same group has incompatible counts.")
    return compiled


def rule_report(players, lineups, rules):
    compiled = compile_rules(players, rules)
    lineups = list(lineups)
    rows = []
    for r in compiled:
        outcomes = [r.counts(lu) for lu in lineups]
        triggered = sum(t for t, _ in outcomes)
        matched = sum(t and good for t, good in outcomes)
        required = int(math.ceil(r.share * triggered - 1e-9))
        rows.append({"Rule": r.label, "Applies to": triggered, "Match": matched,
                     "Needed": required, "Actual %": round(100 * matched / triggered, 1) if triggered else None,
                     "Target %": round(100 * r.share, 1),
                     "Status": "Not used" if not triggered else "Met" if matched >= required else "Unmet"})
    return pd.DataFrame(rows)


class _Rows:
    def __init__(self, n):
        self.n = n
        self.rows, self.cols, self.data, self.low, self.high = [], [], [], [], []

    def add(self, values, lo=-np.inf, hi=np.inf):
        row = len(self.low)
        for col, value in values.items():
            if value:
                self.rows.append(row); self.cols.append(int(col)); self.data.append(float(value))
        self.low.append(lo); self.high.append(hi)

    def constraint(self):
        a = coo_matrix((self.data, (self.rows, self.cols)), shape=(len(self.low), self.n)).tocsc()
        return LinearConstraint(a, np.asarray(self.low), np.asarray(self.high))


def _add_group(rows, rule):
    values = {i: 1 for i in rule.members}
    if rule.anchor is None:
        rows.add(values, rule.minimum, rule.maximum)
    else:
        low = dict(values); low[rule.anchor] = -rule.minimum
        high = dict(values); high[rule.anchor] = 9 - rule.maximum
        rows.add(low, lo=0)
        rows.add(high, hi=9)


def _candidate_model(players, compiled, min_salary, site, flex_position, locks):
    from dfs_platform import get_platform
    n = len(players)
    teams = sorted(set(players.Team))
    rows = _Rows(n + len(teams))
    def group(indices, lo=-np.inf, hi=np.inf):
        rows.add({int(i): 1 for i in indices}, lo, hi)
    pos = players.Position.to_numpy()
    team = players.Team.to_numpy()
    game = players.Game.to_numpy()
    rows.add(dict(enumerate(players.Salary.astype(float))), min_salary, get_platform(site).salary_cap)
    group(range(n), 9, 9)
    for p, lo, hi in [("QB", 1, 1), ("RB", 2, 3), ("WR", 3, 4), ("TE", 1, 2), ("DST", 1, 1)]:
        if flex_position == p:
            lo = hi = {"RB": 3, "WR": 4, "TE": 2}.get(p, lo)
        group(np.flatnonzero(pos == p), lo, hi)
    lower = np.zeros(rows.n); upper = np.ones(rows.n)
    for i in locks:
        lower[i] = 1
    for i in np.flatnonzero(pos == "QB"):
        if "auto_qb_eligible" in players and not bool(players.iloc[i].auto_qb_eligible):
            upper[i] = 0
    if np.any(lower > upper):
        raise RuleError("A locked QB is ineligible. Update the QB's role or remove the lock.")
    for j, t in enumerate(teams):
        ti = np.flatnonzero(team == t)
        qbs = [int(i) for i in ti if pos[i] == "QB"]
        wrs = [int(i) for i in ti if pos[i] == "WR"]
        tes = [int(i) for i in ti if pos[i] == "TE"]
        if site == "FD":
            group(ti, hi=4)
        # Each QB needs a receiver or TE from their own team.
        rows.add({**{i: 1 for i in wrs + tes}, **{i: -1 for i in qbs}}, lo=0)
        # Preserve the hub's WR+WR / WR+TE without-QB restriction.
        rows.add({**{i: 1 for i in wrs}, **{i: -3 for i in qbs}}, hi=1)
        flag = n + j
        rows.add({**{i: 1 for i in wrs}, flag: -4}, hi=0)
        rows.add({**{i: -1 for i in wrs}, flag: 1}, hi=0)
        rows.add({**{i: 1 for i in tes}, flag: 2, **{i: -2 for i in qbs}}, hi=2)
    for d in np.flatnonzero(pos == "DST"):
        opposing = np.flatnonzero((game == game[d]) & (team != team[d]) & (pos != "DST"))
        rows.add({**{int(i): 1 for i in opposing}, int(d): 8}, hi=8)
    for r in compiled:
        if r.share == 1:
            _add_group(rows, r)
    return rows, lower, upper


def generate_rule_candidates(players, rules, n_lineups, min_salary, seed, site, flex_position, locks, baseline):
    """Keep normal correlated candidates, then construct additional rule-compatible ones.

    The constructor has a time budget. It never relaxes Every rules or salary / roster
    constraints; the UI reports a short candidate pool if the requested count is not reached.
    """
    compiled = compile_rules(players, rules)
    hard = [r for r in compiled if r.share == 1]
    n_lineups = int(n_lineups)
    p = players.reset_index(drop=True)
    kept, seen = [], set()
    def add(lu):
        key = tuple(sorted(map(int, lu)))
        if key not in seen and all(not r.counts(key)[0] or r.counts(key)[1] for r in hard):
            seen.add(key); kept.append(list(map(int, lu)))
    for lu in baseline():
        add(lu)
    rows, lower, upper = _candidate_model(p, compiled, min_salary, site, str(flex_position or "ANY").upper(), locks)
    rng = np.random.default_rng(seed + 301)
    counts = np.zeros(len(p))
    for lu in kept:
        counts[lu] += 1
    # Seed supporting examples for each rule. Conditional rules never force final anchor exposure.
    tasks = [r for r in compiled for _ in range(min(6, max(2, n_lineups // max(1, 10 * len(compiled)))))]
    attempts, started = 0, time.monotonic()
    while (len(kept) < n_lineups or tasks) and attempts < max(80, n_lineups * 3) and time.monotonic() - started < 45:
        attempts += 1
        task = tasks.pop(0) if tasks else None
        extra = _Rows(rows.n)
        if task:
            if task.anchor is not None:
                extra.add({task.anchor: 1}, 1, 1)
            if task.share < 1:
                _add_group(extra, task)
        else:
            for r in compiled:
                if r.share < 1 and rng.random() < r.share:
                    _add_group(extra, r)
        # Exact no-good cuts for prior constructor solutions; baseline dedup is checked in add().
        for lu in kept[-100:]:
            extra.add({i: 1 for i in lu}, hi=8)
        value = 2.0 * p.market_score.to_numpy(float) + .6 * p.auto_role_multiplier.to_numpy(float)
        value += rng.gumbel(0, 1.5, len(p)) - .7 * counts / max(1, len(kept))
        objective = np.r_[-value, np.zeros(rows.n - len(p))]
        result = milp(objective, integrality=np.ones(rows.n), bounds=Bounds(lower, upper),
                      constraints=[rows.constraint(), extra.constraint()], options={"time_limit": 1.5, "mip_rel_gap": .08})
        if result.x is not None:
            lu = np.flatnonzero(result.x[:len(p)] > .5).tolist()
            from nuke_sim import _valid_lineup
            if len(lu) == 9 and _valid_lineup(lu, p, min_salary, site=site):
                add(lu); counts[lu] += 1
        elif result.status == 2 and task is None and not any(r.share < 1 for r in compiled):
            break
    if not kept:
        raise RuleError("No lineups satisfy these rules, locks, salary range, and roster restrictions. Pause a rule or loosen a count, then try again.")
    # Include the deliberately constructed support examples rather than truncating them away.
    if len(kept) > n_lineups:
        keep_tail = min(len(tasks) + max(2, len(compiled) * 6), n_lineups // 2, len(kept) - n_lineups)
        kept = kept[:n_lineups - keep_tail] + kept[-keep_tail:] if keep_tail else kept[:n_lineups]
    return kept


def select_rule_portfolio(x, players, rules, size, scores, preferred, max_overlap,
                          max_player_exposure, max_qb_exposure, max_team_exposure,
                          max_game_exposure, preferences, path_balance):
    """Exact quotas and caps; use V7 picks as the starting preference, never silently relax."""
    compiled = compile_rules(players, rules)
    size = int(size)
    if len(x) < size:
        raise RuleError(f"Only {len(x)} candidates are available for {size} portfolio slots. Generate more candidates or reduce the portfolio size.")
    ids = [frozenset(map(int, lu)) for lu in x['_indices']]
    # Deduplicate identical rosters even if imported results repeat one.
    n = len(x)
    path_groups = defaultdict(list)
    for i, value in enumerate(x.get("Strongest Path", pd.Series("Unknown", index=x.index)).astype(str)):
        path_groups[value].append(i)
    diverse_paths = list(path_groups.values()) if len(path_groups) > 1 else []
    rows = _Rows(n + len(diverse_paths))
    rows.add(dict.fromkeys(range(n), 1), size, size)
    # A linear saturation cost retains path diversification during exact rule selection.
    for j, indices in enumerate(diverse_paths):
        rows.add({**dict.fromkeys(indices, 1), n + j: -1}, hi=max(1, size / len(diverse_paths)))
    bounds = np.ones(n)
    for r in compiled:
        values = {}
        for i, lu in enumerate(ids):
            triggered, matched = r.counts(lu)
            if triggered:
                values[i] = float(matched) - r.share
                if r.share == 1 and not matched:
                    bounds[i] = 0
        rows.add(values, lo=0)
    occurrences = defaultdict(list)
    teams, games, qbs = defaultdict(list), defaultdict(list), defaultdict(list)
    conflicts = defaultdict(list)
    for i, lu in enumerate(ids):
        for pid in lu:
            occurrences[pid].append(i)
        for t in {str(players.iloc[pid].Team) for pid in lu}:
            teams[t].append(i)
        for g in {str(players.iloc[pid].Game) for pid in lu}:
            games[g].append(i)
        for pid in lu:
            if players.iloc[pid].Position == 'QB':
                qbs[pid].append(i)
        for core in combinations(sorted(lu), int(max_overlap) + 1):
            conflicts[core].append(i)
    def cap(occ, fraction):
        for indices in occ.values():
            rows.add(dict.fromkeys(indices, 1), hi=max(1, math.floor(size * fraction + 1e-9)))
    for pid in set(occurrences) | set(preferences):
        pref = preferences.get(pid, {})
        indices = occurrences.get(pid, [])
        rows.add(dict.fromkeys(indices, 1), pref.get('min_count', 0), pref.get('max_count', max(1, math.floor(size * max_player_exposure + 1e-9))))
    cap(qbs, max_qb_exposure); cap(teams, max_team_exposure); cap(games, max_game_exposure)
    for indices in conflicts.values():
        if len(indices) > 1:
            rows.add(dict.fromkeys(indices, 1), hi=1)
    scores = np.asarray(scores, float)
    objective = scores.copy()
    objective[list(preferred)] += 1.5
    cost = np.r_[-objective, np.full(len(diverse_paths), .4 * max(0, float(path_balance)))]
    upper = np.r_[bounds, np.full(len(diverse_paths), size)]
    result = milp(cost, integrality=np.r_[np.ones(n), np.zeros(len(diverse_paths))],
                  bounds=Bounds(np.zeros(rows.n), upper), constraints=rows.constraint(),
                  options={"time_limit": 15, "mip_rel_gap": .03})
    if result.x is None:
        reason = "These rules and exposure / overlap limits cannot fill the requested portfolio from the current candidates." if result.status == 2 else "The rule solver could not find a verified portfolio within its time limit."
        raise RuleError(reason + " Pause a rule, raise a cap, reduce the size, or generate more candidates. No noncompliant portfolio was substituted.")
    selected = np.flatnonzero(result.x[:n] > .5).tolist()
    if len(selected) != size:
        raise RuleError("The solver did not return the requested number of lineups. No portfolio was applied.")
    # Check all constraints independently before returning / enabling export.
    a = rows.constraint()
    checked = result.x.copy()
    checked[:n] = np.asarray([int(i in selected) for i in range(n)])
    actual = a.A @ checked
    if np.any(checked < -1e-6) or np.any(checked > upper + 1e-6) or np.any(actual < a.lb - 1e-6) or np.any(actual > a.ub + 1e-6):
        raise RuleError("Portfolio validation failed. No portfolio was applied.")
    return sorted(selected, key=lambda i: objective[i], reverse=True)
