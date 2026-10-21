"""NBA Classic late-swap optimization with DraftKings roster-slot lock integrity.

Never claim to submit entries automatically. All swaps require users to upload
updated CSVs through the proper DraftKings Edit Entries flow.
"""
from __future__ import annotations

import csv
import io
import re
from collections import Counter
from datetime import datetime, timedelta, timezone

from nuke_nba_data import DK_SLOTS

CAP = 50000
SLOT_WEIGHTS = {"PG": 0.0, "SG": 0.0, "SF": 0.0, "PF": 0.0, "C": 0.0,
                "G": 4.0, "F": 4.0, "UTIL": 10.0}
MODES = ("Ceiling chase", "Balanced GPP", "Protect lead")


def is_locked(player, as_of, buffer_minutes=2):
    """Conservative schedule-based approximation; DK GameCenter is authoritative."""
    cutoff = as_of + timedelta(minutes=float(buffer_minutes))
    return player["start"] <= cutoff


def late_swap_slots(lineup, players, as_of, buffer_minutes=2):
    return tuple(k for k, index in enumerate(lineup)
                 if is_locked(players[index], as_of, buffer_minutes))


def flex_score(lineup, players):
    """Only an ordering preference, never a claimed win-probability edge."""
    all_starts = [p["start"].timestamp() for p in players]
    early, late = min(all_starts), max(all_starts)
    span = max(1.0, late - early)
    return sum(
        SLOT_WEIGHTS[slot] * (players[lineup[k]]["start"].timestamp() - early) / span
        for k, slot in enumerate(DK_SLOTS)
    )


def reorder_for_late_swap(lineup, players, locked_slots=()):
    """Assignment-optimize fixed player IDs: late starters in UTIL > G/F > core.

    Locked spots cannot move, and every new assignment must retain DK position
    eligibility. No salary or player membership changes occur in this operation.
    """
    import numpy as np
    from scipy.optimize import linear_sum_assignment

    if len(lineup) != 8 or len(set(lineup)) != 8:
        raise ValueError("An NBA Classic lineup must contain eight unique players")
    frozen = set(locked_slots)
    open_slots = [i for i in range(8) if i not in frozen]
    indices = [lineup[i] for i in open_slots]
    if not indices:
        return tuple(lineup)
    early = min(p["start"].timestamp() for p in players)
    late = max(p["start"].timestamp() for p in players)
    span = max(1.0, late - early)
    cost = np.full((len(indices), len(open_slots)), 1e8, dtype=float)
    for i, player_index in enumerate(indices):
        p = players[player_index]
        age = (p["start"].timestamp() - early) / span
        for j, slot_index in enumerate(open_slots):
            slot = DK_SLOTS[slot_index]
            if slot in p["eligible"]:
                # Small stable tie breaker favors current assignment in an exact tie.
                cost[i, j] = -SLOT_WEIGHTS[slot] * age + (0.00001 if open_slots[i] != slot_index else 0)
    rows, cols = linear_sum_assignment(cost)
    if any(cost[i, j] >= 1e7 for i, j in zip(rows, cols)):
        raise ValueError("No valid DraftKings slot assignment for selected players")
    chosen = list(lineup)
    for i, j in zip(rows, cols):
        chosen[open_slots[j]] = indices[i]
    if any(DK_SLOTS[k] not in players[x]["eligible"] for k, x in enumerate(chosen)):
        raise ValueError("Late swap rearrangement generated an invalid slot")
    if any(chosen[k] != lineup[k] for k in frozen):
        raise ValueError("Locked roster slot was modified")
    return tuple(chosen)


