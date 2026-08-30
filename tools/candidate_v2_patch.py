from pathlib import Path

p=Path('nuke_sim.py')
s=p.read_text()
start=s.index('def generate_lineups(')
end=s.index('\ndef _stack_label', start)
new=r'''CANDIDATE_ENGINE_VERSION = "Candidate Engine V2"


def generate_lineups(players,n_lineups=600,min_salary=49400,seed=26):
    """Generate a diverse tournament candidate pool without paid projections.

    Candidate Engine V2 intentionally samples several construction personalities instead
    of repeatedly drawing from one chalk-heavy distribution. It also applies a light
    anti-crowding penalty as the pool fills so a few players/teams cannot dominate every
    candidate before the contest simulator ever gets a chance to evaluate alternatives.
    """
    rng=np.random.default_rng(seed); p=players.reset_index(drop=True)
    if p.empty:return []
    pos=p.Position.astype(str).to_numpy(); team=p.Team.astype(str).to_numpy(); game=p.Game.astype(str).to_numpy(); sal=p.Salary.to_numpy(int)
    market=p.market_score.to_numpy(float); usage=p.usage_multiplier.to_numpy(float); auto=p.auto_role_multiplier.to_numpy(float)
    gen_boost=pd.to_numeric(p.get("generation_boost",0.0),errors="coerce").fillna(0).clip(-3,3).to_numpy(float)
    base=np.clip(.08+market,1e-5,None)*np.clip(usage,.35,2.25)*np.clip(auto,.18,1.15)*np.exp(.34*gen_boost)
    qbmask=pos=="QB"; qbmask &= p.auto_qb_eligible.fillna(False).to_numpy(bool) if "auto_qb_eligible" in p.columns else qbmask
    pools={k:np.where(qbmask if k=="QB" else pos==k)[0] for k in ["QB","RB","WR","TE","DST"]}; flex=np.where(np.isin(pos,["RB","WR","TE"]))[0]
    if any(len(v)==0 for v in pools.values()):return []

    # Different tournament construction personalities. None uses external projections.
    profiles=[
        {"name":"MARKET","share":.30,"power":3.10,"cheap":0.00,"crowd":.18,"salary_lo":min_salary,"salary_hi":50000,"shapes":[.14,.28,.10,.38,.10]},
        {"name":"BALANCED","share":.27,"power":2.45,"cheap":0.08,"crowd":.32,"salary_lo":max(48500,min_salary-500),"salary_hi":50000,"shapes":[.16,.30,.12,.34,.08]},
        {"name":"LEVERAGE","share":.21,"power":1.75,"cheap":0.22,"crowd":.48,"salary_lo":max(48000,min_salary-900),"salary_hi":49900,"shapes":[.18,.28,.14,.32,.08]},
        {"name":"CORRELATED","share":.22,"power":2.35,"cheap":0.10,"crowd":.36,"salary_lo":max(48700,min_salary-400),"salary_hi":50000,"shapes":[.06,.25,.09,.44,.16]},
    ]
    profile_probs=np.array([x["share"] for x in profiles],dtype=float); profile_probs/=profile_probs.sum()
    stack_shapes=[(1,0),(1,1),(2,0),(2,1),(2,2)]
    seen=[]; keys=set(); attempts=0; target=max(55000,int(n_lineups)*300); counts=np.zeros(len(p),dtype=float)

    def weights_for(ids,prof):
        ids=np.asarray(ids,dtype=int)
        if not len(ids):return np.array([],dtype=float)
        # Cheaper-player term creates controlled leverage paths; crowd term diversifies
        # candidate inclusion frequency while preserving salary/role/boost signal.
        salary_rel=np.clip((9000.0-sal[ids])/6500.0,0,1)
        crowd=np.power(1.0+counts[ids],-float(prof["crowd"]))
        vals=np.power(np.clip(base[ids],1e-7,None),float(prof["power"])) * np.exp(float(prof["cheap"])*salary_rel) * crowd
        vals=np.clip(vals,1e-12,None); return vals/vals.sum()

    while len(seen)<int(n_lineups) and attempts<target:
        attempts+=1; prof=profiles[int(rng.choice(len(profiles),p=profile_probs))]
        qbids=pools["QB"]; qb=int(rng.choice(qbids,p=weights_for(qbids,prof)))
        shape_probs=np.asarray(prof["shapes"],dtype=float); shape_probs/=shape_probs.sum(); nmates,nbring=stack_shapes[int(rng.choice(len(stack_shapes),p=shape_probs))]
        mates=np.where((team==team[qb])&np.isin(pos,["WR","TE"]))[0]
        opp=np.where((game==game[qb])&(team!=team[qb])&np.isin(pos,["RB","WR","TE"]))[0]
        if len(mates)<nmates or len(opp)<nbring:continue
        chosen=[qb]
        if nmates: chosen+=list(map(int,rng.choice(mates,nmates,replace=False,p=weights_for(mates,prof))))
        if nbring:
            avail=opp[~np.isin(opp,chosen)]
            if len(avail)<nbring:continue
            chosen+=list(map(int,rng.choice(avail,nbring,replace=False,p=weights_for(avail,prof))))
        for k,minimum in [("RB",2),("WR",3),("TE",1),("DST",1)]:
            have=sum(pos[i]==k for i in chosen); need=max(0,minimum-have); ids=pools[k][~np.isin(pools[k],chosen)]
            if len(ids)<need: chosen=[]; break
            if need: chosen+=list(map(int,rng.choice(ids,need,replace=False,p=weights_for(ids,prof))))
        if not chosen:continue
        while len(chosen)<9:
            ids=flex[~np.isin(flex,chosen)]
            if not len(ids):break
            chosen.append(int(rng.choice(ids,p=weights_for(ids,prof))))
        if len(chosen)!=9:continue
        arr=np.asarray(chosen,dtype=int); total=int(sal[arr].sum()); key=tuple(sorted(chosen))
        if total<int(prof["salary_lo"]) or total>int(prof["salary_hi"]):continue
        if total<min_salary or total>50000 or key in keys or not _valid_lineup(chosen,p,min_salary):continue

        # Tournament-quality correlation guard: do not roster a DST against 2+ offensive
        # players from its opponent. One opposing offensive player is allowed for flexibility.
        dst_ids=[i for i in chosen if pos[i]=="DST"]
        if dst_ids:
            d=dst_ids[0]; opposing_off=sum((game[i]==game[d]) and (team[i]!=team[d]) and (pos[i]!="DST") for i in chosen)
            if opposing_off>=2:continue

        keys.add(key); seen.append(chosen); counts[arr]+=1.0
    return seen
'''
p.write_text(s[:start]+new+s[end:])
