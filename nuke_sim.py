import numpy as np
import pandas as pd

DK_SLOTS = ["QB", "RB1", "RB2", "WR1", "WR2", "WR3", "TE", "FLEX", "DST"]
ROLE_ADJUST = {"AUTO":0.00,"QB1":0.08,"RB1":0.18,"RB2":-0.05,"RB3":-0.18,"WR1":0.14,"WR2":0.04,"WR3":-0.07,"TE1":0.12,"BACKUP":-0.20}
INACTIVE_STATUSES = {"OUT","IR","INACTIVE","SUSPENDED"}
AUTO_ROLE_MULTIPLIER = {"QB1":1.00,"QB2+":0.12,"RB1":1.08,"RB2":0.93,"RB3":0.78,"RB4+":0.62,"WR1":1.06,"WR2":1.00,"WR3":0.91,"WR4+":0.72,"TE1":1.04,"TE2+":0.76,"DST":1.00}

def _norm_pos(v):
    p=str(v).upper().strip(); return "DST" if p in {"D","DEF","DST"} else p.split("/")[0]
def _auto_role_label(pos,r):
    r=int(r)
    if pos=="QB": return "QB1" if r==1 else "QB2+"
    if pos=="RB": return "RB1" if r==1 else "RB2" if r==2 else "RB3" if r==3 else "RB4+"
    if pos=="WR": return "WR1" if r==1 else "WR2" if r==2 else "WR3" if r==3 else "WR4+"
    if pos=="TE": return "TE1" if r==1 else "TE2+"
    return "DST"
def _attach_auto_roles(out):
    x=out.copy(); x["team_depth_rank"]=1; x["team_pos_salary_max"]=x["Salary"]
    m=x["Position"].isin(["QB","RB","WR","TE"])
    if m.any():
        r=x.loc[m].copy(); r["team_depth_rank"]=r.groupby(["Team","Position"])["Salary"].rank(method="first",ascending=False).astype(int); r["team_pos_salary_max"]=r.groupby(["Team","Position"])["Salary"].transform("max")
        x.loc[r.index,"team_depth_rank"]=r["team_depth_rank"]; x.loc[r.index,"team_pos_salary_max"]=r["team_pos_salary_max"]
    x["salary_vs_team_top"]=(x["Salary"]/pd.to_numeric(x["team_pos_salary_max"],errors="coerce").replace(0,np.nan)).fillna(1).clip(0,1)
    x["auto_role"]=[_auto_role_label(p,r) for p,r in zip(x.Position,x.team_depth_rank)]; x["auto_role_multiplier"]=x.auto_role.map(AUTO_ROLE_MULTIPLIER).fillna(1).astype(float)
    x["auto_qb_eligible"]=(~x.Position.eq("QB"))|x.auto_role.eq("QB1"); x["starter_confidence"]=1.0
    for i,row in x.iterrows():
        if row.Position=="QB": x.at[i,"starter_confidence"]=.995 if row.auto_role=="QB1" else .01
        elif row.Position in {"RB","WR","TE"}:
            base={1:.94,2:.78,3:.58}.get(int(row.team_depth_rank),.32); x.at[i,"starter_confidence"]=float(np.clip(.65*base+.35*float(row.salary_vs_team_top),.05,.99))
    return x

