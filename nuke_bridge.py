import re
import numpy as np
import pandas as pd

from dk_export import lineup_to_dk_slots

HUB_SLOT_NAMES = ["QB", "RB1", "RB2", "WR1", "WR2", "WR3", "TE", "FLEX", "DST"]


def extract_dk_id(value):
    """Return the DraftKings player id from either `Name (123)` or a raw id."""
    if value is None:
        return ""
    s = str(value).strip()
    m = re.search(r"\((\d+)\)\s*$", s)
    if m:
        return m.group(1)
    if re.fullmatch(r"\d+(?:\.0)?", s):
        return s.replace(".0", "")
    return ""


def sync_hub_pool_to_sim(players, pool_state, hub_pool_ids=None, role_adjustments=None):
    """Apply the committed Hub pool and Hub role-adjustment percentages to SIM state.

    Existing SIM role overrides are preserved. A Hub role adjustment maps to the SIM's
    bounded usage multiplier (e.g. +20% -> 1.20) so the same user take carries across pages.
    If the Hub pool is empty/uncommitted, all players remain included.
    """
    state = dict(pool_state or {})
    include_ids = {extract_dk_id(v) for v in (hub_pool_ids or [])}
    include_ids.discard("")
    adj_by_id = {}
    for ref, raw in (role_adjustments or {}).items():
        pid = extract_dk_id(ref)
        if not pid:
            continue
        try:
            adj_by_id[pid] = float(raw)
        except Exception:
            continue

    for _, row in players.iterrows():
        raw_id = str(row.ID).strip().replace(".0", "")
        key = raw_id if raw_id else f"{row.Name}|{row.Team}|{row.Position}|{int(row.Salary)}"
        old = state.get(key, {"include": True, "role": "AUTO", "usage": 1.0})
        include = raw_id in include_ids if include_ids else True
        usage = float(old.get("usage", 1.0))
        if raw_id in adj_by_id:
            usage = float(np.clip(1.0 + adj_by_id[raw_id] / 100.0, 0.25, 2.25))
        state[key] = {
            "include": bool(include),
            "role": str(old.get("role", "AUTO")),
            "usage": usage,
        }
    return state


def portfolio_to_hub_rows(players, portfolio):
    """Convert a SIM portfolio into portable Hub lineup dictionaries."""
    if players is None or portfolio is None or portfolio.empty or "_indices" not in portfolio.columns:
        return []
    rows = []
    for _, r in portfolio.iterrows():
        slots = lineup_to_dk_slots(players, r["_indices"])
        item = dict(zip(HUB_SLOT_NAMES, slots))
        for col in ["Portfolio Slot", "Portfolio Reason", "Portfolio Scenario", "Strongest Path", "Sim ROI %", "1st %", "Top 0.1%", "Top 1%", "NUKE Score", "Ceiling 95", "Salary"]:
            if col in portfolio.columns:
                val = r.get(col)
                if pd.isna(val):
                    val = None
                elif isinstance(val, np.generic):
                    val = val.item()
                item[f"__{col}"] = val
        rows.append(item)
    return rows


def portable_to_hub_lineup(row):
    if not isinstance(row, dict):
        return None
    lu = {slot: row.get(slot) for slot in HUB_SLOT_NAMES}
    return lu if all(lu.values()) else None
