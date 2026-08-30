import numpy as np
import pandas as pd

FIELD_ENGINE_VERSION = "Field Engine V3"

ROLE_BONUS = {
    "QB1": 0.35, "RB1": 0.55, "RB2": 0.18, "RB3": -0.30,
    "WR1": 0.48, "WR2": 0.20, "WR3": -0.05, "TE1": 0.38,
    "QB2+": -2.5, "RB4+": -0.75, "WR4+": -0.65, "TE2+": -0.45,
    "DST": 0.0,
}
EXPECTED_SLOTS = {"QB": 1.00, "RB": 2.30, "WR": 3.55, "TE": 1.15, "DST": 1.00}


def _z(v):
    a=np.asarray(v,dtype=float)
    if not len(a): return a
    sd=float(np.std(a))
    return (a-float(np.mean(a)))/(sd if sd>1e-9 else 1.0)


def projection_free_player_ownership(players):
    """Projection-free field ownership prior from DK salary, role and team market strength."""
    p=players.reset_index(drop=True).copy()
    if p.empty:
        return pd.DataFrame(columns=["Player","Position","Team","Salary","Field Ownership %"])
    p["market_score"]=pd.to_numeric(p.get("market_score",0.5),errors="coerce").fillna(0.5).clip(0,1)
    p["starter_confidence"]=pd.to_numeric(p.get("starter_confidence",1.0),errors="coerce").fillna(1.0).clip(0,1)
    role=p.get("auto_role",pd.Series([""]*len(p))).astype(str)
    role_bonus=role.map(ROLE_BONUS).fillna(0.0).to_numpy(float)
    skill=p[p.Position.isin(["QB","RB","WR","TE"])].groupby("Team")["Salary"].sum()
    team_strength=p.Team.map(skill).fillna(skill.median() if len(skill) else 0).to_numpy(float)
    logit=2.25*p.market_score.to_numpy(float)+0.75*p.starter_confidence.to_numpy(float)+role_bonus+0.18*_z(team_strength)
    raw=np.exp(np.clip(logit,-6,7)); ownership=np.zeros(len(p),dtype=float); pos_arr=p.Position.astype(str).to_numpy()
    for pos,slots in EXPECTED_SLOTS.items():
        ids=np.where(pos_arr==pos)[0]
        if not len(ids): continue
        vals=raw[ids]; vals=vals/vals.sum() if vals.sum() else np.full(len(ids),1.0/len(ids))
        ownership[ids]=100.0*slots*vals
    ownership=np.clip(ownership,0.01,99.5)
    out=pd.DataFrame({"Player":p.Name.astype(str),"Position":p.Position.astype(str),"Team":p.Team.astype(str),"Salary":pd.to_numeric(p.Salary,errors="coerce").fillna(0).astype(int),"Auto Role":role,"Field Ownership %":np.round(ownership,2)})
    out["Ownership Rank"]=out.groupby("Position")["Field Ownership %"].rank(method="first",ascending=False).astype(int)
    return out


def _candidate_frequency_ownership(results):
    lineups=[list(x) for x in results["_indices"]]; max_id=max((max(x) for x in lineups if x),default=-1)
    counts=np.zeros(max_id+1,dtype=float)
    for lu in lineups:
        for i in lu: counts[int(i)]+=1.0
    return np.clip(100.0*counts/max(1,len(lineups)),0.01,99.5)/100.0


