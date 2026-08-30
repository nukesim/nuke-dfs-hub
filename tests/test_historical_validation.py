import pandas as pd

from nuke_historical_data import normalize_nfldfs, historical_week, available_weeks, starter_aware_pool
from nuke_validation import prepare_actuals


def test_normalize_nfldfs_and_week_filter():
    raw=pd.DataFrame({
        "week":[1,1,2],"year":[2017,2017,2017],
        "player_name":["Smith, Alex","Hunt, Kareem","Brady, Tom"],
        "position":["QB","RB","QB"],"team_name":["kan","kan","nwe"],
        "opponent_name":["nwe","nwe","kan"],"points":[34.02,49.6,20.0],
        "salary":[5400,5800,7600],"dfs_site":["dk","dk","dk"]
    })
    data=normalize_nfldfs(raw)
    assert data.loc[0,"Name"]=="Alex Smith"
    assert data.loc[0,"Team"]=="KAN"
    assert data.loc[0,"Actual DK Points"]==34.02
    assert available_weeks(data,2017)==[1,2]
    week1=historical_week(data,2017,1)
    assert len(week1)==2


def test_defense_normalizes_to_dst_and_zero_salary_drops():
    raw=pd.DataFrame({
        "week":[1,1],"year":[2017,2017],"player_name":["Minnesota","Free Player"],
        "position":["Def","WR"],"team_name":["min","min"],"opponent_name":["nor","nor"],
        "points":[11,0],"salary":[3000,0]
    })
    data=normalize_nfldfs(raw)
    assert len(data)==1
    assert data.iloc[0].Position=="DST"


def test_starter_aware_pool_uses_salary_rank_not_actual_points():
    raw=pd.DataFrame({
        "week":[1]*8,"year":[2017]*8,
        "player_name":["Starter, Q","Backup, Q","One, R","Two, R","Three, R","Four, R","One, T","Two, T"],
        "position":["QB","QB","RB","RB","RB","RB","TE","TE"],
        "team_name":["abc"]*8,"opponent_name":["xyz"]*8,
        "points":[0,40,0,0,0,50,0,30],
        "salary":[7000,4000,8000,7000,6000,5000,5000,4000]
    })
    data=normalize_nfldfs(raw)
    pool=starter_aware_pool(data)
    names=set(pool.Name)
    assert "Q Starter" in names
    assert "Q Backup" not in names
    assert "R One" in names and "R Three" in names
    assert "R Four" not in names
    assert "T One" in names and "T Two" in names


def test_auto_actuals_match_expected_schema():
    actuals=prepare_actuals(pd.DataFrame({"Name":["Alex Smith"],"Actual DKFP":[34.02]}),name_col="Name",points_col="Actual DKFP")
    assert actuals.iloc[0]["Actual DKFP"]==34.02
    assert actuals.iloc[0]["name_key"]=="alex smith"
