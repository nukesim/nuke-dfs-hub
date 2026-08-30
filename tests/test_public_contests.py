import pandas as pd

from nuke_public_contests import parse_combined_standings


def test_parse_combined_standings_results_and_ownership():
    raw = pd.DataFrame({
        "Rank": [1, 2],
        "EntryId": [101, 102],
        "EntryName": ["a", "b"],
        "TimeRemaining": [0, 0],
        "Points": [200.5, 180.0],
        "Lineup": [
            "QB Josh Allen RB James Cook RB Breece Hall WR Stefon Diggs WR Tee Higgins WR Zay Flowers TE Dalton Kincaid FLEX Chris Godwin DST Bills",
            "QB Joe Burrow RB Joe Mixon RB James Cook WR Ja'Marr Chase WR Tee Higgins WR Stefon Diggs TE Dawson Knox FLEX Zay Flowers DST Bengals",
        ],
        "Unnamed: 6": [None, None],
        "Player": ["Josh Allen", "James Cook"],
        "%Drafted": ["25.00%", "40.00%"],
        "FPTS": [30.0, 22.0],
    })
    results, ownership = parse_combined_standings(raw, "123")
    assert len(results) == 2
    assert results.iloc[0]["contest_id"] == "123"
    assert results.iloc[0]["roster_size"] == 9
    assert len(ownership) == 2
    assert ownership.loc[ownership.player.eq("Josh Allen"), "pos"].iloc[0] == "QB"
    assert ownership.loc[ownership.player.eq("James Cook"), "pos"].iloc[0] == "RB"
    assert ownership.loc[ownership.player.eq("Josh Allen"), "drafted"].iloc[0] == 25.0
