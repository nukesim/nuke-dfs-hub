import numpy as np
import pandas as pd

from nuke_field import FIELD_ENGINE_VERSION, field_weights_v1, projection_free_player_ownership
from nuke_contest import simulate_contest


def _players():
    rows=[]
    specs=[
        ("QB","A",7000,"QB1",.95),("QB","B",6000,"QB1",.90),
        ("RB","A",8000,"RB1",.95),("RB","B",6500,"RB1",.90),("RB","C",5200,"RB2",.75),
        ("WR","A",7800,"WR1",.95),("WR","A",6000,"WR2",.85),("WR","B",7000,"WR1",.92),("WR","C",5000,"WR2",.78),
        ("TE","A",5500,"TE1",.92),("TE","B",4200,"TE1",.85),
        ("DST","A",3200,"DST",1.0),("DST","B",2800,"DST",1.0),
    ]
    for i,(pos,team,sal,role,conf) in enumerate(specs):
        rows.append({"Name":f"P{i}","Position":pos,"Team":team,"Salary":sal,"auto_role":role,
                     "starter_confidence":conf,"market_score":min(.99,.25+sal/10000)})
    return pd.DataFrame(rows)


def _results():
    lineups=[
        [0,2,3,5,6,7,9,8,11],
        [0,2,4,5,6,8,9,7,12],
        [1,3,4,7,8,5,10,6,11],
        [1,2,3,5,7,8,10,6,12],
    ]
    return pd.DataFrame({
        "Salary":[50000,49600,48700,49200],
        "NUKE Score":[140,136,128,132],
        "Ceiling 95":[190,184,172,178],
        "Stack":["QB + 2 / 1","QB + 2 / 0","QB + 1 / 1","QB + 1 / 0"],
        "_indices":lineups,
    })


def test_player_ownership_is_projection_free_and_position_scaled():
    own=projection_free_player_ownership(_players())
    assert not own.empty
    assert "Field Ownership %" in own.columns
    assert own["Field Ownership %"].between(.01,99.5).all()
    assert own.loc[own.Position.eq("QB"),"Field Ownership %"].sum() > 90


def test_field_weights_are_valid_mixture():
    weights,diag,detail=field_weights_v1(_results(),_players())
    assert diag["engine"] == FIELD_ENGINE_VERSION
    assert np.isclose(weights.sum(),1.0)
    assert (weights > 0).all()
    assert len(detail)==4
    assert "Field Archetype" in detail.columns
    assert "Lineup Ownership Sum %" in detail.columns


def test_field_engine_default_works_without_players_argument():
    results=_results()
    rng=np.random.default_rng(7)
    matrix=rng.normal(12,5,size=(60,13)).astype(np.float32)
    out,summary=simulate_contest(results,matrix,field_size=100,entry_fee=5,first_prize=100,iterations=50,seed=9)
    assert summary["field_model"] == FIELD_ENGINE_VERSION
    assert summary["engine"] == FIELD_ENGINE_VERSION
    assert "Expected Duplicates" in out.columns
    assert "Field Archetype" in out.columns
    assert "Lineup Ownership Sum %" in out.columns
