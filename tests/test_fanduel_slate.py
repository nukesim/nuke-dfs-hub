from fanduel_slate import load_fanduel_slate, fanduel_slate_status
from nuke_sim import prepare_slate


def test_fanduel_week1_repository_slate_loads():
    raw=load_fanduel_slate()
    assert len(raw)==732
    required={"Id","Position","Nickname","Salary","Game","Team","Opponent","Roster Position"}
    assert required.issubset(set(raw.columns))
    players=prepare_slate(raw,site="FD")
    assert len(players)>0
    assert players["Salary"].max()<=10000
    assert players["Position"].isin(["QB","RB","WR","TE","DST"]).all()
    status=fanduel_slate_status()
    assert status["available"] is True
    assert status["players"]==732
