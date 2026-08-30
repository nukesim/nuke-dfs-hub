import pandas as pd
from nuke_crossseason_data import parse_rotoguru_page, normalize_rotoguru


def test_parse_rotoguru_pre_block():
    page='''<html><body><pre>Week;Year;GID;Name;Pos;Team;h/a;Oppt;DK points;DK salary\n1;2019;1;Mahomes, Patrick;QB;kan;h;hou;30.2;7200\n1;2019;2;Kansas City;Def;kan;h;hou;8;3000</pre></body></html>'''
    d=parse_rotoguru_page(page)
    assert len(d)==2
    assert d.iloc[0]["Name"]=="Patrick Mahomes"
    assert d.iloc[0]["Position"]=="QB"
    assert d.iloc[1]["Position"]=="DST"
    assert d.iloc[0]["Salary"]==7200


def test_normalize_drops_zero_salary():
    raw=pd.DataFrame({
        "week":[1,1],"year":[2020,2020],"player_name":["Doe, John","Smith, Bob"],
        "position":["WR","RB"],"team_name":["dal","dal"],"opponent_name":["nyg","nyg"],
        "points":[10,0],"salary":[5000,0]
    })
    d=normalize_rotoguru(raw)
    assert len(d)==1
    assert d.iloc[0]["Name"]=="John Doe"
    assert d.iloc[0]["Game"]=="DAL@NYG"
