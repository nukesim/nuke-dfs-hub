import numpy as np
import pandas as pd
from dfs_platform import get_platform, player_name_series

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

def prepare_slate(df,site="DK"):
    aliases={"Name":["Name","name","Nickname","nickname","Player","player","Name + ID"],"Position":["Position","position","Pos","pos","Roster Position"],"Salary":["Salary","salary"],"Team":["TeamAbbrev","Team","team","team_abbrev"],"Game":["Game Info","Game","game","game_info","game_id","Game ID"],"ID":["ID","Id","id","player_id"],"Status":["Status","status","Injury Status","injury_status","Injury Indicator"]}
    out=pd.DataFrame(index=df.index)
    for t,opts in aliases.items():
        c=next((c for c in opts if c in df.columns),None); out[t]=df[c] if c else ""
    if not out["Name"].astype(str).str.strip().ne("").any():
        names=player_name_series(df)
        if names is not None: out["Name"]=names
    out.Name=out.Name.fillna("").astype(str).str.replace(r"\s*\(\d+\)\s*$","",regex=True); out.Position=out.Position.map(_norm_pos); out.Salary=pd.to_numeric(out.Salary,errors="coerce").fillna(0).astype(int); out.Team=out.Team.fillna("").astype(str).str.upper().str.strip(); out.Game=out.Game.fillna("").astype(str).str.strip(); out.ID=out.ID.fillna("").astype(str).str.strip(); out.Status=out.Status.fillna("").astype(str).str.upper().str.strip().replace({"O":"OUT"}).replace({"O":"OUT"})
    # FanDuel defense rows can have an empty Nickname even though Team/Id are present.
    # Give every defense a stable visible name while preserving FanDuel's real player ID for export.
    dst_blank=out.Position.eq("DST") & ~out.Name.astype(str).str.strip().ne("")
    if dst_blank.any():
        out.loc[dst_blank,"Name"]=out.loc[dst_blank,"Team"].astype(str).str.strip()+" D/ST"
    out=out[out.Position.isin(["QB","RB","WR","TE","DST"])&(out.Salary>0)].reset_index(drop=True); out=out[~out.Status.isin(INACTIVE_STATUSES)].reset_index(drop=True); out["market_score"]=out.groupby("Position")["Salary"].rank(pct=True).fillna(.5); out["role_override"]="AUTO"; out["usage_multiplier"]=1.0; out["generation_boost"]=0.0
    out=_attach_auto_roles(out).reset_index(drop=True)
    out.attrs["site"]=get_platform(site).code
    return out

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

def _valid_lineup(indices,p,min_salary,max_salary=None,site="DK"):
    if max_salary is None: max_salary=get_platform(site).salary_cap
    if len(indices)!=9 or len(set(indices))!=9:return False
    r=p.iloc[indices]; sal=int(r.Salary.sum()); c=r.Position.value_counts().to_dict()
    if sal<min_salary or sal>max_salary:return False
    if not(c.get("QB",0)==1 and c.get("RB",0)>=2 and c.get("WR",0)>=3 and c.get("TE",0)>=1 and c.get("DST",0)==1):return False
    q=r[r.Position.eq("QB")]; return not("auto_qb_eligible" in q.columns and not bool(q.iloc[0].auto_qb_eligible))

