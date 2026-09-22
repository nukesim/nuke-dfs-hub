from fanduel_slate import load_fanduel_slate, fanduel_slate_status
from nuke_game_pool import game_environment
from nuke_odds import load_current_odds
from nuke_sim import prepare_slate


def test_fanduel_week3_repository_slate_loads():
    raw=load_fanduel_slate()
    assert len(raw)==653
    required={"Id","Position","Nickname","Salary","Game","Team","Opponent","Roster Position"}
    assert required.issubset(set(raw.columns))
    players=prepare_slate(raw,site="FD")
    assert len(players)>0
    assert players["Salary"].max()<=10000
    assert players["Position"].isin(["QB","RB","WR","TE","DST"]).all()
    status=fanduel_slate_status()
    assert status["available"] is True
    assert status["players"]==653


def test_fanduel_week3_games_receive_sportsbook_totals():
    players=prepare_slate(load_fanduel_slate(),site="FD")
    odds=load_current_odds()
    environment=game_environment(players,odds)
    assert environment["Game"].nunique()==13
    assert environment["Source"].eq("Sportsbook Consensus").all()
    jacksonville=environment[environment["Team"].eq("JAC")].iloc[0]
    sportsbook=odds[(odds["Team"].eq("JAX")) & (odds["Opponent"].eq("NE"))].iloc[0]
    assert jacksonville["Opponent"]=="NE"
    assert jacksonville["Game Total"]==sportsbook["Game Total"]
