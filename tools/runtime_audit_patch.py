from pathlib import Path
p=Path('pages/6_SIM.py')
s=p.read_text(encoding='utf-8')

# Expand overlap diagnostics so the number is self-explanatory and auditable.
s=s.replace(
'''    avg_overlap=float(sum(overlap_vals)/len(overlap_vals)) if overlap_vals else 0.0\n''',
'''    avg_overlap=float(sum(overlap_vals)/len(overlap_vals)) if overlap_vals else 0.0\n    median_overlap=float(np.median(overlap_vals)) if overlap_vals else 0.0\n    p95_overlap=float(np.percentile(overlap_vals,95)) if overlap_vals else 0.0\n    max_overlap_seen=int(max(overlap_vals)) if overlap_vals else 0\n''')
s=s.replace(
'''return {"grade":grade,"score":score,"generated":n,"requested":int(requested),"fill_pct":fill_pct,"unique_qbs":len(qb_names),"games":len(games),"avg_overlap":avg_overlap,"max_pair_repeat":max_pair,"max_pair_pct":max_pair_pct,"max_triple_repeat":max_triple,"max_triple_pct":max_triple_pct,"avg_salary":avg_salary,"min_salary":int(min_salary)}''',
'''return {"grade":grade,"score":score,"generated":n,"requested":int(requested),"fill_pct":fill_pct,"unique_qbs":len(qb_names),"games":len(games),"avg_overlap":avg_overlap,"median_overlap":median_overlap,"p95_overlap":p95_overlap,"max_overlap_seen":max_overlap_seen,"max_pair_repeat":max_pair,"max_pair_pct":max_pair_pct,"max_triple_repeat":max_triple,"max_triple_pct":max_triple_pct,"avg_salary":avg_salary,"min_salary":int(min_salary)}''')

# Stage timing dictionary.
s=s.replace(
'''    run_started=time.perf_counter()\n    seed=int(manual_seed)''',
'''    run_started=time.perf_counter()\n    stage_times={}\n    seed=int(manual_seed)''')
s=s.replace(
'''        st.write(f"Candidate generation: {time.perf_counter()-stage:.1f}s")''',
'''        stage_times["Candidate Generation"]=time.perf_counter()-stage\n        st.write(f"Candidate generation: {stage_times['Candidate Generation']:.1f}s")''')
s=s.replace(
'''        st.write(f"Football simulation: {time.perf_counter()-stage:.1f}s")''',
'''        stage_times["Football Simulation"]=time.perf_counter()-stage\n        st.write(f"Football simulation: {stage_times['Football Simulation']:.1f}s")''')
s=s.replace(
'''        st.write(f"Ranking + paths: {time.perf_counter()-stage:.1f}s")''',
'''        stage_times["Ranking + Paths"]=time.perf_counter()-stage\n        st.write(f"Ranking + paths: {stage_times['Ranking + Paths']:.1f}s")''')
s=s.replace(
'''        st.write(f"Contest simulation: {time.perf_counter()-stage:.1f}s")''',
'''        stage_times["Contest Simulation"]=time.perf_counter()-stage\n        st.write(f"Contest simulation: {stage_times['Contest Simulation']:.1f}s")''')
s=s.replace(
'''        st.write(f"Portfolio build: {time.perf_counter()-stage:.1f}s")\n        run_seconds=time.perf_counter()-run_started''',
'''        stage_times["Portfolio Build"]=time.perf_counter()-stage\n        st.write(f"Portfolio build: {stage_times['Portfolio Build']:.1f}s")\n        run_seconds=time.perf_counter()-run_started\n        stage_times["Other / UI Overhead"]=max(0.0,run_seconds-sum(stage_times.values()))''')
s=s.replace(
'''"nuke_sim_runtime":run_seconds,"nuke_candidate_diagnostics":candidate_diag,''',
'''"nuke_sim_runtime":run_seconds,"nuke_stage_times":stage_times,"nuke_candidate_diagnostics":candidate_diag,''')

# Read timings and show a persistent breakdown after each run.
s=s.replace(
'''portfolio_stats=st.session_state.get("nuke_portfolio_stats",{})\ncandidate_diag=st.session_state.get("nuke_candidate_diagnostics",{})''',
'''portfolio_stats=st.session_state.get("nuke_portfolio_stats",{})\ncandidate_diag=st.session_state.get("nuke_candidate_diagnostics",{})\nstage_times=st.session_state.get("nuke_stage_times",{})''')
s=s.replace(
'''if candidate_diag:\n    st.subheader("🩺 Candidate Pool Health")''',
'''if stage_times:\n    st.subheader("⏱️ Run Performance")\n    total=float(st.session_state.get("nuke_sim_runtime",0.0))\n    timing_cols=st.columns(len(stage_times))\n    for col,(name,secs) in zip(timing_cols,stage_times.items()):\n        col.metric(name,f"{float(secs):.1f}s")\n    if total>0:\n        slow_name,slow_secs=max(stage_times.items(),key=lambda kv:kv[1])\n        st.caption(f"Total {total:.1f}s · Bottleneck: {slow_name} ({float(slow_secs):.1f}s, {100.0*float(slow_secs)/total:.0f}% of run).")\n\nif candidate_diag:\n    st.subheader("🩺 Candidate Pool Health")''')
s=s.replace(
'''    d4.metric("Avg Overlap",f"{float(candidate_diag.get('avg_overlap',0)):.2f}")''',
'''    d4.metric("Avg Shared Players",f"{float(candidate_diag.get('avg_overlap',0)):.2f}",help="Average number of identical players shared by two candidate lineups. This is calculated across candidate-lineup pairs, not against one reference lineup.")''')
s=s.replace(
'''    st.caption(f"Generated {float(candidate_diag.get('fill_pct',0)):.1f}% of requested candidates · {int(candidate_diag.get('games',0))} games represented · Avg salary ${float(candidate_diag.get('avg_salary',0)):,.0f}.")''',
'''    st.caption(f"Generated {float(candidate_diag.get('fill_pct',0)):.1f}% of requested candidates · {int(candidate_diag.get('games',0))} games represented · Avg salary ${float(candidate_diag.get('avg_salary',0)):,.0f} · Shared-player overlap: median {float(candidate_diag.get('median_overlap',0)):.1f}, 95th percentile {float(candidate_diag.get('p95_overlap',0)):.1f}, max {int(candidate_diag.get('max_overlap_seen',0))}.")''')

p.write_text(s,encoding='utf-8')