def generate_lineups(players,n_lineups=600,min_salary=None,seed=26,site="DK"):
    """Candidate Engine V3: salary-aware tournament construction.

    Builds the first eight roster spots under the existing stack/profile rules, then solves
    the final FLEX directly inside the legal salary window instead of repeatedly creating
    full lineups that must be rejected afterward.
    """
    rng=np.random.default_rng(seed); p=players.reset_index(drop=True)
    if p.empty:return []
    cfg=get_platform(site); salary_cap=int(cfg.salary_cap); min_salary=int(cfg.default_min_salary if min_salary is None else min_salary); n_lineups=int(n_lineups)
    pos=p.Position.astype(str).to_numpy(); team=p.Team.astype(str).to_numpy(); game=p.Game.astype(str).to_numpy(); sal=p.Salary.to_numpy(int)
    market=p.market_score.to_numpy(float); usage=p.usage_multiplier.to_numpy(float); auto=p.auto_role_multiplier.to_numpy(float)
    gen_boost=pd.to_numeric(p.get("generation_boost",0.0),errors="coerce").fillna(0).clip(-3,3).to_numpy(float)
    qbmask=pos=="QB"; qbmask &= p.auto_qb_eligible.fillna(False).to_numpy(bool) if "auto_qb_eligible" in p.columns else qbmask
    pools={k:np.where(qbmask if k=="QB" else pos==k)[0] for k in ["QB","RB","WR","TE","DST"]}; flex=np.where(np.isin(pos,["RB","WR","TE"]))[0]
    if any(len(v)==0 for v in pools.values()):return []
    profiles=[
        ("Market",.30,3.10,.18,np.array([.16,.30,.10,.36,.08])),
        ("Balanced",.27,2.55,.28,np.array([.16,.28,.12,.34,.10])),
        ("Leverage",.20,1.85,.52,np.array([.18,.24,.14,.32,.12])),
        ("Correlated",.23,2.35,.34,np.array([.08,.24,.10,.42,.16])),
    ]
    profile_probs=np.array([x[1] for x in profiles],dtype=float); profile_probs/=profile_probs.sum()
    stack_shapes=[(1,0),(1,1),(2,0),(2,1),(2,2)]
    # Static profile weights: only the mild exposure crowding factor changes during generation.
    profile_weights=[]
    for profile,_,market_power,_,_ in profiles:
        base=np.power(.08+market,market_power)*np.clip(usage,.35,2.25)*np.clip(auto,.18,1.15)*np.exp(.34*gen_boost)
        if profile=="Leverage": base*=np.power(np.clip(1.20-market,.20,1.20),.35)
        elif profile=="Correlated": base*=np.clip(.70+.55*auto,.25,1.25)
        profile_weights.append(np.clip(base,1e-10,None))
    # Pre-cache correlation pools per QB so they are not rebuilt on every attempt.
    qb_cache={}
    for q in pools["QB"]:
        qb_cache[int(q)]=(
            np.where((team==team[q])&np.isin(pos,["WR","TE"]))[0],
            np.where((game==game[q])&(team!=team[q])&np.isin(pos,["RB","WR","TE"]))[0],
        )
    seen=[]; keys=set(); attempts=0; target=max(12000,n_lineups*80); player_counts=np.zeros(len(p),dtype=float)
    while len(seen)<n_lineups and attempts<target:
        attempts+=1
        profile_i=int(rng.choice(len(profiles),p=profile_probs)); profile,_,_,crowd_strength,shape_probs=profiles[profile_i]
        w=profile_weights[profile_i].copy()
        if seen:
            exposure=player_counts/len(seen)
            w*=np.exp(-crowd_strength*np.clip(exposure-.18,0,None)*4.0)
        qbids=pools["QB"]; qweights=w[qbids]; qsum=qweights.sum()
        if qsum<=0:continue
        qb=int(rng.choice(qbids,p=qweights/qsum))
        nmates,nbring=stack_shapes[int(rng.choice(5,p=shape_probs/shape_probs.sum()))]
        mates,opp=qb_cache[qb]
        if len(mates)<nmates or len(opp)<nbring:continue
        chosen=[qb]
        if nmates:
            mw=w[mates]; chosen+=list(map(int,rng.choice(mates,nmates,replace=False,p=mw/mw.sum())))
        if nbring:
            avail=opp[~np.isin(opp,chosen)]
            if len(avail)<nbring:continue
            ow=w[avail]; chosen+=list(map(int,rng.choice(avail,nbring,replace=False,p=ow/ow.sum())))
        # Fill position minimums, but stop at eight players so FLEX becomes a direct salary solve.
        failed=False
        for k,minimum in [("RB",2),("WR",3),("TE",1),("DST",1)]:
            have=sum(pos[i]==k for i in chosen); need=max(0,minimum-have)
            if len(chosen)+need>8: failed=True; break
            ids=pools[k][~np.isin(pools[k],chosen)]
            if len(ids)<need: failed=True; break
            if need:
                pw=w[ids]; chosen+=list(map(int,rng.choice(ids,need,replace=False,p=pw/pw.sum())))
        if failed or len(chosen)>8:continue
        # If stacking already supplied extra FLEX-eligible players, fill only until eight.
        while len(chosen)<8:
            ids=flex[~np.isin(flex,chosen)]
            if not len(ids):break
            # Leave enough salary for a legal final FLEX rather than blindly spending.
            partial=int(sal[np.asarray(chosen,dtype=int)].sum())
            max_flex_salary=salary_cap-partial
            ids=ids[sal[ids]<=max_flex_salary]
            if not len(ids):break
            fw=w[ids]; chosen.append(int(rng.choice(ids,p=fw/fw.sum())))
        if len(chosen)!=8:continue
        partial=int(sal[np.asarray(chosen,dtype=int)].sum())
        lo=min_salary-partial; hi=salary_cap-partial
        ids=flex[(sal[flex]>=lo)&(sal[flex]<=hi)&(~np.isin(flex,chosen))]
        if not len(ids):continue
        # Prevent final FLEX from creating the DST-vs-multiple-offense conflict.
        dst=[i for i in chosen if pos[i]=="DST"]
        if dst:
            d=dst[0]
            current_opp=sum((game[i]==game[d]) and (team[i]!=team[d]) and pos[i]!="DST" for i in chosen)
            if current_opp>=1:
                ids=ids[~((game[ids]==game[d])&(team[ids]!=team[d]))]
                if not len(ids):continue
        fw=w[ids]; final=int(rng.choice(ids,p=fw/fw.sum())); lineup=chosen+[final]
        key=tuple(sorted(lineup))
        if key in keys:continue
        arr=np.asarray(lineup,dtype=int)
        # Cheap array-level roster validation; construction already guarantees salary and minimums.
        counts={k:int(np.sum(pos[arr]==k)) for k in ["QB","RB","WR","TE","DST"]}
        if not(counts["QB"]==1 and counts["RB"]>=2 and counts["WR"]>=3 and counts["TE"]>=1 and counts["DST"]==1):continue
        if dst:
            d=dst[0]; opposing=sum((game[i]==game[d]) and (team[i]!=team[d]) and pos[i]!="DST" for i in lineup)
            if opposing>=2:continue
        keys.add(key); seen.append(lineup); player_counts[arr]+=1.0
    # Safety fallback: if an unusually constrained slate cannot fill, use the prior validator-style
    # search for the remainder rather than silently returning a short pool.
    if len(seen)<n_lineups:
        extra_target=max(30000,(n_lineups-len(seen))*240)
        fallback_attempts=0
        while len(seen)<n_lineups and fallback_attempts<extra_target:
            fallback_attempts+=1
            profile_i=int(rng.choice(len(profiles),p=profile_probs)); _,_,_,crowd_strength,shape_probs=profiles[profile_i]
            w=profile_weights[profile_i].copy()
            if seen:
                exposure=player_counts/len(seen); w*=np.exp(-crowd_strength*np.clip(exposure-.18,0,None)*4.0)
            qbids=pools["QB"]; qw=w[qbids]/w[qbids].sum(); qb=int(rng.choice(qbids,p=qw))
            nmates,nbring=stack_shapes[int(rng.choice(5,p=shape_probs/shape_probs.sum()))]; mates,opp=qb_cache[qb]
            if len(mates)<nmates or len(opp)<nbring:continue
            chosen=[qb]
            if nmates:
                mw=w[mates]; chosen+=list(map(int,rng.choice(mates,nmates,replace=False,p=mw/mw.sum())))
            if nbring:
                avail=opp[~np.isin(opp,chosen)];
                if len(avail)<nbring:continue
                ow=w[avail]; chosen+=list(map(int,rng.choice(avail,nbring,replace=False,p=ow/ow.sum())))
            for k,minimum in [("RB",2),("WR",3),("TE",1),("DST",1)]:
                have=sum(pos[i]==k for i in chosen); need=max(0,minimum-have); ids0=pools[k][~np.isin(pools[k],chosen)]
                if len(ids0)<need: chosen=[]; break
                if need:
                    pw=w[ids0]; chosen+=list(map(int,rng.choice(ids0,need,replace=False,p=pw/pw.sum())))
            if not chosen:continue
            while len(chosen)<9:
                ids0=flex[~np.isin(flex,chosen)]
                if not len(ids0):break
                fw=w[ids0]; chosen.append(int(rng.choice(ids0,p=fw/fw.sum())))
            if len(chosen)!=9:continue
            arr=np.asarray(chosen,dtype=int); total=int(sal[arr].sum()); key=tuple(sorted(chosen))
            if total<min_salary or total>salary_cap or key in keys or not _valid_lineup(chosen,p,min_salary,max_salary=salary_cap,site=site):continue
            dst_ids=[i for i in chosen if pos[i]=="DST"]
            if dst_ids:
                d=dst_ids[0]; opposing=sum((game[i]==game[d]) and (team[i]!=team[d]) and pos[i]!="DST" for i in chosen)
                if opposing>=2:continue
            keys.add(key); seen.append(chosen); player_counts[arr]+=1.0
    return seen


