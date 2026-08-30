import pandas as pd

import nuke_historical_dk as h


def test_recover_contest_draftables(monkeypatch):
    responses = [
        {"contest": {"draftGroupId": 12345}},
        {"draftables": [
            {"displayName": "Player A", "position": "QB", "salary": 6000, "teamAbbreviation": "AAA", "draftableId": 1},
            {"displayName": "Team B", "position": "DEF", "salary": 2500, "teamAbbreviation": "BBB", "draftableId": 2},
        ]},
    ]

    def fake_get(url, timeout=12):
        return responses.pop(0)

    monkeypatch.setattr(h, "_get_json", fake_get)
    slate, meta = h.recover_contest_draftables("999")
    assert meta["recovered"] is True
    assert meta["draft_group_id"] == "12345"
    assert len(slate) == 2
    assert slate.loc[0, "salary"] == 6000
    assert slate.loc[1, "position"] == "DST"


def test_recover_contest_draftables_missing_history(monkeypatch):
    def fail(url, timeout=12):
        raise RuntimeError("gone")

    monkeypatch.setattr(h, "_get_json", fail)
    slate, meta = h.recover_contest_draftables("999")
    assert isinstance(slate, pd.DataFrame)
    assert slate.empty
    assert meta["recovered"] is False
    assert "unavailable" in meta["error"].lower()
