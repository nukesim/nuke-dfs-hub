"""Filterable, sortable NBA Player Lab grid — pure functions for Streamlit + tests."""

from __future__ import annotations

POSITION_ORDER = ("PG", "SG", "SF", "PF", "C")
GRID_COLUMNS = (
    "Player", "Pos", "Team", "Salary", "Proj", "Min", "FPPM", "Own %",
    "P90", "P99", "Value", "20+ %", "6x %",
    "Status", "Starter", "Pool", "Source",
)
SORT_OPTIONS = {
    "Projected points": "Proj",
    "Projected minutes": "Min",
    "DK fantasy points per minute": "FPPM",
    "Ownership": "Own %",
    "P90 ceiling": "P90",
    "P99 ceiling": "P99",
    "Salary": "Salary",
    "Value per $1K": "Value",
    "20+ point hit rate": "20+ %",
    "6x salary hit rate": "6x %",
}


def player_lab_rows(
    players, *,
    position="ALL",
    team="ALL",
    pool="Eligible",
    search="",
    salary_range=None,
    minimum_minutes=0.0,
    sort_by="Projected points",
):
    """Return a grid without changing the model or the upstream player pool.

    Position filters use DraftKings CORE eligibility, not the flexible G/F/UTIL
    roster slots. Players eligible at two positions appear in both filters.
    """
    if position not in ("ALL", *POSITION_ORDER):
        raise ValueError("Unknown NBA position filter")
    if pool not in ("Eligible", "All players", "Injury watch", "Starting fives"):
        raise ValueError("Unknown NBA pool filter")
    if sort_by not in SORT_OPTIONS:
        raise ValueError("Unknown NBA sort option")
    if salary_range is None:
        salary_range = (0, float("inf"))
    minimum_salary, maximum_salary = salary_range
    term = search.strip().casefold()

    rows = []
    for p in players:
        eligible = tuple(pos for pos in POSITION_ORDER if pos in p.get("eligible", ()))
        if position != "ALL" and position not in eligible:
            continue
        if team != "ALL" and p.get("team") != team:
            continue
        if term and term not in str(p.get("name", "")).casefold():
            continue

        salary = int(p.get("salary", 0))
        minutes = float(p.get("minutes", 0))
        excluded = bool(p.get("excluded", False))
        status = str(p.get("status", "ACTIVE")).upper()
        starter = str(p.get("starter", "UNKNOWN")).upper()
        if not minimum_salary <= salary <= maximum_salary or minutes < minimum_minutes:
            continue
        if pool == "Eligible" and (excluded or minutes <= 0):
            continue
        if pool == "Injury watch" and status == "ACTIVE":
            continue
        if pool == "Starting fives" and starter not in {"EXPECTED", "CONFIRMED"}:
            continue

        rows.append({
            "Player": str(p.get("name", "")),
            "Pos": "/".join(eligible) if eligible else "—",
            "Team": str(p.get("team", "")),
            "Salary": salary,
            "Proj": round(float(p.get("projection", 0)), 1),
            "Min": round(minutes, 1),
            "FPPM": round(float(p.get("fppm_base", 0)), 2),
            "Own %": round(float(p.get("ownership", 0)), 1),
            "P90": round(float(p.get("p90", 0)), 1),
            "P99": round(float(p.get("p99", 0)), 1),
            "Value": round(float(p.get("value", 0)), 2),
            "20+ %": round(float(p.get("hit_20", 0)), 1),
            "6x %": round(float(p.get("hit_6x", 0)), 1),
            "Status": "—" if status == "ACTIVE" else status,
            "Starter": starter if starter in {"EXPECTED", "CONFIRMED"} else "—",
            "Pool": "EXCLUDED" if excluded else "IN",
            "Source": str(p.get("source", "DK fallback")),
        })

    sort_column = SORT_OPTIONS[sort_by]
    rows.sort(key=lambda row: (-row[sort_column], row["Player"].casefold()))
    return rows
