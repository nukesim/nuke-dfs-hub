import csv
import io
import re
import pandas as pd

FD_ROSTER_ORDER = ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "D"]
ANALYSIS_ROSTER_HEADERS = ["QB", "RB1", "RB2", "WR1", "WR2", "WR3", "TE", "FLEX", "D"]


def _player_id(row):
    pid = str(row.get("ID", "")).strip()
    if pid and pid.lower() not in {"nan", "none"}:
        return pid
    return str(row.get("Name", "")).strip()


def _player_ref(row):
    name = str(row.get("Name", "")).strip()
    pid = str(row.get("ID", "")).strip()
    return f"{name} ({pid})" if pid and pid.lower() not in {"nan", "none"} else name


def lineup_to_fd_slots(players, indices, ids_only=False):
    roster = players.iloc[list(indices)].copy()
    if len(roster) != 9:
        raise ValueError("FanDuel NFL Classic lineups must contain 9 players")
    groups = {p: roster[roster["Position"].eq(p)].copy().sort_values(["Salary", "Name"], ascending=[False, True]) for p in ["QB", "RB", "WR", "TE", "DST"]}
    if len(groups["QB"]) != 1 or len(groups["DST"]) != 1:
        raise ValueError("Lineup must contain exactly one QB and one D/ST")
    if len(groups["RB"]) < 2 or len(groups["WR"]) < 3 or len(groups["TE"]) < 1:
        raise ValueError("Lineup does not satisfy FanDuel NFL Classic position minimums")
    flex_row = None
    if len(groups["RB"]) > 2:
        flex_row = groups["RB"].iloc[-1]; groups["RB"] = groups["RB"].iloc[:-1]
    elif len(groups["WR"]) > 3:
        flex_row = groups["WR"].iloc[-1]; groups["WR"] = groups["WR"].iloc[:-1]
    elif len(groups["TE"]) > 1:
        flex_row = groups["TE"].iloc[-1]; groups["TE"] = groups["TE"].iloc[:-1]
    if flex_row is None:
        raise ValueError("Could not identify FLEX player")
    ref = _player_id if ids_only else _player_ref
    return [
        ref(groups["QB"].iloc[0]),
        ref(groups["RB"].iloc[0]), ref(groups["RB"].iloc[1]),
        ref(groups["WR"].iloc[0]), ref(groups["WR"].iloc[1]), ref(groups["WR"].iloc[2]),
        ref(groups["TE"].iloc[0]), ref(flex_row), ref(groups["DST"].iloc[0]),
    ]


def lineup_flex_position(players, indices):
    counts = players.iloc[list(indices)]["Position"].value_counts().to_dict()
    if counts.get("RB", 0) > 2: return "RB"
    if counts.get("WR", 0) > 3: return "WR"
    if counts.get("TE", 0) > 1: return "TE"
    return "UNKNOWN"


def add_fd_roster_columns(players, results):
    if results is None or results.empty:
        return pd.DataFrame()
    out = results.copy().reset_index(drop=True)
    slots = pd.DataFrame([lineup_to_fd_slots(players, lu) for lu in out["_indices"]], columns=ANALYSIS_ROSTER_HEADERS)
    slots["FLEX Pos"] = [lineup_flex_position(players, lu) for lu in out["_indices"]]
    remainder = out.drop(columns=["QB", "RB", "WR", "TE", "DST", "D", "FLEX Pos"], errors="ignore")
    return pd.concat([slots, remainder], axis=1)


def build_fd_lineup_only_csv(players, results, limit=None):
    """Create a simple FanDuel lineup CSV using FanDuel player IDs.

    For safest contest entry editing, users can also upload FanDuel's downloaded
    entry template and use fill_fd_entries_csv, which preserves every original
    contest/entry column and only fills the roster slots.
    """
    if results is None or results.empty:
        return b""
    x = results.head(int(limit)) if limit else results
    buf = io.StringIO(newline="")
    writer = csv.writer(buf)
    writer.writerow(FD_ROSTER_ORDER)
    for indices in x["_indices"]:
        writer.writerow(lineup_to_fd_slots(players, indices, ids_only=True))
    return buf.getvalue().encode("utf-8-sig")


def _base_slot(header):
    h = re.sub(r"\.\d+$", "", str(header).strip().upper())
    if h in {"D", "DEF", "DST", "D/ST"}:
        return "D"
    return h if h in {"QB", "RB", "WR", "TE", "FLEX"} else None


def fill_fd_entries_csv(upload_bytes, players, results, limit=None):
    if results is None or results.empty:
        raise ValueError("No simulated lineups are available")
    if not upload_bytes:
        raise ValueError("FanDuel entries CSV is empty")
    text = upload_bytes.decode("utf-8-sig", errors="replace")
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        raise ValueError("FanDuel entries CSV has no rows")
    header = rows[0]
    slot_cols = [(i, _base_slot(h)) for i, h in enumerate(header) if _base_slot(h)]
    if [s for _, s in slot_cols] != FD_ROSTER_ORDER:
        raise ValueError("Could not find FanDuel NFL roster columns in order: " + ", ".join(FD_ROSTER_ORDER))
    data_rows = rows[1:]
    usable_rows = [i for i, row in enumerate(data_rows) if any(str(v).strip() for v in row)]
    if not usable_rows:
        raise ValueError("FanDuel entries CSV contains no entry rows")
    count = min(len(usable_rows), len(results))
    if limit:
        count = min(count, int(limit))
    for j in range(count):
        row_i = usable_rows[j]
        row = data_rows[row_i]
        if len(row) < len(header):
            row.extend([""] * (len(header) - len(row)))
        values = lineup_to_fd_slots(players, results.iloc[j]["_indices"], ids_only=True)
        for (col_i, _), value in zip(slot_cols, values):
            row[col_i] = value
    out = io.StringIO(newline="")
    writer = csv.writer(out)
    writer.writerow(header)
    writer.writerows(data_rows)
    return out.getvalue().encode("utf-8-sig"), {
        "entries_in_file": len(usable_rows),
        "lineups_available": len(results),
        "entries_filled": count,
    }