def parse_dk_entries(raw, players):
    """Parse both DK edit-entries CSVs (with metadata) and simple eight-slot CSVs.

    Refuse unknown or duplicate player IDs rather than guessing a replacement.
    Returns original columns, validated entries and row-specific error messages.
    """
    text = raw.decode("utf-8-sig") if isinstance(raw, bytes) else str(raw).lstrip("\ufeff")
    reader = csv.DictReader(io.StringIO(text))
    headers = list(reader.fieldnames or [])
    if not all(slot in headers for slot in DK_SLOTS):
        raise ValueError("Use a DraftKings NBA Classic Edit Entries CSV with PG/SG/SF/PF/C/G/F/UTIL columns")
    lookup = {str(p["id"]): i for i, p in enumerate(players)}
    entries, errors = [], []
    for rowno, row in enumerate(reader, 2):
        if not any(str(v or "").strip() for v in row.values()):
            continue
        lineup = []
        problem = None
        for slot in DK_SLOTS:
            value = str(row.get(slot) or "").strip()
            m = re.search(r"\((\d+)\)\s*$", value)
            player_id = m.group(1) if m else value
            if player_id not in lookup:
                problem = f"Row {rowno}: unknown or missing {slot} ID {value!r}; use matching-slate DK entries."
                break
            lineup.append(lookup[player_id])
        if problem is None and len(set(lineup)) != 8:
            problem = f"Row {rowno}: duplicate player IDs in lineup."
        if problem is None and any(DK_SLOTS[i] not in players[idx]["eligible"] for i, idx in enumerate(lineup)):
            problem = f"Row {rowno}: player in an ineligible DK roster position."
        if problem is None and sum(players[i]["salary"] for i in lineup) > CAP:
            problem = f"Row {rowno}: lineup salary exceeds $50,000."
        if problem:
            errors.append(problem)
        else:
            entries.append({"row": row.copy(), "lineup": tuple(lineup), "number": rowno})
    if not entries:
        raise ValueError("No valid entries for today's DK player IDs. " + "; ".join(errors[:3]))
    return headers, entries, errors


def gpp_weight(player, mode="Ceiling chase"):
    if mode not in MODES:
        raise ValueError(f"Unknown late-swap GPP strategy {mode}")
    proj = float(player.get("projection", 0))
    p90 = float(player.get("p90", proj * 1.25))
    p99 = float(player.get("p99", proj * 1.55))
    ownership = float(player.get("ownership", 0))
    if mode == "Ceiling chase":
        return 0.28 * proj + 0.44 * p90 + 0.28 * p99 - 0.07 * ownership
    if mode == "Protect lead":
        return 0.80 * proj + 0.20 * p90 - 0.01 * ownership
    return 0.60 * proj + 0.32 * p90 + 0.08 * p99 - 0.04 * ownership


