import pandas as pd

from dk_export import build_lineup_only_csv, fill_entries_csv, lineup_to_dk_slots, add_dk_roster_columns


def _players():
    rows = [
        {"Name":"QB One","ID":"1","Position":"QB","Salary":6500},
        {"Name":"RB One","ID":"2","Position":"RB","Salary":8000},
        {"Name":"RB Two","ID":"3","Position":"RB","Salary":7200},
        {"Name":"RB Flex","ID":"4","Position":"RB","Salary":6100},
        {"Name":"WR One","ID":"5","Position":"WR","Salary":7600},
        {"Name":"WR Two","ID":"6","Position":"WR","Salary":6400},
        {"Name":"WR Three","ID":"7","Position":"WR","Salary":5200},
        {"Name":"TE One","ID":"8","Position":"TE","Salary":4800},
        {"Name":"DST One","ID":"9","Position":"DST","Salary":3000},
    ]
    return pd.DataFrame(rows)


def _results():
    return pd.DataFrame({
        "_indices": [list(range(9))],
        "QB": ["QB One"], "RB": ["RB One / RB Two / RB Flex"],
        "WR": ["WR One / WR Two / WR Three"], "TE": ["TE One"], "DST": ["DST One"],
        "FLEX Pos": ["RB"], "Contest Rank": [1], "Sim ROI %": [12.3],
    })


def test_lineup_to_dk_slots_and_entries_fill():
    players = _players(); results = _results()
    slots = lineup_to_dk_slots(players, results.iloc[0]["_indices"])
    assert len(slots) == 9
    assert slots[0] == "QB One (1)"
    assert slots[7] == "RB Flex (4)"
    assert slots[8] == "DST One (9)"

    lineup_csv = build_lineup_only_csv(players, results)
    text = lineup_csv.decode("utf-8-sig")
    assert text.splitlines()[0] == "QB,RB,RB,WR,WR,WR,TE,FLEX,DST"

    entries = (
        "Entry ID,Contest Name,Contest ID,Entry Fee,QB,RB,RB,WR,WR,WR,TE,FLEX,DST\n"
        "123,Test Contest,999,$5,,,,,,,,,\n"
    ).encode()
    filled, info = fill_entries_csv(entries, players, results)
    out = filled.decode("utf-8-sig")
    assert "QB One (1)" in out
    assert "RB Flex (4)" in out
    assert info["entries_filled"] == 1


def test_analysis_export_has_unique_columns_and_dk_slots_left():
    analysis = add_dk_roster_columns(_players(), _results())
    assert not analysis.columns.duplicated().any()
    assert list(analysis.columns[:10]) == ["QB","RB1","RB2","WR1","WR2","WR3","TE","FLEX","DST","FLEX Pos"]
    assert analysis.loc[0, "FLEX Pos"] == "RB"
    assert analysis.loc[0, "QB"] == "QB One (1)"