def candidate_pool_diagnostics(players,lineups):
    """Compact diagnostics for whether the candidate pool is actually diversified."""
    if players is None or players.empty or not lineups:
        return {}
    p=players.reset_index(drop=True); n=len(lineups); counts=np.zeros(len(p),dtype=int); qb_counts={}; stack_counts={}; flex_counts={}; salaries=[]; pair_counts={}
    for lu in lineups:
        ids=list(map(int,lu)); salaries.append(int(p.iloc[ids].Salary.sum()))
        for i in ids: counts[i]+=1
        r=p.iloc[ids]; q=r[r.Position.eq("QB")]
        if not q.empty: qb_counts[str(q.iloc[0].Name)]=qb_counts.get(str(q.iloc[0].Name),0)+1
        st=_stack_label(r); stack_counts[st]=stack_counts.get(st,0)+1
        fp=_flex_pos(r); flex_counts[fp]=flex_counts.get(fp,0)+1
        sid=sorted(ids)
        for a in range(len(sid)):
            for b in range(a+1,len(sid)):
                pair=(sid[a],sid[b]); pair_counts[pair]=pair_counts.get(pair,0)+1
    exp=100*counts/max(1,n); top5=np.sort(exp)[-5:] if len(exp)>=5 else np.sort(exp)
    return {
        "candidate_lineups":n,
        "salary_min":int(min(salaries)),"salary_avg":round(float(np.mean(salaries)),1),"salary_max":int(max(salaries)),
        "unique_qbs":len(qb_counts),"max_qb_exposure_pct":round(100*max(qb_counts.values())/n,1) if qb_counts else 0.0,
        "max_player_exposure_pct":round(float(exp.max()),1) if len(exp) else 0.0,"top5_player_exposure_avg_pct":round(float(np.mean(top5)),1) if len(top5) else 0.0,
        "max_pair_exposure_pct":round(100*max(pair_counts.values())/n,1) if pair_counts else 0.0,
        "stack_mix":{k:round(100*v/n,1) for k,v in sorted(stack_counts.items())},
        "flex_mix":{k:round(100*v/n,1) for k,v in sorted(flex_counts.items())},
    }

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
