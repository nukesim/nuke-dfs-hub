import numpy as np
import pandas as pd

TARGET_Z90 = 1.6448536269514722
POSITIONS = ["QB", "RB", "WR", "TE", "DST"]


def fit_position_calibration(detail, min_players=25):
    """Fit position mean-bias and spread multipliers from a training sample only.

    Bias is the average simulated mean minus actual DKFP. Spread uses the 90th
    percentile of absolute standardized residuals, translated to the central-90%
    normal reference. This is deliberately simple and auditable; it does not use
    holdout outcomes.
    """
    if detail is None or detail.empty:
        return pd.DataFrame(columns=["Position", "Players", "Mean Bias Correction", "Spread Multiplier"])

    rows=[]
    for pos in POSITIONS:
        d=detail[detail.Position.eq(pos)].copy()
        if len(d)<int(min_players):
            continue
        bias=float(d["Mean Error"].mean())
        sd=pd.to_numeric(d["Sim SD"],errors="coerce").replace(0,np.nan)
        resid=(pd.to_numeric(d["Actual DKFP"],errors="coerce")-pd.to_numeric(d["Sim Mean"],errors="coerce")).abs()
        z=(resid/sd).replace([np.inf,-np.inf],np.nan).dropna()
        if len(z)>=int(min_players):
            spread=float(np.quantile(z,.90)/TARGET_Z90)
        else:
            spread=1.0
        spread=float(np.clip(spread,.75,2.50))
        rows.append({
            "Position":pos,
            "Players":int(len(d)),
            "Mean Bias Correction":round(bias,4),
            "Spread Multiplier":round(spread,4),
        })
    return pd.DataFrame(rows)


def calibration_map(params):
    if params is None or params.empty:
        return {}
    return {
        str(r.Position): {
            "bias":float(getattr(r,"_2",0.0)) if False else float(r["Mean Bias Correction"]),
            "spread":float(r["Spread Multiplier"]),
        }
        for _,r in params.iterrows()
    }


def apply_position_calibration(players, matrix, params):
    """Apply training-derived calibration to a new simulation matrix.

    The original player-level simulated mean is shifted by the learned position
    bias, while deviations around that mean are widened/narrowed by the learned
    position spread multiplier.
    """
    arr=np.asarray(matrix,dtype=float)
    if arr.ndim!=2 or arr.shape[1]!=len(players):
        raise ValueError("Player table and simulation matrix do not align.")
    out=arr.copy()
    pmap=calibration_map(params)
    positions=players.Position.astype(str).to_numpy()
    for j,pos in enumerate(positions):
        cfg=pmap.get(pos,{"bias":0.0,"spread":1.0})
        col=arr[:,j]
        mean=float(np.mean(col))
        corrected_mean=mean-float(cfg["bias"])
        out[:,j]=corrected_mean+(col-mean)*float(cfg["spread"])
        floor=-6.0 if pos=="DST" else 0.0
        out[:,j]=np.maximum(floor,out[:,j])
    return out.astype(np.float32)


def summary_comparison(original_summary, calibrated_summary):
    if not original_summary or not calibrated_summary:
        return pd.DataFrame()
    rows=[]
    for label,s in [("V2 Original",original_summary),("V2.1 Candidate",calibrated_summary)]:
        rows.append({
            "Model":label,
            "Players":int(s["matched_players"]),
            "MAE":round(float(s["mae"]),3),
            "Bias":round(float(s["bias"]),3),
            "Inside 50%":round(float(s["inside_50"]),1),
            "Inside 80%":round(float(s["inside_80"]),1),
            "Inside 90%":round(float(s["inside_90"]),1),
        })
    return pd.DataFrame(rows)


def calibration_distance(summary):
    if not summary:
        return np.inf
    return (
        abs(float(summary["inside_50"])-50.0)+
        abs(float(summary["inside_80"])-80.0)+
        abs(float(summary["inside_90"])-90.0)
    )


def promotion_gate(original_summary, calibrated_summary):
    """Conservative diagnostic gate; passing does not automatically alter live V2."""
    if not original_summary or not calibrated_summary:
        return {"pass":False,"checks":{}}
    checks={
        "Holdout MAE not worse":float(calibrated_summary["mae"])<=float(original_summary["mae"])+0.05,
        "Absolute holdout bias improved":abs(float(calibrated_summary["bias"]))<abs(float(original_summary["bias"])),
        "Interval calibration improved":calibration_distance(calibrated_summary)<calibration_distance(original_summary),
    }
    return {"pass":all(checks.values()),"checks":checks}
