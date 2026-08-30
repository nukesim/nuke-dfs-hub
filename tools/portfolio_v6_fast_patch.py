from pathlib import Path

# --- Portfolio V6 ---
p=Path('nuke_portfolio.py')
s=p.read_text(encoding='utf-8')
s=s.replace('PORTFOLIO_ENGINE_VERSION = "Portfolio Engine V5.2"','PORTFOLIO_ENGINE_VERSION = "Portfolio Engine V6"')
start=s.index('def build_portfolio(')
end=s.index('\n\ndef portfolio_summary', start)
new=r'''def build_portfolio(
    contest_results,
    size=20,
    max_overlap=7,
    path_balance=1.25,
    leverage_weight=0.0,
    max_player_exposure=0.45,
    max_qb_exposure=0.30,
    player_preferences=None,
    players=None,
    max_team_exposure=1.0,
    max_game_exposure=1.0,
):
    """Portfolio Engine V6: same portfolio controls, faster execution.

    V6 preserves the player/QB/team/game caps, max-overlap rule, path diversification,
    soft 45% path concentration line, and repeated pair/3-player-core penalties. The
    speedup comes from precomputed overlap/core structures and array-backed exposure
    accounting rather than recalculating lineup relationships on every selection.
    """
    if contest_results is None or contest_results.empty:
        return pd.DataFrame()

    x=contest_results.reset_index(drop=True).copy(); n=len(x)
    size=max(1,min(int(size),n)); max_overlap=int(np.clip(max_overlap,0,8))
    max_player_exposure=float(np.clip(max_player_exposure,.01,1.0)); max_qb_exposure=float(np.clip(max_qb_exposure,.01,1.0))
    max_team_exposure=float(np.clip(max_team_exposure,.01,1.0)); max_game_exposure=float(np.clip(max_game_exposure,.01,1.0))
    global_max_player_count=max(1,int(np.floor(size*max_player_exposure+1e-9)))
    max_qb_count=max(1,int(np.floor(size*max_qb_exposure+1e-9))); max_team_count=max(1,int(np.floor(size*max_team_exposure+1e-9))); max_game_count=max(1,int(np.floor(size*max_game_exposure+1e-9)))
    prefs=_normalize_player_preferences(player_preferences,size,max_player_exposure)

    def num(col,default=0):
        return pd.to_numeric(x.get(col,default),errors="coerce").fillna(default).to_numpy(float)
    base=.75*_z(num("Sim ROI %"))+.90*_z(num("1st %"))+.75*_z(num("Top 0.1%"))+.45*_z(num("Top 1%"))+.55*_z(num("Ceiling 95"))+.30*_z(num("NUKE Score"))+.15*_z(num("Path Score",50))
    path_arr=x.get("Strongest Path",pd.Series(["UNKNOWN"]*n)).fillna("UNKNOWN").astype(str).to_numpy()
    qb_arr=x.get("QB",pd.Series(["UNKNOWN"]*n)).fillna("UNKNOWN").astype(str).to_numpy()
    stack_arr=x.get("Stack",pd.Series(["UNKNOWN"]*n)).fillna("UNKNOWN").astype(str).to_numpy()
    lineup_ids=[tuple(map(int,lu)) for lu in x["_indices"]] if "_indices" in x.columns else [tuple() for _ in range(n)]
    lineup_sets=[set(lu) for lu in lineup_ids]
    lineup_pairs=[tuple(itertools.combinations(sorted(set(lu)),2)) for lu in lineup_ids]
    lineup_triples=[tuple(itertools.combinations(sorted(set(lu)),3)) for lu in lineup_ids]

    # Precompute every candidate-to-candidate overlap once (250 candidates => tiny matrix).
    overlap_matrix=np.zeros((n,n),dtype=np.int8)
    for i in range(n):
        si=lineup_sets[i]
        for j in range(i+1,n):
            ov=len(si & lineup_sets[j]); overlap_matrix[i,j]=ov; overlap_matrix[j,i]=ov

    # Fast team/game incidence from player arrays rather than repeated iloc lookups.
    if players is not None and len(players):
        pteam=players.Team.astype(str).to_numpy(); pgame=players.Game.astype(str).to_numpy()
    else:
        pteam=np.array([],dtype=str); pgame=np.array([],dtype=str)
    lineup_teams=[]; lineup_games=[]
    for lu in lineup_ids:
        lineup_teams.append(tuple(sorted({pteam[pid] for pid in lu if 0<=pid<len(pteam) and pteam[pid] and pteam[pid].lower()!="nan"})))
        lineup_games.append(tuple(sorted({pgame[pid] for pid in lu if 0<=pid<len(pgame) and pgame[pid] and pgame[pid].lower()!="nan"})))

    pref_adj=np.zeros(n,dtype=float)
    for i,lu in enumerate(lineup_ids): pref_adj[i]=sum(.42*prefs.get(pid,{}).get("boost",0.0) for pid in lu)
    support_floor=max(2,int(np.ceil(size*.015))); vals,counts=np.unique(path_arr,return_counts=True); support=dict(zip(vals,counts))
    viable_paths={p for p,c in support.items() if c>=support_floor} or set(support.keys()) or {"UNKNOWN"}; target_per_path=max(1.0,size/max(1,len(viable_paths)))

    # Array-backed player exposure counts. Dicts remain for labels whose universe is small.
    max_pid=max((max(lu) for lu in lineup_ids if lu),default=-1); player_counts=np.zeros(max_pid+1,dtype=np.int16)
    player_max=np.full(max_pid+1,global_max_player_count,dtype=np.int16)
    player_min=np.zeros(max_pid+1,dtype=np.int16)
    for pid,pref in prefs.items():
        if 0<=pid<=max_pid:
            player_max[pid]=pref.get("max_count",global_max_player_count); player_min[pid]=pref.get("min_count",0)
    path_counts={}; qb_counts={}; stack_counts={}; team_counts={}; game_counts={}; pair_counts={}; triple_counts={}; reasons={}
    selected=[]; selected_mask=np.zeros(n,dtype=bool)

    for pick in range(size):
        best_i=-1; best_score=-1e18; best_meta=None; slots_left=size-pick-1; denom=max(1,len(selected))
        selected_idx=np.asarray(selected,dtype=int) if selected else None
        for i in range(n):
            if selected_mask[i]: continue
            lu=lineup_ids[i]
            if any(pid<=max_pid and player_counts[pid]>=player_max[pid] for pid in lu): continue
            qb=qb_arr[i]
            if qb_counts.get(qb,0)>=max_qb_count: continue
            if any(team_counts.get(t,0)>=max_team_count for t in lineup_teams[i]): continue
            if any(game_counts.get(g,0)>=max_game_count for g in lineup_games[i]): continue

            if selected_idx is not None:
                ovs=overlap_matrix[i,selected_idx]; worst=int(ovs.max()); avg=float(ovs.mean())
                if worst>max_overlap: continue
            else:
                worst=0; avg=0.0

            path=path_arr[i]; stack=stack_arr[i]; current_path=path_counts.get(path,0)
            if path in viable_paths:
                sat=current_path/target_per_path
                path_adj=float(path_balance)*(.55*max(0.0,1.0-sat)-.42*max(0.0,sat-1.0)**2)
            else: path_adj=0.0
            next_share=(current_path+1)/max(1,len(selected)+1); dom_pen=0.0
            if path in viable_paths and next_share>.45:
                ex=(next_share-.45)/.10; dom_pen=float(path_balance)*(.90*ex+.50*ex**2)
            qb_share=qb_counts.get(qb,0)/denom; stack_share=stack_counts.get(stack,0)/denom
            conc=.25*max(0.0,qb_share-.20)+.10*max(0.0,stack_share-.55)
            redundancy=.10*max(0.0,avg-5.25)+.16*max(0.0,worst-6)

            prs=lineup_pairs[i]; trs=lineup_triples[i]
            max_pr=max((pair_counts.get(c,0) for c in prs),default=0); max_tr=max((triple_counts.get(c,0) for c in trs),default=0)
            pair_load=sum(max(0,pair_counts.get(c,0)-4) for c in prs); triple_load=sum(max(0,triple_counts.get(c,0)-2) for c in trs)
            core_pen=.035*pair_load+.075*triple_load+.08*max(0,max_pr-10)**1.35+.16*max(0,max_tr-6)**1.45

            min_bonus=0.0
            for pid in lu:
                if 0<=pid<=max_pid:
                    need=max(0,int(player_min[pid])-int(player_counts[pid]))
                    if need: min_bonus+=1.10+2.40*(need/max(1,slots_left+1))
            score=float(base[i]+pref_adj[i]+min_bonus+path_adj-dom_pen-conc-redundancy-core_pen)
            if score>best_score:
                best_i=i; best_score=score; best_meta=(path,qb,stack,worst,max_pr,max_tr)

        if best_i<0:
            # Same V5 behavior: relax overlap only to finish a feasible portfolio.
            feasible=[]
            for i in range(n):
                if selected_mask[i]: continue
                lu=lineup_ids[i]
                if any(pid<=max_pid and player_counts[pid]>=player_max[pid] for pid in lu): continue
                if qb_counts.get(qb_arr[i],0)>=max_qb_count: continue
                if any(team_counts.get(t,0)>=max_team_count for t in lineup_teams[i]): continue
                if any(game_counts.get(g,0)>=max_game_count for g in lineup_games[i]): continue
                feasible.append(i)
            if not feasible: break
            best_i=max(feasible,key=lambda i:base[i]+pref_adj[i]); best_meta=(path_arr[best_i],qb_arr[best_i],stack_arr[best_i],0,0,0)
            reasons[best_i]="Best remaining GPP upside; overlap relaxed to complete portfolio"
        else:
            path,qb,stack,worst,max_pr,max_tr=best_meta
            takes=sum(1 for pid in lineup_ids[best_i] if abs(prefs.get(pid,{}).get("boost",0.0))>1e-9 or prefs.get(pid,{}).get("min",0.0)>0)
            reasons[best_i]=f"GPP upside | {path} | player takes {takes} | max overlap {worst} | pair repeat {max_pr} | 3-core repeat {max_tr}"

        selected.append(best_i); selected_mask[best_i]=True
        path,qb,stack=path_arr[best_i],qb_arr[best_i],stack_arr[best_i]
        path_counts[path]=path_counts.get(path,0)+1; qb_counts[qb]=qb_counts.get(qb,0)+1; stack_counts[stack]=stack_counts.get(stack,0)+1
        for pid in lineup_ids[best_i]:
            if 0<=pid<=max_pid: player_counts[pid]+=1
        for t in lineup_teams[best_i]: team_counts[t]=team_counts.get(t,0)+1
        for g in lineup_games[best_i]: game_counts[g]=game_counts.get(g,0)+1
        for c in lineup_pairs[best_i]: pair_counts[c]=pair_counts.get(c,0)+1
        for c in lineup_triples[best_i]: triple_counts[c]=triple_counts.get(c,0)+1

    out=x.iloc[selected].copy().reset_index(drop=True)
    if not out.empty:
        out.insert(0,"Portfolio Slot",np.arange(1,len(out)+1)); out["Portfolio Reason"]=[reasons[i] for i in selected]
    out.attrs["requested_size"]=size; out.attrs["max_player_exposure"]=max_player_exposure; out.attrs["max_qb_exposure"]=max_qb_exposure
    out.attrs["max_team_exposure"]=max_team_exposure; out.attrs["max_game_exposure"]=max_game_exposure; out.attrs["path_soft_cap"]=.45; out.attrs["player_preferences"]=prefs
    out.attrs["max_pair_repeat"]=max(pair_counts.values(),default=0); out.attrs["max_triple_repeat"]=max(triple_counts.values(),default=0)
    unmet={}
    for pid,pref in prefs.items():
        actual=int(player_counts[pid]) if 0<=pid<=max_pid else 0
        if actual<pref["min_count"]: unmet[pid]={"requested":pref["min_count"],"actual":actual}
    out.attrs["unmet_minimums"]=unmet
    return out
'''
s=s[:start]+new+s[end:]
p.write_text(s,encoding='utf-8')

