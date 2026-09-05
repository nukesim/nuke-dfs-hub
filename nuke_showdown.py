import io
from collections import Counter

import pandas as pd

SHOWDOWN_SALARY_CAP = 50000
SHOWDOWN_ROSTER_SIZE = 6
SHOWDOWN_FLEX_SLOTS = 5

REQUIRED_COLUMNS = {
    "Position",
    "Name",
    "ID",
    "Roster Position",
    "Salary",
    "Game Info",
    "TeamAbbrev",
}


def parse_showdown_salary_csv(source):
    """Parse a DraftKings NFL Showdown salary CSV into one row per real player."""
    if isinstance(source, pd.DataFrame):
        raw = source.copy()
    else:
        raw = pd.read_csv(source)

    missing = sorted(REQUIRED_COLUMNS - set(raw.columns))
    if missing:
        raise ValueError("Missing DraftKings Showdown columns: " + ", ".join(missing))

    raw = raw.copy()
    raw["Roster Position"] = raw["Roster Position"].astype(str).str.upper().str.strip()
    positions = set(raw["Roster Position"].dropna().unique())
    if not {"CPT", "FLEX"}.issubset(positions):
        raise ValueError("This does not look like a DraftKings Showdown salary CSV. CPT and FLEX rows are required.")

    game_values = raw["Game Info"].dropna().astype(str).unique().tolist()
    if len(game_values) != 1:
        raise ValueError("Showdown requires a single-game DraftKings salary file.")

    rows = []
    group_cols = ["Name", "TeamAbbrev", "Position"]
    for (name, team, pos), grp in raw.groupby(group_cols, sort=False, dropna=False):
        flex = grp[grp["Roster Position"].eq("FLEX")]
        cpt = grp[grp["Roster Position"].eq("CPT")]
        if flex.empty or cpt.empty:
            continue
        fr = flex.iloc[0]
        cr = cpt.iloc[0]
        status = ""
        if "Status" in grp.columns:
            vals = [str(x).strip().upper() for x in grp["Status"].dropna().tolist() if str(x).strip()]
            status = vals[0] if vals else ""
        rows.append(
            {
                "Player Key": f"{team}|{name}",
                "Name": str(name),
                "Team": str(team),
                "Pos": str(pos),
                "FLEX Salary": int(fr["Salary"]),
                "CPT Salary": int(cr["Salary"]),
                "FLEX ID": str(fr["ID"]),
                "CPT ID": str(cr["ID"]),
                "Status": status,
                "Avg FPPG": float(fr.get("AvgPointsPerGame", 0) or 0),
                "Game Info": str(fr["Game Info"]),
            }
        )

    players = pd.DataFrame(rows)
    if players.empty:
        raise ValueError("No paired CPT/FLEX players were found in this Showdown file.")

    players["Auto Include"] = ~players["Status"].isin({"OUT", "IR", "O"})
    players = players.sort_values(["FLEX Salary", "Team", "Name"], ascending=[False, True, True]).reset_index(drop=True)

    teams = players["Team"].dropna().astype(str).unique().tolist()
    if len(teams) != 2:
        raise ValueError(f"Expected exactly two teams in a Showdown slate; found {len(teams)}.")

    meta = {
        "game_info": game_values[0],
        "teams": teams,
        "player_count": int(len(players)),
    }
    return players, meta


def lineup_salary(players_by_key, captain_key, flex_keys):
    if not captain_key:
        return 0
    salary = int(players_by_key[captain_key]["CPT Salary"])
    for key in flex_keys:
        if key:
            salary += int(players_by_key[key]["FLEX Salary"])
    return salary


