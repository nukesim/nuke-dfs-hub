from __future__ import annotations

from pathlib import Path
import pandas as pd

DATA_PATH = Path("data/nfl_availability_current.csv")

RED_STATUSES = {"out", "ir", "injured reserve", "pup", "nfi", "suspended", "inactive", "declared inactive"}
YELLOW_STATUSES = {"questionable", "doubtful", "limited", "did not practice", "dnp"}


def _norm(x):
    return " ".join(str(x or "").lower().replace(".", "").replace("'", "").replace("-", " ").split())


def load_availability():
    if not DATA_PATH.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(DATA_PATH)
    except Exception:
        return pd.DataFrame()


def availability_status(players, feed=None):
    """Join the latest injury feed to a prepared NUKE slate.

    Returns (annotated_players, summary). Red statuses are NOT removed here;
    the caller decides whether to auto-exclude them from its pool state.
    """
    out = players.copy()
    out["Availability"] = "Available"
    out["Availability Detail"] = ""
    out["Auto Exclude"] = False
    out["Availability Updated"] = ""
    if feed is None:
        feed = load_availability()
    if feed is None or feed.empty:
        return out, {"loaded": False, "red": 0, "yellow": 0, "qb_warnings": [], "updated": ""}

    f = feed.copy()
    for c in ["name", "team", "status", "practice", "comment", "updated"]:
        if c not in f.columns:
            f[c] = ""
    f["_name"] = f["name"].map(_norm)
    f["_team"] = f["team"].astype(str).str.upper().str.strip()
    lookup = {}
    for _, r in f.iterrows():
        lookup[(r["_name"], r["_team"])] = r
        lookup.setdefault((r["_name"], ""), r)

    red = yellow = 0
    qb_warnings = []
    latest = ""
    for idx, p in out.iterrows():
        key = (_norm(p.get("Name", "")), str(p.get("Team", "")).upper().strip())
        r = lookup.get(key) or lookup.get((key[0], ""))
        if r is None:
            continue
        status = str(r.get("status", "") or "").strip()
        practice = str(r.get("practice", "") or "").strip()
        comment = str(r.get("comment", "") or "").strip()
        updated = str(r.get("updated", "") or "").strip()
        blob = f"{status} {practice}".lower()
        is_red = any(s in blob for s in RED_STATUSES)
        is_yellow = (not is_red) and any(s in blob for s in YELLOW_STATUSES)
        if is_red:
            label = "OUT / INACTIVE"
            red += 1
        elif is_yellow:
            label = status or practice or "Questionable"
            yellow += 1
        else:
            label = status or "Available"
        out.at[idx, "Availability"] = label
        out.at[idx, "Availability Detail"] = comment or practice
        out.at[idx, "Auto Exclude"] = bool(is_red)
        out.at[idx, "Availability Updated"] = updated
        if updated and updated > latest:
            latest = updated
        if str(p.get("Position", "")).upper() == "QB" and (is_red or is_yellow) and str(p.get("auto_role", "")).upper() == "QB1":
            qb_warnings.append(f"{p.get('Team','')} — {p.get('Name','')} ({label})")

    return out, {"loaded": True, "red": red, "yellow": yellow, "qb_warnings": qb_warnings, "updated": latest}