# --- SIM duplicate performance block cleanup ---
p=Path('pages/6_SIM.py')
s=p.read_text(encoding='utf-8')
# Collapse repeated state assignment.
s=s.replace('stage_times=st.session_state.get("nuke_stage_times",{})\nstage_times=st.session_state.get("nuke_stage_times",{})','stage_times=st.session_state.get("nuke_stage_times",{})')
# Keep exactly one Run Performance block between stage_times assignment and Candidate Pool Health.
state_anchor='stage_times=st.session_state.get("nuke_stage_times",{})\n'
cand_anchor='\nif candidate_diag:\n'
a=s.index(state_anchor)+len(state_anchor); b=s.index(cand_anchor,a)
perf='''\nif stage_times:\n    st.subheader("⏱️ Run Performance")\n    total=float(st.session_state.get("nuke_sim_runtime",0.0))\n    timing_cols=st.columns(len(stage_times))\n    for col,(name,secs) in zip(timing_cols,stage_times.items()):\n        col.metric(name,f"{float(secs):.1f}s")\n    if total>0:\n        slow_name,slow_secs=max(stage_times.items(),key=lambda kv:kv[1])\n        st.caption(f"Total {total:.1f}s · Bottleneck: {slow_name} ({float(slow_secs):.1f}s, {100.0*float(slow_secs)/total:.0f}% of run).")\n'''
s=s[:a]+perf+s[b:]
p.write_text(s,encoding='utf-8')
