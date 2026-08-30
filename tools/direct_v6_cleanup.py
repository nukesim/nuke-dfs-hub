from pathlib import Path
import re

# ---------- Portfolio Engine V6 ----------
p=Path('nuke_portfolio.py')
s=p.read_text(encoding='utf-8')
s=s.replace('PORTFOLIO_ENGINE_VERSION = "Portfolio Engine V5.2"','PORTFOLIO_ENGINE_VERSION = "Portfolio Engine V6"')
start=s.index('def build_portfolio(')
end=s.index('\n\ndef portfolio_summary',start)
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
    """Portfolio Engine V6: same portfolio rules, faster execution.

    V6 precomputes lineup overlap, pair/core membership, and encoded path/QB/stack
    data once. Selection then uses NumPy arrays and incremental counters instead of
    rebuilding lineup relationships on every candidate comparison.
    """
    if contest_results is None or contest_results.empty:
        return pd.DataFrame()

    x=contest_results.reset_index(drop=True).copy(); n=len(x)
    size=max(1,min(int(size),n)); max_overlap=int(np.clip(max_overlap,0,8))
    max_player_exposure=float(np.clip(max_player_exposure,.01,1.0)); max_qb_exposure=float(np.clip(max_qb_exposure,.01,1.0))
    max_team_exposure=float(np.clip(max_team_exposure,.01,1.0)); max_game_exposure=float(np.clip(max_game_exposure,.01,1.0))
    global_max_player_count=max(1,int(np.floor(size*max_player_exposure+1e-9))); max_qb_count=max(1,int(np.floor(size*max_qb_exposure+1e-9)))
    max_team_count=max(1,int(np.floor(size*max_team_exposure+1e-9))); max_game_count=max(1,int(np.floor(size*max_game_exposure+1e-9)))
    prefs=_normalize_player_preferences(player_preferences,size,max_player_exposure)

    def numcol(name,default=0):
        return pd.to_numeric(x.get(name,pd.Series([default]*n)),errors='coerce').fillna(default).to_numpy(float)
    base=.75*_z(numcol('Sim ROI %'))+.90*_z(numcol('1st %'))+.75*_z(numcol('Top 0.1%'))+.45*_z(numcol('Top 1%'))+.55*_z(numcol('Ceiling 95'))+.30*_z(numcol('NUKE Score'))+.15*_z(numcol('Path Score',50))

    path_vals=x.get('Strongest Path',pd.Series(['UNKNOWN']*n)).fillna('UNKNOWN').astype(str).to_numpy()
    qb_vals=x.get('QB',pd.Series(['UNKNOWN']*n)).fillna('UNKNOWN').astype(str).to_numpy()
    stack_vals=x.get('Stack',pd.Series(['UNKNOWN']*n)).fillna('UNKNOWN').astype(str).to_numpy()
    lineup_ids=[tuple(map(int,lu)) for lu in x['_indices']] if '_indices' in x.columns else [tuple() for _ in range(n)]
    lineup_teams,lineup_games=_lineup_team_game_sets(players,lineup_ids)

    max_pid=max((max(lu) for lu in lineup_ids if lu),default=-1)
    lu_mat=np.full((n,9),-1,dtype=np.int32)
    for i,lu in enumerate(lineup_ids):
        lu_mat[i,:min(9,len(lu))]=np.asarray(lu[:9],dtype=np.int32)
    if max_pid>=0:
        incidence=np.zeros((n,max_pid+1),dtype=np.uint8)
        rr=np.repeat(np.arange(n),9); cc=lu_mat.ravel(); valid=cc>=0
        incidence[rr[valid],cc[valid]]=1
        overlap_matrix=(incidence @ incidence.T).astype(np.uint8)
    else:
        overlap_matrix=np.zeros((n,n),dtype=np.uint8)

    # Encode categorical controls once.
    path_names,path_code=np.unique(path_vals,return_inverse=True); qb_names,qb_code=np.unique(qb_vals,return_inverse=True); stack_names,stack_code=np.unique(stack_vals,return_inverse=True)
    path_support=np.bincount(path_code,minlength=len(path_names)); support_floor=max(2,int(np.ceil(size*.015)))
    viable_path=np.asarray(path_support>=support_floor,dtype=bool)
    if not viable_path.any(): viable_path[:]=True
    target_per_path=max(1.0,size/max(1,int(viable_path.sum())))

    pref_adjust=np.zeros(n,dtype=float)
    for i,lu in enumerate(lineup_ids): pref_adjust[i]=sum(.42*prefs.get(pid,{}).get('boost',0.0) for pid in lu)

    # Encode every unique 2-player and 3-player core once.
    pair_map={}; triple_map={}; pair_ids=[]; triple_ids=[]
    for lu in lineup_ids:
        sid=tuple(sorted(set(lu))); pa=[]; tr=[]
        for core in itertools.combinations(sid,2):
            if core not in pair_map: pair_map[core]=len(pair_map)
            pa.append(pair_map[core])
        for core in itertools.combinations(sid,3):
            if core not in triple_map: triple_map[core]=len(triple_map)
            tr.append(triple_map[core])
        pair_ids.append(np.asarray(pa,dtype=np.int32)); triple_ids.append(np.asarray(tr,dtype=np.int32))
    pair_counts=np.zeros(len(pair_map),dtype=np.int32); triple_counts=np.zeros(len(triple_map),dtype=np.int32)

    player_counts=np.zeros(max_pid+1 if max_pid>=0 else 0,dtype=np.int32)
    player_caps=np.full(max_pid+1 if max_pid>=0 else 0,global_max_player_count,dtype=np.int32)
    for pid,pref in prefs.items():
        if 0<=pid<len(player_caps): player_caps[pid]=max(0,int(pref['max_count']))
    path_counts=np.zeros(len(path_names),dtype=np.int32); qb_counts=np.zeros(len(qb_names),dtype=np.int32); stack_counts=np.zeros(len(stack_names),dtype=np.int32)
    team_counts={}; game_counts={}; selected=[]; selected_mask=np.zeros(n,dtype=bool); reasons={}

    for pick in range(size):
        eligible=~selected_mask
        if player_counts.size:
            for i in np.where(eligible)[0]:
                lu=lu_mat[i]; lu=lu[lu>=0]
                if lu.size and np.any(player_counts[lu]>=player_caps[lu]): eligible[i]=False
        eligible &= qb_counts[qb_code] < max_qb_count
        for i in np.where(eligible)[0]:
            if any(team_counts.get(t,0)>=max_team_count for t in lineup_teams[i]) or any(game_counts.get(g,0)>=max_game_count for g in lineup_games[i]): eligible[i]=False
        cand=np.where(eligible)[0]
        if not len(cand): break

        if selected:
            ovs=overlap_matrix[np.ix_(cand,np.asarray(selected,dtype=int))]
            worst=ovs.max(axis=1).astype(float); avg=ovs.mean(axis=1)
            keep=worst<=max_overlap; cand=cand[keep]; worst=worst[keep]; avg=avg[keep]
        else:
            worst=np.zeros(len(cand)); avg=np.zeros(len(cand))

        if not len(cand):
            # Relax overlap only, preserving exposure caps, to finish a feasible portfolio.
            cand=np.where(eligible)[0]
            if not len(cand): break
            worst=np.zeros(len(cand)); avg=np.zeros(len(cand))

        pc=path_code[cand]; qc=qb_code[cand]; sc=stack_code[cand]
        current_path=path_counts[pc].astype(float); saturation=current_path/target_per_path
        path_adj=np.where(viable_path[pc],float(path_balance)*(.55*np.maximum(0,1-saturation)-.42*np.maximum(0,saturation-1)**2),0.0)
        next_share=(current_path+1)/max(1,len(selected)+1); excess=np.maximum(0,(next_share-.45)/.10)
        dominance=np.where(viable_path[pc]&(next_share>.45),float(path_balance)*(.90*excess+.50*excess**2),0.0)
        denom=max(1,len(selected)); qb_share=qb_counts[qc]/denom; stack_share=stack_counts[sc]/denom
        concentration=.25*np.maximum(0,qb_share-.20)+.10*np.maximum(0,stack_share-.55)
        redundancy=.10*np.maximum(0,avg-5.25)+.16*np.maximum(0,worst-6)

        core_pen=np.zeros(len(cand),dtype=float); pair_max=np.zeros(len(cand),dtype=int); triple_max=np.zeros(len(cand),dtype=int)
        min_bonus=np.zeros(len(cand),dtype=float); slots_left=size-pick
        for z,i in enumerate(cand):
            pa=pair_counts[pair_ids[i]] if len(pair_ids[i]) else np.empty(0,dtype=int); tr=triple_counts[triple_ids[i]] if len(triple_ids[i]) else np.empty(0,dtype=int)
            pm=int(pa.max()) if pa.size else 0; tm=int(tr.max()) if tr.size else 0; pair_max[z]=pm; triple_max[z]=tm
            core_pen[z]=.035*np.maximum(0,pa-4).sum()+.075*np.maximum(0,tr-2).sum()+.08*max(0,pm-10)**1.35+.16*max(0,tm-6)**1.45
            bonus=0.0
            for pid in lineup_ids[i]:
                need=max(0,prefs.get(pid,{}).get('min_count',0)-(int(player_counts[pid]) if 0<=pid<len(player_counts) else 0))
                if need: bonus += 1.10+2.40*(need/max(1,slots_left))
            min_bonus[z]=bonus

        scores=base[cand]+pref_adjust[cand]+min_bonus+path_adj-dominance-concentration-redundancy-core_pen
        z=int(np.argmax(scores)); best_i=int(cand[z]); selected.append(best_i); selected_mask[best_i]=True
        path_counts[path_code[best_i]]+=1; qb_counts[qb_code[best_i]]+=1; stack_counts[stack_code[best_i]]+=1
        for pid in lineup_ids[best_i]:
            if 0<=pid<len(player_counts): player_counts[pid]+=1
        for t in lineup_teams[best_i]: team_counts[t]=team_counts.get(t,0)+1
        for g in lineup_games[best_i]: game_counts[g]=game_counts.get(g,0)+1
        if len(pair_ids[best_i]): pair_counts[pair_ids[best_i]]+=1
        if len(triple_ids[best_i]): triple_counts[triple_ids[best_i]]+=1
        takes=sum(1 for pid in lineup_ids[best_i] if abs(prefs.get(pid,{}).get('boost',0.0))>1e-9 or prefs.get(pid,{}).get('min',0.0)>0)
        reasons[best_i]=f"GPP upside | {path_vals[best_i]} | player takes {takes} | max overlap {int(worst[z])} | pair repeat {int(pair_max[z])} | 3-core repeat {int(triple_max[z])}"

    out=x.iloc[selected].copy().reset_index(drop=True)
    if not out.empty:
        out.insert(0,'Portfolio Slot',np.arange(1,len(out)+1)); out['Portfolio Reason']=[reasons[i] for i in selected]
    out.attrs['requested_size']=size; out.attrs['max_player_exposure']=max_player_exposure; out.attrs['max_qb_exposure']=max_qb_exposure
    out.attrs['max_team_exposure']=max_team_exposure; out.attrs['max_game_exposure']=max_game_exposure; out.attrs['path_soft_cap']=.45; out.attrs['player_preferences']=prefs
    out.attrs['max_pair_repeat']=int(pair_counts.max()) if pair_counts.size else 0; out.attrs['max_triple_repeat']=int(triple_counts.max()) if triple_counts.size else 0
    unmet={}
    for pid,pref in prefs.items():
        actual=int(player_counts[pid]) if 0<=pid<len(player_counts) else 0
        if actual<pref['min_count']: unmet[pid]={'requested':pref['min_count'],'actual':actual}
    out.attrs['unmet_minimums']=unmet
    return out
