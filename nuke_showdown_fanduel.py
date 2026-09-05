import csv
import io

import pandas as pd

FANDUEL_SHOWDOWN_SALARY_CAP = 60000

REQUIRED_COLUMNS = {
    "Id", "Position", "Nickname", "FPPG", "Salary", "MVP 1.5x Salary",
    "Game", "Team", "Opponent", "Roster Position",
}


def parse_fanduel_showdown_csv(source):
    if isinstance(source, pd.DataFrame):
        raw = source.copy()
    else:
        raw = pd.read_csv(source)

    missing = sorted(REQUIRED_COLUMNS - set(raw.columns))
    if missing:
        raise ValueError("Missing FanDuel Showdown columns: " + ", ".join(missing))

    games = raw["Game"].dropna().astype(str).unique().tolist()
    if len(games) != 1:
        raise ValueError("FanDuel Showdown requires a single-game player list.")

    rows = []
    for _, r in raw.iterrows():
        name = str(r.get("Nickname", "") or "").strip()
        team = str(r.get("Team", "") or "").strip()
        pos = str(r.get("Position", "") or "").strip().upper()
        if not name or not team:
            continue
        status = str(r.get("Injury Indicator", "") or "").strip().upper()
        pid = str(r.get("Id", "") or "").strip()
        salary = int(float(r.get("Salary", 0) or 0))
        mvp_salary = int(float(r.get("MVP 1.5x Salary", 0) or 0))
        fppg = float(r.get("FPPG", 0) or 0) if pd.notna(r.get("FPPG", None)) else 0.0
        rows.append({
            "Player Key": f"{team}|{name}",
            "Name": name,
            "Team": team,
            "Pos": "DST" if pos == "D" else pos,
            "FLEX Salary": salary,
            "CPT Salary": mvp_salary,
            "FLEX ID": pid,
            "CPT ID": pid,
            "Status": status,
            "Avg FPPG": fppg,
            "Game Info": games[0],
        })

    players = pd.DataFrame(rows)
    if players.empty:
        raise ValueError("No FanDuel Showdown players were found in this file.")
    players["Auto Include"] = ~players["Status"].isin({"OUT", "IR", "O"})
    players = players.sort_values(["FLEX Salary", "Team", "Name"], ascending=[False, True, True]).reset_index(drop=True)

    teams = players["Team"].dropna().astype(str).unique().tolist()
    if len(teams) != 2:
        raise ValueError(f"Expected exactly two teams in a FanDuel Showdown slate; found {len(teams)}.")

    return players, {"game_info": games[0], "teams": teams, "player_count": int(len(players))}


def export_fanduel_lineup_only_csv(saved, players_by_key):
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(["MVP - 1.5X Points", "AnyFLEX", "AnyFLEX", "AnyFLEX", "AnyFLEX", "AnyFLEX"])
    for rec in saved:
        cpt = players_by_key[rec["captain_key"]]
        flex = [players_by_key[k] for k in rec["flex_keys"]]
        writer.writerow([
            str(cpt["CPT ID"]),
            str(flex[0]["FLEX ID"]), str(flex[1]["FLEX ID"]), str(flex[2]["FLEX ID"]),
            str(flex[3]["FLEX ID"]), str(flex[4]["FLEX ID"]),
        ])
    return output.getvalue().encode("utf-8-sig")