def prepare_slate(df):
    aliases={"Name":["Name","name","Player","player","Name + ID"],"Position":["Position","position","Pos","pos","Roster Position"],"Salary":["Salary","salary"],"Team":["TeamAbbrev","Team","team","team_abbrev"],"Game":["Game Info","Game","game","game_info","game_id","Game ID"],"ID":["ID","Id","id","player_id"],"Status":["Status","status","Injury Status","injury_status"]}
    out=pd.DataFrame(index=df.index)
    for t,opts in aliases.items():
        c=next((c for c in opts if c in df.columns),None); out[t]=df[c] if c else ""
    out.Name=out.Name.fillna("").astype(str).str.replace(r"\s*\(\d+\)\s*$","",regex=True); out.Position=out.Position.map(_norm_pos); out.Salary=pd.to_numeric(out.Salary,errors="coerce").fillna(0).astype(int); out.Team=out.Team.fillna("").astype(str).str.upper().str.strip(); out.Game=out.Game.fillna("").astype(str).str.strip(); out.ID=out.ID.fillna("").astype(str); out.Status=out.Status.fillna("").astype(str).str.upper().str.strip()
    out=out[out.Position.isin(["QB","RB","WR","TE","DST"])&(out.Salary>0)].reset_index(drop=True); out=out[~out.Status.isin(INACTIVE_STATUSES)].reset_index(drop=True); out["market_score"]=out.groupby("Position")["Salary"].rank(pct=True).fillna(.5); out["role_override"]="AUTO"; out["usage_multiplier"]=1.0
    return _attach_auto_roles(out).reset_index(drop=True)

def _sample_points(row,rng,mode="NUKEM"):
    salary=float(row.Salary); pos=row.Position; base={"QB":13,"RB":8,"WR":7,"TE":5,"DST":5.5}[pos]; slope={"QB":.00115,"RB":.00155,"WR":.00145,"TE":.00135,"DST":.00055}[pos]; mean=base+max(0,salary-2500)*slope; sigma={"QB":6.2,"RB":7.2,"WR":7.8,"TE":6.5,"DST":5.5}[pos]
    usage=float(np.clip(float(getattr(row,"usage_multiplier",1) or 1),.25,2.25)); role=str(getattr(row,"role_override","AUTO") or "AUTO").upper().strip(); auto=float(getattr(row,"auto_role_multiplier",1) or 1)
    if pos!="DST": mean*=usage*auto*(1+ROLE_ADJUST.get(role,0)); sigma*=float(np.clip(np.sqrt(usage*max(auto,.25)),.55,1.45))
    if mode=="NUKEM":
        boom=.06+.12*float(getattr(row,"market_score",.5)); boom*=float(np.clip(.55+.45*auto,.35,1.10)) if pos in {"RB","WR","TE"} else 1; boom*=float(np.clip(.8+.2*usage,.65,1.3))
        if rng.random()<min(.32,boom): mean+=rng.gamma(2.2,4)*float(np.clip(usage*auto,.45,1.5))
        if rng.random()<.055: mean*=rng.uniform(.05,.45)
    return max(-4 if pos=="DST" else 0,rng.normal(mean,sigma))

def simulate_player_matrix(players,n_sims=1500,seed=26,mode="NUKEM"):
    rng=np.random.default_rng(seed); mat=np.zeros((n_sims,len(players)),dtype=np.float32); games=players.Game.fillna("").astype(str).tolist(); teams=players.Team.fillna("").astype(str).tolist()
    for s in range(n_sims):
        gf={g:rng.normal(0,3.4) for g in sorted(set(games))}; tf={t:rng.normal(0,2.4) for t in sorted(set(teams))}
        for i,row in enumerate(players.itertuples(index=False)):
            pts=_sample_points(row,rng,mode); pts += (.72*gf.get(row.Game,0)+.48*tf.get(row.Team,0)) if row.Position!="DST" else -.30*gf.get(row.Game,0); mat[s,i]=max(-6 if row.Position=="DST" else 0,pts)
    return mat

def _valid_lineup(indices,p,min_salary,max_salary=50000):
    if len(indices)!=9 or len(set(indices))!=9:return False
    r=p.iloc[indices]; sal=int(r.Salary.sum()); c=r.Position.value_counts().to_dict()
    if sal<min_salary or sal>max_salary:return False
    if not(c.get("QB",0)==1 and c.get("RB",0)>=2 and c.get("WR",0)>=3 and c.get("TE",0)>=1 and c.get("DST",0)==1):return False
    q=r[r.Position.eq("QB")]; return not("auto_qb_eligible" in q.columns and not bool(q.iloc[0].auto_qb_eligible))