'''
s=s[:start]+new+s[end:]
p.write_text(s,encoding='utf-8')

# ---------- Clean SIM diagnostic duplication ----------
p=Path('pages/6_SIM.py')
s=p.read_text(encoding='utf-8')
# Collapse repeated median/p95/max diagnostic assignments.
for line in [
    '    median_overlap=float(np.median(overlap_vals)) if overlap_vals else 0.0\n',
    '    p95_overlap=float(np.percentile(overlap_vals,95)) if overlap_vals else 0.0\n',
    '    max_overlap_seen=int(max(overlap_vals)) if overlap_vals else 0\n',
]:
    first=s.find(line)
    if first!=-1:
        head=s[:first+len(line)]; tail=s[first+len(line):].replace(line,''); s=head+tail
# Keep one stage_times assignment in the results-reading section.
s=re.sub(r'(stage_times=st\.session_state\.get\("nuke_stage_times",\{\}\)\n)(?:stage_times=st\.session_state\.get\("nuke_stage_times",\{\}\)\n)+',r'\1',s)
# Replace every consecutive Run Performance block group before candidate diagnostics with exactly one.
marker='if candidate_diag:\n'
pos=s.find(marker)
pre=s[:pos]; post=s[pos:]
first=pre.find('if stage_times:\n    st.subheader("⏱️ Run Performance")')
if first!=-1:
    perf='''if stage_times:\n    st.subheader("⏱️ Run Performance")\n    total=float(st.session_state.get("nuke_sim_runtime",0.0))\n    timing_cols=st.columns(len(stage_times))\n    for col,(name,secs) in zip(timing_cols,stage_times.items()):\n        col.metric(name,f"{float(secs):.1f}s")\n    if total>0:\n        slow_name,slow_secs=max(stage_times.items(),key=lambda kv:kv[1])\n        st.caption(f"Total {total:.1f}s · Bottleneck: {slow_name} ({float(slow_secs):.1f}s, {100.0*float(slow_secs)/total:.0f}% of run).")\n\n'''
    pre=pre[:first]+perf
    s=pre+post
p.write_text(s,encoding='utf-8')

# Self-disable this one-shot workflow before commit so it cannot patch future pushes.
w=Path('.github/workflows/direct-v6-cleanup.yml')
if w.exists():
    w.write_text('''name: Direct V6 Cleanup\non:\n  workflow_dispatch:\njobs:\n  disabled:\n    if: ${{ false }}\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo "Direct V6 migration completed."\n''',encoding='utf-8')
