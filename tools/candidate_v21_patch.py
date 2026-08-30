from pathlib import Path

p=Path('nuke_sim.py')
s=p.read_text()
start=s.index('def generate_lineups(')
end=s.index('def _stack_label(', start)

new=r'''def generate_lineups(players,n_lineups=600,min_salary=49400,seed=26):
    """Candidate Engine V2.1: diversified tournament lineup generation.

    Hard salary rule: every accepted lineup must be between `min_salary` and $50,000.
    With the NUKE default this means $49,400-$50,000 only.
    """
    rng=np.random.default_rng(seed); p=players.reset_index(drop=True)
    if p.empty:return []
    min_salary=max(49400,int(min_salary))
    pos=p.Position.astype(str).to_numpy(); team=p.Team.astype(str).to_numpy(); game=p.Game.astype(str).to_numpy(); sal=p.Salary.to_numpy(int)
    market=p.market_score.to_numpy(float); usage=p.usage_multiplier.to_numpy(float); auto=p.auto_role_multiplier.to_numpy(float)
    gen_boost=pd.to_numeric(p.get("generation_boost",0.0),errors="coerce").fillna(0).clip(-3,3).to_numpy(float)
    qbmask=pos=="QB"; qbmask &= p.auto_qb_eligible.fillna(False).to_numpy(bool) if "auto_qb_eligible" in p.columns else qbmask
    pools={k:np.where(qbmask if k=="QB" else pos==k)[0] for k in ["QB","RB","WR","TE","DST"]}; flex=np.where(np.isin(pos,["RB","WR","TE"]))[0]
    if any(len(v)==0 for v in pools.values()):return []

    # Distinct tournament construction profiles. All obey the same $49.4K+ floor.
    profiles=[
        ("Market",.30,3.10,.18,np.array([.16,.30,.10,.36,.08])),
        ("Balanced",.27,2.55,.28,np.array([.16,.28,.12,.34,.10])),
        ("Leverage",.20,1.85,.52,np.array([.18,.24,.14,.32,.12])),
        ("Correlated",.23,2.35,.34,np.array([.08,.24,.10,.42,.16])),
    ]
    profile_probs=np.array([x[1] for x in profiles],dtype=float); profile_probs/=profile_probs.sum()
    stack_shapes=[(1,0),(1,1),(2,0),(2,1),(2,2)]

    seen=[]; keys=set(); attempts=0; target=max(60000,int(n_lineups)*320); player_counts=np.zeros(len(p),dtype=float)
    while len(seen)<int(n_lineups) and attempts<target:
        attempts+=1
        profile_i=int(rng.choice(len(profiles),p=profile_probs)); profile,_,market_power,crowd_strength,shape_probs=profiles[profile_i]
        base=np.power(.08+market,market_power)*np.clip(usage,.35,2.25)*np.clip(auto,.18,1.15)*np.exp(.34*gen_boost)
        if len(seen):
            exposure=player_counts/max(1,len(seen)); crowd=np.exp(-crowd_strength*np.clip(exposure-.18,0,None)*4.0)
            base*=crowd
        if profile=="Leverage":
            base*=np.power(np.clip(1.20-market,.20,1.20),.35)
        elif profile=="Correlated":
            base*=np.clip(.70+.55*auto,.25,1.25)
        w=np.clip(base,1e-10,None)

        qbids=pools["QB"]; qw=w[qbids]/w[qbids].sum(); qb=int(rng.choice(qbids,p=qw))
        nmates,nbring=stack_shapes[int(rng.choice(len(stack_shapes),p=shape_probs/shape_probs.sum()))]
        mates=np.where((team==team[qb])&np.isin(pos,["WR","TE"]))[0]
        opp=np.where((game==game[qb])&(team!=team[qb])&np.isin(pos,["RB","WR","TE"]))[0]
        if len(mates)<nmates or len(opp)<nbring:continue
        chosen=[qb]
        if nmates:
            mw=w[mates]/w[mates].sum(); chosen+=list(map(int,rng.choice(mates,nmates,replace=False,p=mw)))
        if nbring:
            avail=opp[~np.isin(opp,chosen)]
            if len(avail)<nbring:continue
            ow=w[avail]/w[avail].sum(); chosen+=list(map(int,rng.choice(avail,nbring,replace=False,p=ow)))

        for k,minimum in [("RB",2),("WR",3),("TE",1),("DST",1)]:
            have=sum(pos[i]==k for i in chosen); need=max(0,minimum-have); ids=pools[k][~np.isin(pools[k],chosen)]
            if len(ids)<need: chosen=[]; break
            if need:
                pw=w[ids]/w[ids].sum(); chosen+=list(map(int,rng.choice(ids,need,replace=False,p=pw)))
        if not chosen:continue
        while len(chosen)<9:
            ids=flex[~np.isin(flex,chosen)]
            if not len(ids):break
            fw=w[ids]/w[ids].sum(); chosen.append(int(rng.choice(ids,p=fw)))
        if len(chosen)!=9:continue

        arr=np.asarray(chosen,dtype=int); total=int(sal[arr].sum()); key=tuple(sorted(chosen))
        if total<min_salary or total>50000 or key in keys or not _valid_lineup(chosen,p,min_salary):continue

        # Do not allow a DST to directly fight against two or more opposing offensive players.
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

'''
p.write_text(s[:start]+new+s[end:])
