from fanduel_slate import load_fanduel_slate, fanduel_slate_status
from nuke_game_pool import game_environment
from nuke_odds import load_current_odds
from nuke_sim import prepare_slate


def test_fanduel_week8_repository_slate_loads():
    raw = load_fanduel_slate()
    assert len(raw) == 551
    required = {"Id", "Position", "Nickname", "Salary", "Game", "Team", "Opponent", "Roster Position"}
    assert required.issubset(raw.columns)
    assert raw["Id"].astype(str).str.startswith("135859-").all()
    assert raw["Id"].is_unique
    assert raw["Game"].nunique() == 11
    assert raw["Team"].nunique() == 22
    assert raw["Salary"].between(3000, 9400).all()

    players = prepare_slate(raw, site="FD")
    assert not players.empty
    assert players["Salary"].max() <= 9400
    assert players["Position"].isin(["QB", "RB", "WR", "TE", "DST"]).all()
    assert players["ID"].astype(str).str.startswith("135859-").all()
    assert players["Game"].nunique() == 11
    assert players["Team"].nunique() == 22

    status = fanduel_slate_status()
    assert status["available"] is True
    assert status["players"] == 551


def test_fanduel_week8_games_receive_valid_environment():
    players = prepare_slate(load_fanduel_slate(), site="FD")
    odds = load_current_odds()
    environment = game_environment(players, odds)
    assert environment["Game"].nunique() == 11
    assert len(environment) == 22
    assert set(environment["Team"]) == set(players["Team"])
    assert environment["Team Total"].notna().all()
    assert environment["Game Total"].notna().all()
    assert (environment["Game Total"] > 0).all()
    # Old sportsbook snapshots may not cover the new slate. Fallback is valid.
    assert environment["Source"].notna().all()

