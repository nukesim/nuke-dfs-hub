import csv
import io
import re
import pandas as pd

ROSTER_ORDER = ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DST"]
ANALYSIS_ROSTER_HEADERS = ["QB", "RB1", "RB2", "WR1", "WR2", "WR3", "TE", "FLEX", "DST"]


def _player_ref(row):
    name = str(row.get("Name", "")).strip()
    pid = str(row.get("ID", "")).strip()
    if pid and pid.lower() not in {"nan", "none"}:
        return f"{name} ({pid})"
    return name


def lineup_to_dk_slots(players, indices):
    roster = players.iloc[list(indices)].copy()
    if len(roster) != 9:
        raise ValueError("DraftKings classic NFL lineups must contain 9 players")
    groups = {}
    for pos in ["QB", "RB", "WR", "TE", "DST"]:
        groups[pos] = roster[roster["Position"].eq(pos)].copy().sort_values(["Salary", "Name"], ascending=[False, True])
    if len(groups["QB"]) != 1 or len(groups["DST"]) != 1:
        raise ValueError("Lineup must contain exactly one QB and one DST")
    if len(groups["RB"]) < 2 or len(groups["WR"]) < 3 or len(groups["TE"]) < 1:
        raise ValueError("Lineup does not satisfy DraftKings NFL position minimums")
    flex_row = None
    if len(groups["RB"]) > 2:
        flex_row = groups["RB"].iloc[-1]; groups["RB"] = groups["RB"].iloc[:-1]
    elif len(groups["WR"]) > 3:
        flex_row = groups["WR"].iloc[-1]; groups["WR"] = groups["WR"].iloc[:-1]
    elif len(groups["TE"]) > 1:
        flex_row = groups["TE"].iloc[-1]; groups["TE"] = groups["TE"].iloc[:-1]
    if flex_row is None:
        raise ValueError("Could not identify FLEX player")
    refs = {
        "QB": [_player_ref(r) for _, r in groups["QB"].iterrows()],
        "RB": [_player_ref(r) for _, r in groups["RB"].iterrows()],
        "WR": [_player_ref(r) for _, r in groups["WR"].iterrows()],
        "TE": [_player_ref(r) for _, r in groups["TE"].iterrows()],
        "DST": [_player_ref(r) for _, r in groups["DST"].iterrows()],
        "FLEX": [_player_ref(flex_row)],
    }
    return [refs["QB"][0], refs["RB"][0], refs["RB"][1], refs["WR"][0], refs["WR"][1], refs["WR"][2], refs["TE"][0], refs["FLEX"][0], refs["DST"][0]]


def lineup_flex_position(players, indices):
    roster = players.iloc[list(indices)]
    counts = roster["Position"].value_counts().to_dict()
    if counts.get("RB", 0) > 2: return "RB"
    if counts.get("WR", 0) > 3: return "WR"
    if counts.get("TE", 0) > 1: return "TE"
    return "UNKNOWN"


def add_dk_roster_columns(players, results, include_ids=True):
    """Return analysis results with copy/paste-ready DK roster slots on the far left."""
    if results is None or results.empty:
        return pd.DataFrame()
    out = results.copy().reset_index(drop=True)
    slot_rows = [lineup_to_dk_slots(players, lu) for lu in out["_indices"]]
    slots = pd.DataFrame(slot_rows, columns=ANALYSIS_ROSTER_HEADERS)
    slots.insert(len(slots.columns), "FLEX Pos", [lineup_flex_position(players, lu) for lu in out["_indices"]])
    return pd.concat([slots, out.drop(columns=["QB", "RB", "WR", "TE", "DST"], errors="ignore")], axis=1)


def build_lineup_only_csv(players, results, limit=None):
    if results is None or results.empty: return b""
    x = results.head(int(limit)) if limit else results
    buf = io.StringIO(newline=""); writer = csv.writer(buf); writer.writerow(ROSTER_ORDER)
    for indices in x["_indices"]: writer.writerow(lineup_to_dk_slots(players, indices))
    return buf.getvalue().encode("utf-8-sig")


def _base_slot(header):
    h = str(header).strip().upper(); h = re.sub(r"\.\d+$", "", h)
    return h if h in {"QB", "RB", "WR", "TE", "FLEX", "DST"} else None


def fill_entries_csv(upload_bytes, players, results, limit=None):
    if results is None or results.empty: raise ValueError("No simulated lineups are available")
    if not upload_bytes: raise ValueError("Entries CSV is empty")
    text = upload_bytes.decode("utf-8-sig", errors="replace"); rows = list(csv.reader(io.StringIO(text)))
    if not rows: raise ValueError("Entries CSV has no rows")
    header = rows[0]; slot_cols = []
    for i, h in enumerate(header):
        slot = _base_slot(h)
        if slot: slot_cols.append((i, slot))
    if [slot for _, slot in slot_cols] != ROSTER_ORDER:
        raise ValueError("Could not find DraftKings NFL roster columns in order: " + ", ".join(ROSTER_ORDER))
    data_rows = rows[1:]; usable_rows = [i for i, row in enumerate(data_rows) if any(str(v).strip() for v in row)]
    if not usable_rows: raise ValueError("Entries CSV contains no entry rows")
    count = min(len(usable_rows), len(results)); count = min(count, int(limit)) if limit else count
    if count <= 0: raise ValueError("No entries can be filled")
    for j in range(count):
        row_i = usable_rows[j]; row = data_rows[row_i]
        if len(row) < len(header): row.extend([""] * (len(header) - len(row)))
        roster_values = lineup_to_dk_slots(players, results.iloc[j]["_indices"])
        for (col_i, _), value in zip(slot_cols, roster_values): row[col_i] = value
    out = io.StringIO(newline=""); writer = csv.writer(out); writer.writerow(header); writer.writerows(data_rows)
    return out.getvalue().encode("utf-8-sig"), {"entries_in_file": len(usable_rows), "lineups_available": len(results), "entries_filled": count}