def optimize_late_entry(players, lineup, as_of, *, mode="Ceiling chase",
                        max_team=4, buffer_minutes=2, min_gain=0.4, time_limit=1.0):
    """Rebuild only UNLOCKED slots via exact positional MILP, preserving locked slots.

    If infeasible or improvement is marginal, keep the current selection and
    optimize its unlocked positional arrangement. Locked players are never
    inserted as new candidates, including those ruled OUT after game start.
    """
    import numpy as np
    from scipy.optimize import Bounds, LinearConstraint, milp
    from scipy.sparse import coo_matrix

    lineup = tuple(lineup)
    if len(lineup) != 8 or len(set(lineup)) != 8:
        raise ValueError("Expected eight unique NBA player IDs")
    if any(DK_SLOTS[k] not in players[i]["eligible"] for k, i in enumerate(lineup)):
        raise ValueError("Imported lineup has an ineligible slot assignment")
    if sum(players[i]["salary"] for i in lineup) > CAP:
        raise ValueError("Current entry exceeds salary cap")
    locked = late_swap_slots(lineup, players, as_of, buffer_minutes)
    open_slots = [k for k in range(8) if k not in locked]
    if not open_slots:
        return {"lineup": lineup, "locked": locked, "changes": 0,
                "gain": 0.0, "reason": "All games locked", "flex_gain": 0.0}

    frozen_ids = {lineup[k] for k in locked}
    salary_remaining = CAP - sum(players[lineup[k]]["salary"] for k in locked)
    locked_teams = Counter(players[lineup[k]]["team"] for k in locked)
    cutoff = as_of + timedelta(minutes=float(buffer_minutes))
    eligible = [
        (i, k) for i, p in enumerate(players) for k in open_slots
        if i not in frozen_ids and DK_SLOTS[k] in p["eligible"]
        and p["start"] > cutoff and not p.get("excluded")
        and float(p.get("minutes", 0)) > 0
        and locked_teams[p["team"]] < max_team
    ]
    # A tiny role for retaining current (unlocked) selections avoids churn.
    old_unlocked_ids = {lineup[k] for k in open_slots}
    weights = [gpp_weight(p, mode) for p in players]
    original_weight = sum(weights[lineup[k]] for k in open_slots)
    original_flex = flex_score(lineup, players)
    if not eligible:
        return {"lineup": lineup, "locked": locked, "changes": 0, "gain": 0.0,
                "reason": "No eligible unlocked replacements", "flex_gain": 0.0}

    rows, cols, coefficients, lows, highs = [], [], [], [], []
    def constrain(items, low, high):
        r = len(lows)
        for c, v in items:
            rows.append(r); cols.append(c); coefficients.append(float(v))
        lows.append(float(low)); highs.append(float(high))

    slot_groups = {}
    player_groups = {}
    team_groups = {}
    for col, (i, k) in enumerate(eligible):
        slot_groups.setdefault(k, []).append(col)
        player_groups.setdefault(i, []).append(col)
        team_groups.setdefault(players[i]["team"], []).append(col)
    if any(k not in slot_groups for k in open_slots):
        return {"lineup": lineup, "locked": locked, "changes": 0, "gain": 0.0,
                "reason": "No eligible player for a remaining roster slot", "flex_gain": 0.0}
    for k in open_slots:
        constrain(((col, 1) for col in slot_groups[k]), 1, 1)
    for cols_for_player in player_groups.values():
        constrain(((col, 1) for col in cols_for_player), 0, 1)
    constrain(((col, players[i]["salary"]) for col, (i, k) in enumerate(eligible)),
              0, salary_remaining)
    for team, members in team_groups.items():
        constrain(((col, 1) for col in members), 0, max_team - locked_teams[team])

    early = min(p["start"].timestamp() for p in players)
    late = max(p["start"].timestamp() for p in players)
    span = max(1.0, late - early)
    cost = []
    for i, k in eligible:
        time_rank = (players[i]["start"].timestamp() - early) / span
        flex_bonus = 0.08 * SLOT_WEIGHTS[DK_SLOTS[k]] * time_rank
        retain_bonus = 0.15 if i in old_unlocked_ids else 0
        cost.append(-(weights[i] + flex_bonus + retain_bonus))
    matrix = coo_matrix((coefficients, (rows, cols)),
                        shape=(len(lows), len(eligible))).tocsr()
    solution = milp(np.array(cost), integrality=np.ones(len(eligible)),
                    bounds=Bounds(0, 1),
                    constraints=LinearConstraint(matrix, lows, highs),
                    options={"time_limit": float(time_limit), "mip_rel_gap": 0.02})
    if solution.x is None:
        return {"lineup": lineup, "locked": locked, "changes": 0, "gain": 0.0,
                "reason": "No legal improvement with locked players and remaining salary", "flex_gain": 0.0}

    result = list(lineup)
    for selected, (i, k) in zip(solution.x, eligible):
        if selected > 0.5:
            result[k] = i
    if len(set(result)) != 8 or any(DK_SLOTS[k] not in players[i]["eligible"]
                                    for k, i in enumerate(result)):
        raise ValueError("Optimizer produced invalid slot assignment")
    if any(result[k] != lineup[k] for k in locked):
        raise ValueError("Optimizer attempted to alter a locked slot")
    if sum(players[i]["salary"] for i in result) > CAP:
        raise ValueError("Optimizer exceeded DraftKings salary cap")
    if max(Counter(players[i]["team"] for i in result).values()) > max_team:
        raise ValueError("Optimizer exceeded maximum per-team exposure")

    result = reorder_for_late_swap(result, players, locked)
    selected_weight = sum(weights[result[k]] for k in open_slots)
    gain = selected_weight - original_weight
    if gain < min_gain:
        # Still reorganize same remaining players so late-game flexibility
        # increases if valid. Do not impose a meaningless player swap.
        result = reorder_for_late_swap(lineup, players, locked)
        gain = 0.0
    changed = sum(result[k] != lineup[k] for k in range(8))
    return {"lineup": tuple(result), "locked": locked, "changes": changed,
            "gain": round(gain, 2), "flex_gain": round(flex_score(result, players) - original_flex, 2),
            "reason": "Optimized" if changed else "Already optimized"}


def export_dk_swaps(headers, entries, swaps, players, *, changed_only=True):
    """Retain metadata, entry IDs, original CSV columns, and locked slot values."""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=headers, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    count = 0
    for entry, swap in zip(entries, swaps):
        if changed_only and not swap["changes"]:
            continue
        row = dict(entry["row"])
        for k, slot in enumerate(DK_SLOTS):
            i = swap["lineup"][k]
            if k not in swap["locked"]:
                row[slot] = f'{players[i]["name"]} ({players[i]["id"]})'
            # Frozen slots retain their original cell representation verbatim.
        writer.writerow(row)
        count += 1
    return output.getvalue(), count
