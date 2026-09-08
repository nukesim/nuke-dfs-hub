from pathlib import Path

# ---- Engine: force locked players into every generated candidate ----
p=Path('nuke_sim.py')
s=p.read_text(encoding='utf-8')
s=s.replace(
    'def generate_lineups(players,n_lineups=600,min_salary=None,seed=26,site="DK",flex_position=None):',
    'def generate_lineups(players,n_lineups=600,min_salary=None,seed=26,site="DK",flex_position=None,locked_indices=None):',
    1,
)
old='''    flex_position=str(flex_position or "ANY").upper().strip()\n    if flex_position not in {"ANY","RB","WR","TE"}: flex_position="ANY"\n    pos=p.Position.astype(str).to_numpy(); team=p.Team.astype(str).to_numpy(); game=p.Game.astype(str).to_numpy(); sal=p.Salary.to_numpy(int)\n'''
new='''    flex_position=str(flex_position or "ANY").upper().strip()\n    if flex_position not in {"ANY","RB","WR","TE"}: flex_position="ANY"\n    locked=[]\n    for i in (locked_indices or []):\n        try: i=int(i)\n        except Exception: continue\n        if 0<=i<len(p) and i not in locked: locked.append(i)\n    pos=p.Position.astype(str).to_numpy(); team=p.Team.astype(str).to_numpy(); game=p.Game.astype(str).to_numpy(); sal=p.Salary.to_numpy(int)\n    if len(locked)>9:return []\n    if locked:\n        lc={k:int(np.sum(pos[np.asarray(locked,dtype=int)]==k)) for k in ["QB","RB","WR","TE","DST"]}\n        if lc.get("QB",0)>1 or lc.get("DST",0)>1 or lc.get("RB",0)>3 or lc.get("WR",0)>4 or lc.get("TE",0)>2:return []\n        if int(sal[np.asarray(locked,dtype=int)].sum())>salary_cap:return []\n'''
if old not in s: raise SystemExit('engine setup block not found')
s=s.replace(old,new,1)
old='''        qbids=pools["QB"]; qweights=w[qbids]; qsum=qweights.sum()\n        if qsum<=0:continue\n        qb=int(rng.choice(qbids,p=qweights/qsum))\n        nmates,nbring=stack_shapes[int(rng.choice(5,p=shape_probs/shape_probs.sum()))]\n        mates,opp=qb_cache[qb]\n        if len(mates)<nmates or len(opp)<nbring:continue\n        chosen=[qb]\n        if nmates:\n            mw=w[mates]; chosen+=list(map(int,rng.choice(mates,nmates,replace=False,p=mw/mw.sum())))\n        if nbring:\n            avail=opp[~np.isin(opp,chosen)]\n            if len(avail)<nbring:continue\n            ow=w[avail]; chosen+=list(map(int,rng.choice(avail,nbring,replace=False,p=ow/ow.sum())))\n'''
new='''        chosen=list(locked)\n        locked_qbs=[i for i in chosen if pos[i]=="QB"]\n        if locked_qbs:\n            qb=int(locked_qbs[0])\n            if not bool(qbmask[qb]): continue\n        else:\n            qbids=pools["QB"]; qweights=w[qbids]; qsum=qweights.sum()\n            if qsum<=0:continue\n            qb=int(rng.choice(qbids,p=qweights/qsum)); chosen.append(qb)\n        nmates,nbring=stack_shapes[int(rng.choice(5,p=shape_probs/shape_probs.sum()))]\n        mates,opp=qb_cache[qb]\n        have_mates=sum((team[i]==team[qb]) and (pos[i] in {"WR","TE"}) for i in chosen)\n        have_bring=sum((game[i]==game[qb]) and (team[i]!=team[qb]) and (pos[i] in {"RB","WR","TE"}) for i in chosen)\n        need_mates=max(0,nmates-have_mates); need_bring=max(0,nbring-have_bring)\n        avail_mates=mates[~np.isin(mates,chosen)]\n        if len(avail_mates)<need_mates:continue\n        if need_mates:\n            mw=w[avail_mates]; chosen+=list(map(int,rng.choice(avail_mates,need_mates,replace=False,p=mw/mw.sum())))\n        avail=opp[~np.isin(opp,chosen)]\n        if len(avail)<need_bring:continue\n        if need_bring:\n            ow=w[avail]; chosen+=list(map(int,rng.choice(avail,need_bring,replace=False,p=ow/ow.sum())))\n'''
if old not in s: raise SystemExit('engine QB/stack block not found')
s=s.replace(old,new,1)
# Accept an already complete 9-player locked/stacked roster before final FLEX solve.
old='''        if failed or len(chosen)>8:continue\n        # If stacking already supplied extra FLEX-eligible players, fill only until eight.\n'''
new='''        if failed or len(chosen)>9:continue\n        if len(chosen)==9:\n            arr=np.asarray(chosen,dtype=int); key=tuple(sorted(chosen)); total=int(sal[arr].sum())\n            if total<min_salary or total>salary_cap or key in keys or not _valid_lineup(chosen,p,min_salary,max_salary=salary_cap,site=site):continue\n            if flex_position!="ANY":\n                counts={k:int(np.sum(pos[arr]==k)) for k in ["RB","WR","TE"]}\n                if counts.get(flex_position,0)!={"RB":3,"WR":4,"TE":2}[flex_position]:continue\n            dst_ids=[i for i in chosen if pos[i]=="DST"]\n            if dst_ids:\n                d=dst_ids[0]; opposing=sum((game[i]==game[d]) and (team[i]!=team[d]) and pos[i]!="DST" for i in chosen)\n                if opposing>=2:continue\n            keys.add(key); seen.append(chosen); player_counts[arr]+=1.0; continue\n        # If stacking already supplied extra FLEX-eligible players, fill only until eight.\n'''
if old not in s: raise SystemExit('engine nine-player block not found')
s=s.replace(old,new,1)
p.write_text(s,encoding='utf-8')