def validate_lineup(players_by_key, captain_key, flex_keys):
    selected = [captain_key] + list(flex_keys)
    if any(not x for x in selected):
        return False, "Fill all 6 roster spots."
    if len(selected) != SHOWDOWN_ROSTER_SIZE:
        return False, "A Showdown lineup must contain 1 CPT and 5 FLEX players."
    if len(set(selected)) != SHOWDOWN_ROSTER_SIZE:
        return False, "A player can only appear once in a Showdown lineup."
    if any(k not in players_by_key for k in selected):
        return False, "One or more selected players are no longer in the active pool."
    salary = lineup_salary(players_by_key, captain_key, flex_keys)
    if salary > SHOWDOWN_SALARY_CAP:
        return False, f"Salary is ${salary:,}; DraftKings Showdown cap is ${SHOWDOWN_SALARY_CAP:,}."
    teams = {players_by_key[k]["Team"] for k in selected}
    if len(teams) < 2:
        return False, "Roster at least one player from each team."
    return True, "Legal DraftKings Showdown lineup."


def lineup_record(players_by_key, captain_key, flex_keys):
    selected = [captain_key] + list(flex_keys)
    salary = lineup_salary(players_by_key, captain_key, flex_keys)
    teams = [players_by_key[k]["Team"] for k in selected]
    counts = Counter(teams)
    split = "-".join(str(x) for x in sorted(counts.values(), reverse=True))
    return {
        "captain_key": captain_key,
        "flex_keys": list(flex_keys),
        "salary": salary,
        "team_split": split,
    }


def lineup_identity(record):
    return (record["captain_key"], tuple(sorted(record["flex_keys"])))


def saved_lineups_table(saved, players_by_key):
    rows = []
    for i, rec in enumerate(saved, 1):
        cpt = players_by_key.get(rec["captain_key"], {})
        flex = [players_by_key.get(k, {}) for k in rec["flex_keys"]]
        rows.append(
            {
                "#": i,
                "CPT": cpt.get("Name", rec["captain_key"]),
                "FLEX": " · ".join(x.get("Name", "?") for x in flex),
                "Salary": int(rec.get("salary", 0)),
                "Split": rec.get("team_split", ""),
            }
        )
    return pd.DataFrame(rows)


def exposure_tables(saved, players_by_key):
    if not saved:
        return pd.DataFrame(), pd.DataFrame()
    n = len(saved)
    player_counts = Counter()
    captain_counts = Counter()
    for rec in saved:
        captain_counts[rec["captain_key"]] += 1
        player_counts[rec["captain_key"]] += 1
        player_counts.update(rec["flex_keys"])

    def rows_from(counter):
        rows = []
        for key, count in counter.most_common():
            p = players_by_key.get(key, {})
            rows.append(
                {
                    "Player": p.get("Name", key),
                    "Team": p.get("Team", ""),
                    "Pos": p.get("Pos", ""),
                    "Lineups": int(count),
                    "Exposure %": round(100.0 * count / n, 1),
                }
            )
        return pd.DataFrame(rows)

    return rows_from(player_counts), rows_from(captain_counts)


def _dk_ref(player, slot):
    pid = str(player[f"{slot} ID"])
    return f"{player['Name']} ({pid})"


def export_lineup_only_csv(saved, players_by_key):
    rows = []
    for rec in saved:
        cpt = players_by_key[rec["captain_key"]]
        flex = [players_by_key[k] for k in rec["flex_keys"]]
        rows.append(
            {
                "CPT": _dk_ref(cpt, "CPT"),
                "FLEX": _dk_ref(flex[0], "FLEX"),
                "FLEX.1": _dk_ref(flex[1], "FLEX"),
                "FLEX.2": _dk_ref(flex[2], "FLEX"),
                "FLEX.3": _dk_ref(flex[3], "FLEX"),
                "FLEX.4": _dk_ref(flex[4], "FLEX"),
            }
        )
    out = pd.DataFrame(rows, columns=["CPT", "FLEX", "FLEX.1", "FLEX.2", "FLEX.3", "FLEX.4"])
    return out.to_csv(index=False).encode("utf-8-sig")
