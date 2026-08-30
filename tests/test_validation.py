import numpy as np
import pandas as pd

from nuke_validation import prepare_actuals, build_validation, validation_summary


def test_validation_matches_names_and_calculates_metrics():
    players=pd.DataFrame({
        "Name":["Josh Allen","DJ Moore"],
        "Position":["QB","WR"],
        "Team":["BUF","CHI"],
        "Salary":[8000,6500],
        "ID":["1","2"],
    })
    matrix=np.array([[20,10],[30,20],[25,15],[35,25]],dtype=float)
    actual_raw=pd.DataFrame({"Player":["Josh Allen","DJ Moore"],"DKFP":[28,18]})
    actuals=prepare_actuals(actual_raw)
    detail=build_validation(players,matrix,actuals)
    summary,pos=validation_summary(detail)
    assert len(detail)==2
    assert summary["matched_players"]==2
    assert summary["mae"]>=0
    assert set(pos["Position"])=={"QB","WR"}


def test_prepare_actuals_requires_points():
    df=pd.DataFrame({"Player":["A"]})
    try:
        prepare_actuals(df)
        assert False
    except ValueError:
        assert True
