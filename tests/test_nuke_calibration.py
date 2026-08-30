import numpy as np
import pandas as pd

from nuke_calibration import fit_position_calibration, apply_position_calibration, promotion_gate


def test_fit_position_calibration_recovers_positive_bias_and_wider_spread():
    rng=np.random.default_rng(1)
    n=200
    sim_mean=np.full(n,20.0)
    sim_sd=np.full(n,4.0)
    actual=sim_mean-3.0+rng.normal(0,7.0,size=n)
    detail=pd.DataFrame({
        "Position":["QB"]*n,
        "Mean Error":sim_mean-actual,
        "Sim SD":sim_sd,
        "Actual DKFP":actual,
        "Sim Mean":sim_mean,
    })
    params=fit_position_calibration(detail,min_players=25)
    row=params.iloc[0]
    assert row.Position=="QB"
    assert row["Mean Bias Correction"]>2.0
    assert row["Spread Multiplier"]>1.0


def test_apply_position_calibration_shifts_mean_and_changes_spread():
    players=pd.DataFrame({"Position":["QB","WR"]})
    matrix=np.array([[10,5],[20,10],[30,15]],dtype=np.float32)
    params=pd.DataFrame([
        {"Position":"QB","Players":100,"Mean Bias Correction":4.0,"Spread Multiplier":1.5},
        {"Position":"WR","Players":100,"Mean Bias Correction":2.0,"Spread Multiplier":2.0},
    ])
    out=apply_position_calibration(players,matrix,params)
    assert np.isclose(out[:,0].mean(),16.0)
    assert np.isclose(out[:,1].mean(),8.0)
    assert out[:,0].std()>matrix[:,0].std()
    assert out[:,1].std()>matrix[:,1].std()


def test_promotion_gate_requires_all_three_improvements():
    original={"mae":5.5,"bias":2.0,"inside_50":34,"inside_80":63,"inside_90":74}
    candidate={"mae":5.2,"bias":0.5,"inside_50":46,"inside_80":76,"inside_90":87}
    gate=promotion_gate(original,candidate)
    assert gate["pass"] is True
    bad=dict(candidate); bad["mae"]=6.0
    assert promotion_gate(original,bad)["pass"] is False