def generate_lineups(players,n_lineups=600,min_salary=49400,seed=26):
    """Generate legal DK lineups with automatic tournament stack diversification."""
    rng=np.random.default_rng(seed); p=players.reset_index(drop=True)
    if p.empty:return []
    pos=p.Position.astype(str).to_numpy(); team=p.Team.astype(str).to_numpy(); game=p.Game.astype(str).to_numpy(); sal=p.Salary.to_numpy(int); market=p.market_score.to_numpy(float); usage=p.usage_multiplier.to_numpy(float); auto=p.auto_role_multiplier.to_numpy(float)
    w=np.power(.08+market,3)*np.clip(usage,.35,2.25)*np.clip(auto,.18,1.15); w=np.clip(w,1e-8,None)
    qbmask=pos=="QB"; qbmask &= p.auto_qb_eligible.fillna(False).to_numpy(bool) if "auto_qb_eligible" in p.columns else qbmask
    pools={k:np.where(qbmask if k=="QB" else pos==k)[0] for k in ["QB","RB","WR","TE","DST"]}; flex=np.where(np.isin(pos,["RB","WR","TE"]))[0]
    if any(len(v)==0 for v in pools.values()):return []
    seen=[]; keys=set(); attempts=0; target=max(40000,int(n_lineups)*220)
    # Tournament mixture: intentionally creates meaningful QB+2 and bring-back exposure.
    stack_shapes=[(1,0),(1,1),(2,0),(2,1),(2,2)]; shape_probs=np.array([.18,.30,.12,.32,.08])
    while len(seen)<int(n_lineups) and attempts<target:
        attempts+=1; qbids=pools["QB"]; qw=w[qbids]/w[qbids].sum(); qb=int(rng.choice(qbids,p=qw)); nmates,nbring=stack_shapes[int(rng.choice(len(stack_shapes),p=shape_probs))]
        mates=np.where((team==team[qb])&np.isin(pos,["WR","TE"]))[0]
        opp=np.where((game==game[qb])&(team!=team[qb])&np.isin(pos,["RB","WR","TE"]))[0]
        if len(mates)<nmates or len(opp)<nbring:continue
        chosen=[qb]
        mw=w[mates]/w[mates].sum(); chosen+=list(map(int,rng.choice(mates,nmates,replace=False,p=mw)))
        if nbring:
            avail=opp[~np.isin(opp,chosen)]; ow=w[avail]/w[avail].sum(); chosen+=list(map(int,rng.choice(avail,nbring,replace=False,p=ow)))
        # Fill position minimums after structural stack pieces are locked.
        for k,minimum in [("RB",2),("WR",3),("TE",1),("DST",1)]:
            have=sum(pos[i]==k for i in chosen); need=max(0,minimum-have)
            ids=pools[k][~np.isin(pools[k],chosen)]
            if len(ids)<need: chosen=[]; break
            if need:
                pw=w[ids]/w[ids].sum(); chosen+=list(map(int,rng.choice(ids,need,replace=False,p=pw)))
        if not chosen:continue
        # Exactly one FLEX remains after minimums; if stack pieces already created an extra, roster is full.
        while len(chosen)<9:
            ids=flex[~np.isin(flex,chosen)];
            if not len(ids):break
            fw=w[ids]/w[ids].sum(); chosen.append(int(rng.choice(ids,p=fw)))
        if len(chosen)!=9:continue
        total=int(sal[np.asarray(chosen)].sum()); key=tuple(sorted(chosen))
        if total<min_salary or total>50000 or key in keys or not _valid_lineup(chosen,p,min_salary):continue
        keys.add(key); seen.append(chosen)
    return seen