# ---- UI/state: Lock checkbox in game pool, dashboard, and generation call ----
p=Path('pages/6_SIM.py')
s=p.read_text(encoding='utf-8')
s=s.replace(
    'pool_state.setdefault(key,{"include":not auto_exclude,"role":"AUTO","usage":1.0})',
    'pool_state.setdefault(key,{"include":not auto_exclude,"role":"AUTO","usage":1.0,"lock":False})',
    1,
)
s=s.replace(
    'cfg=updated_state.get(key,{"include":True,"role":"AUTO","usage":1.0})\n                            rows.append({"_row":int(idx),"_key":key,"Include":bool(cfg.get("include",True)),"Pos":row.Position,"Player":row.Name,',
    'cfg=updated_state.get(key,{"include":True,"role":"AUTO","usage":1.0,"lock":False})\n                            rows.append({"_row":int(idx),"_key":key,"Include":bool(cfg.get("include",True)),"Lock":bool(cfg.get("lock",False)),"Pos":row.Position,"Player":row.Name,',
    1,
)
s=s.replace(
    'visible_cols=["Include","Pos","Player"]',
    'visible_cols=["Include","Lock","Pos","Player"]',
    1,
)
s=s.replace(
    '"Include":st.column_config.CheckboxColumn("In",width="small",help="Include this player in the active SIM pool."),',
    '"Include":st.column_config.CheckboxColumn("In",width="small",help="Include this player in the active SIM pool."),\n                                "Lock":st.column_config.CheckboxColumn("🔒",width="small",help="Force this player into every generated NUKE SIM candidate lineup. Use for confirmed value starters or other must-play stands."),',
    1,
)
old='''                    include=bool(erow["Include"])\n                    if action=="✅ Include all": include=True\n                    elif action=="🚫 Exclude all": include=False\n                    if game_action=="✅ Include entire game": include=True\n                    elif game_action=="🚫 Exclude entire game": include=False\n                    updated_state[key]={"include":include,"role":str(erow["Role"]),"usage":float(erow["Usage x"])}\n'''
new='''                    include=bool(erow["Include"])\n                    lock=bool(erow.get("Lock",False))\n                    if action=="✅ Include all": include=True\n                    elif action=="🚫 Exclude all": include=False\n                    if game_action=="✅ Include entire game": include=True\n                    elif game_action=="🚫 Exclude entire game": include=False\n                    if lock: include=True\n                    updated_state[key]={"include":include,"role":str(erow["Role"]),"usage":float(erow["Usage x"]),"lock":lock}\n'''
if old not in s: raise SystemExit('apply state block not found')
s=s.replace(old,new,1)
# Current Player Pool summary gets a Locked marker.
s=s.replace(
    'pcfg=updated_state.get(key,{"include":True,"role":"AUTO","usage":1.0})',
    'pcfg=updated_state.get(key,{"include":True,"role":"AUTO","usage":1.0,"lock":False})',
    1,
)
s=s.replace(
    '"Usage":float(pcfg.get("usage",1.0)),\n        })',
    '"Usage":float(pcfg.get("usage",1.0)),\n            "Locked":"🔒" if bool(pcfg.get("lock",False)) else "",\n        })',
    1,
)
s=s.replace(
    'st.dataframe(view[["Player","Team","Salary","Role","Usage"]],use_container_width=True,hide_index=True,height=min(520,70+35*len(view)))',
    'st.dataframe(view[["Locked","Player","Team","Salary","Role","Usage"]],use_container_width=True,hide_index=True,height=min(520,70+35*len(view)))',
    1,
)
# Active player frame carries the lock through reindexing.
s=s.replace(
    'cfg=updated_state.get(key,{"include":True,"role":"AUTO","usage":1.0})\n    if cfg.get("include",True):\n        r=row.copy()\n        r["role_override"]=str(cfg.get("role","AUTO")).upper()\n        r["usage_multiplier"]=float(cfg.get("usage",1.0))',
    'cfg=updated_state.get(key,{"include":True,"role":"AUTO","usage":1.0,"lock":False})\n    if cfg.get("include",True):\n        r=row.copy()\n        r["role_override"]=str(cfg.get("role","AUTO")).upper()\n        r["usage_multiplier"]=float(cfg.get("usage",1.0))\n        r["sim_lock"]=bool(cfg.get("lock",False))',
    1,
)
# Show lock status and validate before running.
s=s.replace(
    'if not players.empty:\n    st.caption(f"Active pool: {len(players):,} players")\n\nif st.button("☢️ RUN NUKE SIM",type="primary",use_container_width=True):',
    'if not players.empty:\n    locked_count=int(players.get("sim_lock",pd.Series(False,index=players.index)).fillna(False).astype(bool).sum())\n    st.caption(f"Active pool: {len(players):,} players" + (f" · 🔒 {locked_count} locked" if locked_count else ""))\n\nif st.button("☢️ RUN NUKE SIM",type="primary",use_container_width=True):',
    1,
)
old='''    if len(players)<9:\n        st.error("Not enough active players.")\n        st.stop()\n    with st.status("NUKE SIM is running...",expanded=True) as status:\n'''
new='''    if len(players)<9:\n        st.error("Not enough active players.")\n        st.stop()\n    locked_indices=np.where(players.get("sim_lock",pd.Series(False,index=players.index)).fillna(False).astype(bool).to_numpy())[0].tolist()\n    if locked_indices:\n        locked_names=players.iloc[locked_indices]["Name"].astype(str).tolist()\n        st.info("🔒 Locked into every candidate: "+", ".join(locked_names))\n        lc=players.iloc[locked_indices]["Position"].value_counts().to_dict()\n        if len(locked_indices)>9 or lc.get("QB",0)>1 or lc.get("DST",0)>1 or lc.get("RB",0)>3 or lc.get("WR",0)>4 or lc.get("TE",0)>2:\n            st.error("Locked-player combination cannot fit a legal lineup. Reduce the number of locks at one or more positions.")\n            st.stop()\n    with st.status("NUKE SIM is running...",expanded=True) as status:\n'''
if old not in s: raise SystemExit('run validation block not found')
s=s.replace(old,new,1)
s=s.replace(
    'lineups=generate_lineups(players,generation_target,int(min_salary),int(seed),site=site)',
    'lineups=generate_lineups(players,generation_target,int(min_salary),int(seed),site=site,locked_indices=locked_indices)',
    1,
)
p.write_text(s,encoding='utf-8')