def _lineup_features(results,players=None):
    r=results.reset_index(drop=True).copy()
    own=projection_free_player_ownership(players)["Field Ownership %"].to_numpy(float)/100.0 if players is not None and len(players) else _candidate_frequency_ownership(r)
    salary=pd.to_numeric(r["Salary"],errors="coerce").fillna(49000).to_numpy(float)
    nuke=pd.to_numeric(r.get("NUKE Score",0),errors="coerce").fillna(0).to_numpy(float)
    ceiling=pd.to_numeric(r.get("Ceiling 95",0),errors="coerce").fillna(0).to_numpy(float)
    stack=r.get("Stack",pd.Series([""]*len(r))).astype(str)
    n=len(r)
    log_own=np.zeros(n); chalk=np.zeros(n); max_own=np.zeros(n); low_owned=np.zeros(n); ultra_chalk=np.zeros(n); product_own=np.zeros(n)
    team_max=np.zeros(n); game_max=np.zeros(n); qb_own=np.zeros(n); pair_log=np.zeros(n); core_log=np.zeros(n)
    team_arr=players.Team.astype(str).to_numpy() if players is not None and len(players) and "Team" in players.columns else None
    game_arr=players.Game.astype(str).to_numpy() if players is not None and len(players) and "Game" in players.columns else None
    pos_arr=players.Position.astype(str).to_numpy() if players is not None and len(players) and "Position" in players.columns else None
    for j,lu in enumerate(r["_indices"]):
        ids=np.asarray(list(lu),dtype=int); vals=np.clip(own[ids],0.001,0.995)
        logs=np.log(vals)
        log_own[j]=logs.sum(); chalk[j]=vals.sum(); max_own[j]=vals.max(); low_owned[j]=np.sum(vals<0.05); ultra_chalk[j]=np.sum(vals>=0.20); product_own[j]=np.exp(logs.mean())
        # Popular two- and three-player cores are a major source of duplicated lineups.
        sv=np.sort(vals)[::-1]
        pair_log[j]=np.log(max(1e-9,sv[0]*sv[1])) if len(sv)>=2 else -9.0
        core_log[j]=np.log(max(1e-9,sv[0]*sv[1]*sv[2])) if len(sv)>=3 else -12.0
        if team_arr is not None:
            _,cnt=np.unique(team_arr[ids],return_counts=True); team_max[j]=cnt.max()
        if game_arr is not None:
            _,cnt=np.unique(game_arr[ids],return_counts=True); game_max[j]=cnt.max()
        if pos_arr is not None:
            q=ids[pos_arr[ids]=="QB"]
            if len(q): qb_own[j]=own[q[0]]
    # Full salary is common, but leave a realistic tail of salary left on the table.
    salary_left=50000.0-salary
    salary_full=np.exp(-np.square(salary_left/650.0))
    salary_near=np.exp(-np.square((salary_left-650.0)/900.0))
    stack_bonus=np.zeros(n); bringback=np.zeros(n); double_stack=np.zeros(n); naked=np.zeros(n)
    stack_bonus+=np.where(stack.str.startswith("QB + 1 / 1"),0.45,0.0); bringback+=np.where(stack.str.contains("/ 1|/ 2",regex=True),1.0,0.0)
    stack_bonus+=np.where(stack.str.startswith("QB + 2 / 1"),0.72,0.0); double_stack+=np.where(stack.str.startswith("QB + 2"),1.0,0.0)
    stack_bonus+=np.where(stack.str.startswith("QB + 2 / 0"),0.24,0.0); stack_bonus+=np.where(stack.str.startswith("QB + 1 / 0"),0.08,0.0); stack_bonus+=np.where(stack.str.startswith("QB + 2 / 2"),0.42,0.0)
    naked+=np.where(stack.str.startswith("QB + 0"),1.0,0.0)
    return {"salary":salary,"salary_left":salary_left,"salary_full":salary_full,"salary_near":salary_near,"nuke_z":_z(nuke),"ceiling_z":_z(ceiling),"log_own_z":_z(log_own),"max_own":max_own,"low_owned":low_owned,"ultra_chalk":ultra_chalk,"stack_bonus":stack_bonus,"chalk_sum":chalk,"product_own":product_own,"bringback":bringback,"double_stack":double_stack,"naked":naked,"team_max":team_max,"game_max":game_max,"qb_own":qb_own,"pair_pop_z":_z(pair_log),"core_pop_z":_z(core_log)}


