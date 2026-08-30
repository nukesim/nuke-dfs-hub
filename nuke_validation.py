import re
import numpy as np
import pandas as pd

POINT_ALIASES=["Actual DKFP","DKFP","FPTS","Fantasy Points","FantasyPoints","Points","Actual Points","Score"]
NAME_ALIASES=["Name","Player","Player Name","name","player"]
ID_ALIASES=["ID","Id","id","player_id","Player ID"]


def _pick_col(df, aliases):
    return next((c for c in aliases if c in df.columns), None)


def normalize_name(v):
    s=str(v or "").strip().lower()
    s=re.sub(r"\s*\(\d+\)\s*$","",s)
    s=re.sub(r"[^a-z0-9]+"," ",s)
    return re.sub(r"\s+"," ",s).strip()


def prepare_actuals(df, name_col=None, points_col=None, id_col=None):
    name_col=name_col or _pick_col(df,NAME_ALIASES)
    points_col=points_col or _pick_col(df,POINT_ALIASES)
    id_col=id_col or _pick_col(df,ID_ALIASES)
    if not points_col:
        raise ValueError("Could not identify the actual fantasy-points column.")
    if not name_col and not id_col:
        raise ValueError("Actual-results file needs a player name or player ID column.")
    out=pd.DataFrame(index=df.index)
    out["Actual DKFP"]=pd.to_numeric(df[points_col],errors="coerce")
    out["actual_name"]=df[name_col].astype(str) if name_col else ""
    out["actual_id"]=df[id_col].astype(str) if id_col else ""
    out["name_key"]=out.actual_name.map(normalize_name)
    return out.dropna(subset=["Actual DKFP"]).reset_index(drop=True)


def build_validation(players, matrix, actuals):
    if len(players)!=matrix.shape[1]:
        raise ValueError("Player table and simulation matrix do not align.")
    p=players.reset_index(drop=True).copy()
    p["name_key"]=p.Name.map(normalize_name)
    p["id_key"]=p.ID.fillna("").astype(str)
    a=actuals.copy()
    a["id_key"]=a.actual_id.fillna("").astype(str)
    by_id={k:i for i,k in enumerate(a.id_key) if k and k.lower()!="nan"}
    by_name={k:i for i,k in enumerate(a.name_key) if k}
    rows=[]
    for i,r in p.iterrows():
        ai=by_id.get(r.id_key) if r.id_key else None
        if ai is None: ai=by_name.get(r.name_key)
        if ai is None: continue
        actual=float(a.iloc[ai]["Actual DKFP"])
        sims=np.asarray(matrix[:,i],dtype=float)
        mean=float(np.mean(sims)); median=float(np.median(sims)); sd=float(np.std(sims)); p10,p25,p75,p90,p95=np.quantile(sims,[.10,.25,.75,.90,.95])
        percentile=float(np.mean(sims<=actual)*100.0)
        rows.append({
            "Player":r.Name,"Position":r.Position,"Team":r.Team,"Salary":int(r.Salary),"Actual DKFP":round(actual,2),
            "Sim Mean":round(mean,2),"Sim Median":round(median,2),"Sim SD":round(sd,2),"P10":round(float(p10),2),"P25":round(float(p25),2),"P75":round(float(p75),2),"P90":round(float(p90),2),"P95":round(float(p95),2),
            "Mean Error":round(mean-actual,2),"Abs Error":round(abs(mean-actual),2),"Actual Percentile":round(percentile,1),
            "Inside 50%":bool(p25<=actual<=p75),"Inside 80%":bool(p10<=actual<=p90),"Inside 90%":bool(np.quantile(sims,.05)<=actual<=p95)
        })
    return pd.DataFrame(rows)


def validation_summary(detail):
    if detail is None or detail.empty:
        return {},pd.DataFrame()
    d=detail.copy()
    summary={
        "matched_players":int(len(d)),
        "mae":float(d["Abs Error"].mean()),
        "bias":float(d["Mean Error"].mean()),
        "inside_50":float(d["Inside 50%"].mean()*100),
        "inside_80":float(d["Inside 80%"].mean()*100),
        "inside_90":float(d["Inside 90%"].mean()*100),
        "median_actual_percentile":float(d["Actual Percentile"].median()),
    }
    pos=d.groupby("Position",as_index=False).agg(
        Players=("Player","count"),MAE=("Abs Error","mean"),Bias=("Mean Error","mean"),
        Inside_50=("Inside 50%","mean"),Inside_80=("Inside 80%","mean"),Inside_90=("Inside 90%","mean"),
        Actual_DKFP=("Actual DKFP","mean"),Sim_Mean=("Sim Mean","mean")
    )
    for c in ["Inside_50","Inside_80","Inside_90"]: pos[c]=(100*pos[c]).round(1)
    for c in ["MAE","Bias","Actual_DKFP","Sim_Mean"]: pos[c]=pos[c].round(2)
    pos=pos.rename(columns={"Inside_50":"Inside 50%","Inside_80":"Inside 80%","Inside_90":"Inside 90%","Actual_DKFP":"Avg Actual DKFP","Sim_Mean":"Avg Sim Mean"})
    return summary,pos
