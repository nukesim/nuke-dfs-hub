from pathlib import Path

p=Path('pages/6_SIM.py')
s=p.read_text()
anchor='''    site=st.segmented_control("Platform",options=["DK","FD"],format_func=lambda x: "DraftKings" if x=="DK" else "FanDuel",default=st.session_state.get("dfs_site","DK"),key="dfs_site") or "DK"\n    cfg=get_platform(site)\n'''
replacement='''    previous_site=st.session_state.get("nuke_sim_active_site")\n    site=st.segmented_control("Platform",options=["DK","FD"],format_func=lambda x: "DraftKings" if x=="DK" else "FanDuel",default=st.session_state.get("dfs_site","DK"),key="dfs_site") or "DK"\n    if previous_site is not None and previous_site != site:\n        for key in [\n            "nuke_sim_results","nuke_sim_players","nuke_sim_exposure","nuke_path_exposure",\n            "nuke_contest_results","nuke_contest_summary","nuke_portfolio","nuke_portfolio_paths",\n            "nuke_portfolio_stats","nuke_sim_runtime","nuke_stage_times","nuke_candidate_diagnostics",\n            "nuke_player_takes","nuke_shared_portfolio_rows","nuke_shared_portfolio_version",\n            "nuke_pregame_pool","nuke_pool_editor_version"\n        ]:\n            st.session_state.pop(key,None)\n    st.session_state["nuke_sim_active_site"]=site\n    cfg=get_platform(site)\n'''
if anchor not in s:
    if replacement not in s:
        raise RuntimeError('SIM platform selector anchor not found')
else:
    s=s.replace(anchor,replacement,1)

p.write_text(s)
print('SIM platform switch now clears stale platform-specific results')