def field_weights_v1(results,players=None):
    """Field Engine V3: projection-free opponent behavior + duplication structure.

    V3 keeps the public function name for backwards compatibility. It models five
    opponent archetypes instead of treating the field as one optimizer. Salary-left,
    QB popularity, game/team concentration, popular cores and stacking behavior are
    explicitly represented. This remains a behavioral model, not live ownership data.
    """
    r=results.reset_index(drop=True)
    if r.empty: return np.array([],dtype=float),{},pd.DataFrame()
    f=_lineup_features(r,players)

    # Public/chalk builds: salary efficient, popular players/QBs, weaker correlation discipline.
    chalk=1.55*f["log_own_z"]+0.70*f["salary_full"]+0.22*f["salary_near"]+0.22*_z(f["qb_own"])+0.10*f["stack_bonus"]+0.12*f["pair_pop_z"]-0.20*f["low_owned"]
    # Sharp GPP builds: correlation + ceiling, willing to leave salary and use lower-owned pieces.
    sharp=0.40*f["log_own_z"]+0.24*f["salary_full"]+0.28*f["salary_near"]+1.08*f["stack_bonus"]+0.82*f["ceiling_z"]+0.42*f["nuke_z"]+0.24*f["bringback"]+0.12*f["double_stack"]-0.08*f["core_pop_z"]
    # Balanced optimizers: still salary/ownership sensitive with reasonable stacking.
    balanced=0.86*f["log_own_z"]+0.50*f["salary_full"]+0.28*f["salary_near"]+0.58*f["stack_bonus"]+0.30*f["ceiling_z"]+0.10*f["bringback"]+0.08*f["pair_pop_z"]
    # Game stack hunters concentrate players from one game more aggressively.
    game_stack=0.48*f["log_own_z"]+0.28*f["salary_near"]+0.92*f["stack_bonus"]+0.36*f["bringback"]+0.22*f["double_stack"]+0.24*_z(f["game_max"])+0.30*f["ceiling_z"]
    # Recreational builds use popular names/QBs but have weaker stack discipline.
    recreational=0.48*f["log_own_z"]+0.48*f["salary_full"]+0.22*_z(f["qb_own"])+0.10*_z(f["max_own"])-0.06*f["stack_bonus"]-0.10*f["low_owned"]

    archetypes={"Chalk/Public":(0.34,chalk),"Sharp GPP":(0.25,sharp),"Balanced":(0.21,balanced),"Game Stack":(0.12,game_stack),"Recreational":(0.08,recreational)}
    mix=np.zeros(len(r)); components={}
    for name,(share,logits) in archetypes.items():
        clipped=np.clip(logits,-10,10); w=np.exp(clipped-np.max(clipped)); w=w/w.sum() if w.sum() else np.full(len(w),1.0/len(w)); components[name]=w; mix+=share*w
    mix/=mix.sum()

    # Duplication pressure is deliberately separate from field selection probability.
    # It estimates how likely the same construction is to be repeated once selected.
    dup_log=0.88*f["log_own_z"]+0.42*f["pair_pop_z"]+0.26*f["core_pop_z"]+0.34*f["salary_full"]+0.14*_z(f["qb_own"])+0.08*f["ultra_chalk"]-0.16*f["low_owned"]
    dup_pressure=np.exp(np.clip(dup_log,-7,7)); dup_pressure/=max(1e-9,float(np.mean(dup_pressure)))

    detail=pd.DataFrame({
        "Field Popularity %":np.round(100*mix,4),
        "Lineup Ownership Sum %":np.round(100*f["chalk_sum"],1),
        "Max Player Ownership %":np.round(100*f["max_own"],1),
        "QB Ownership %":np.round(100*f["qb_own"],1),
        "Sub-5% Players":f["low_owned"].astype(int),
        "20%+ Players":f["ultra_chalk"].astype(int),
        "Salary Left":np.maximum(0,50000-f["salary"]).astype(int),
        "Field Team Max":f["team_max"].astype(int),
        "Field Game Max":f["game_max"].astype(int),
        "Duplication Pressure":np.round(dup_pressure,3),
    })
    names=np.array(list(components)); detail["Field Archetype"]=names[np.argmax(np.stack([components[k] for k in components],axis=1),axis=1)]
    diagnostics={
        "engine":FIELD_ENGINE_VERSION,"chalk_share":0.34,"sharp_share":0.25,"balanced_share":0.21,"game_stack_share":0.12,"recreational_share":0.08,
        "ownership_source":"salary/role player model" if players is not None and len(players) else "salary/role candidate-frequency proxy",
        "field_note":"Behavioral field + duplication pressure; not live ownership projections",
    }
    return mix,diagnostics,detail