def _stack_label(rows):
    q=rows[rows.Position.eq("QB")]
    if q.empty:return "NO QB"
    t=q.iloc[0].Team; g=q.iloc[0].Game; mates=rows[(rows.Team.eq(t))&rows.Position.isin(["WR","TE"])]; opp=rows[(rows.Game.eq(g))&(~rows.Team.eq(t))&rows.Position.ne("DST")]
    return f"QB + {len(mates)} / {len(opp)}"

def _flex_pos(roster):
    c=roster.Position.value_counts().to_dict()
    return "RB" if c.get("RB",0)>2 else "WR" if c.get("WR",0)>3 else "TE" if c.get("TE",0)>1 else "?"
def evaluate_lineups(players,lineups,player_matrix):
    if not lineups:return pd.DataFrame()
    scores=np.stack([player_matrix[:,lu].sum(axis=1) for lu in lineups],axis=1); rows=[]
    for j,lu in enumerate(lineups):
        r=players.iloc[lu]; s=scores[:,j]; q=r[r.Position.eq("QB")]
        rows.append({"Rank":0,"NUKE Score":round(float(np.mean(s)+.65*np.std(s)+.25*np.quantile(s,.95)),2),"Median":round(float(np.median(s)),2),"Ceiling 95":round(float(np.quantile(s,.95)),2),"Salary":int(r.Salary.sum()),"Stack":_stack_label(r),"FLEX Pos":_flex_pos(r),"QB Auto Role":q.iloc[0].get("auto_role","QB1") if not q.empty else "","QB":" / ".join(r.loc[r.Position.eq("QB"),"Name"]),"RB":" / ".join(r.loc[r.Position.eq("RB"),"Name"]),"WR":" / ".join(r.loc[r.Position.eq("WR"),"Name"]),"TE":" / ".join(r.loc[r.Position.eq("TE"),"Name"]),"DST":" / ".join(r.loc[r.Position.eq("DST"),"Name"]),"_indices":lu})
    out=pd.DataFrame(rows).sort_values(["NUKE Score","Ceiling 95"],ascending=False).reset_index(drop=True); out["Rank"]=np.arange(1,len(out)+1); return out

def exposure_table(players,results,top_n=50):
    if results is None or results.empty:return pd.DataFrame()
    sample=results.head(min(top_n,len(results))); counts={}
    for lu in sample._indices:
        for i in lu:counts[i]=counts.get(i,0)+1
    rows=[]
    for i,c in counts.items():
        r=players.iloc[i]; rows.append({"Player":r.Name,"Pos":r.Position,"Team":r.Team,"Salary":int(r.Salary),"Auto Role":getattr(r,"auto_role",""),"Starter Confidence":round(100*float(getattr(r,"starter_confidence",1)),1),"Exposure %":round(100*c/len(sample),1)})
    return pd.DataFrame(rows).sort_values(["Exposure %","Salary"],ascending=[False,False]).reset_index(drop=True)

def position_exposure_table(players,results,top_n=None):
    if results is None or results.empty:return pd.DataFrame()
    x=results.head(min(int(top_n),len(results))) if top_n else results; denom=len(x); rows=[]
    for pos in ["QB","RB","WR","TE","DST"]:
        vals=[]
        for lu in x._indices:
            vals.extend(players.iloc[lu].loc[lambda z:z.Position.eq(pos),"Name"].tolist())
        vc=pd.Series(vals).value_counts() if vals else pd.Series(dtype=int)
        for name,c in vc.items(): rows.append({"Position":pos,"Player":name,"Lineups":int(c),"Exposure %":round(100*c/denom,1)})
    return pd.DataFrame(rows)

def flex_exposure_table(players,results,top_n=None):
    if results is None or results.empty:return pd.DataFrame()
    x=results.head(min(int(top_n),len(results))) if top_n else results; vc=x["FLEX Pos"].value_counts(); return pd.DataFrame({"FLEX Position":vc.index,"Lineups":vc.values,"Exposure %":np.round(100*vc.values/len(x),1)})
