from pathlib import Path
p=Path('nuke_sim.py')
s=p.read_text(encoding='utf-8')
start=s.index('def generate_lineups(')
end=s.index('\n\ndef candidate_pool_diagnostics',start)
new=r'''def generate_lineups(players,n_lineups=600,min_salary=49400,seed=26):
    """Candidate Engine V3: salary-aware tournament construction.

    Builds the first eight roster spots under the existing stack/profile rules, then solves
    the final FLEX directly inside the legal salary window instead of repeatedly creating
    full lineups that must be rejected afterward.
    """
    rng=np.random.default_rng(seed); p=players.reset_index(drop=True)
    if p.empty:return []
    min_salary=max(49400,int(min_salary)); n_lineups=int(n_lineups)
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
            max_flex_salary=50000-partial
            ids=ids[sal[ids]<=max_flex_salary]
            if not len(ids):break
            fw=w[ids]; chosen.append(int(rng.choice(ids,p=fw/fw.sum())))
        if len(chosen)!=8:continue
        partial=int(sal[np.asarray(chosen,dtype=int)].sum())
        lo=min_salary-partial; hi=50000-partial
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
            if total<min_salary or total>50000 or key in keys or not _valid_lineup(chosen,p,min_salary):continue
            dst_ids=[i for i in chosen if pos[i]=="DST"]
            if dst_ids:
                d=dst_ids[0]; opposing=sum((game[i]==game[d]) and (team[i]!=team[d]) and pos[i]!="DST" for i in chosen)
                if opposing>=2:continue
            keys.add(key); seen.append(chosen); player_counts[arr]+=1.0
    return seen
'''
p.write_text(s[:start]+new+s[end:],encoding='utf-8')
