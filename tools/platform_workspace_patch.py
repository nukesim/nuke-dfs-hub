from pathlib import Path

p=Path('pages/6_SIM.py')
s=p.read_text()

imp='from nuke_platform_workspace import switch_workspace, workspace_status\n'
if imp not in s:
    anchor='from fd_export import lineup_to_fd_slots, ANALYSIS_ROSTER_HEADERS\n'
    if anchor not in s:
        raise RuntimeError('import anchor not found')
    s=s.replace(anchor, anchor+imp, 1)

old='''    previous_site=st.session_state.get("nuke_sim_active_site")\n    site=st.segmented_control("Platform",options=["DK","FD"],format_func=lambda x: "DraftKings" if x=="DK" else "FanDuel",default=st.session_state.get("dfs_site","DK"),key="dfs_site") or "DK"\n    if previous_site is not None and previous_site != site:\n        for key in [\n            "nuke_sim_results","nuke_sim_players","nuke_sim_exposure","nuke_path_exposure",\n            "nuke_contest_results","nuke_contest_summary","nuke_portfolio","nuke_portfolio_paths",\n            "nuke_portfolio_stats","nuke_sim_runtime","nuke_stage_times","nuke_candidate_diagnostics",\n            "nuke_player_takes","nuke_shared_portfolio_rows","nuke_shared_portfolio_version",\n            "nuke_pregame_pool","nuke_pool_editor_version"\n        ]:\n            st.session_state.pop(key,None)\n    st.session_state["nuke_sim_active_site"]=site\n    cfg=get_platform(site)\n    st.caption(f"{cfg.name} · ${cfg.salary_cap:,} cap · {'1.0 PPR + yardage bonuses' if site=='DK' else '0.5 PPR · no 100/300-yard bonuses'}")\n'''
new='''    site=st.segmented_control("Platform",options=["DK","FD"],format_func=lambda x: "DraftKings" if x=="DK" else "FanDuel",default=st.session_state.get("dfs_site","DK"),key="dfs_site") or "DK"\n    previous_site,workspace_restored=switch_workspace(st.session_state,site)\n    cfg=get_platform(site)\n    st.caption(f"{cfg.name} · ${cfg.salary_cap:,} cap · {'1.0 PPR + yardage bonuses' if site=='DK' else '0.5 PPR · no 100/300-yard bonuses'}")\n    dk_saved=workspace_status(st.session_state,"DK")\n    fd_saved=workspace_status(st.session_state,"FD")\n    st.caption(f"Workspace memory · DraftKings {'✓ saved' if dk_saved else 'empty'} · FanDuel {'✓ saved' if fd_saved else 'empty'}")\n    if previous_site is not None and previous_site != site:\n        if workspace_restored:\n            st.success(f"Restored your {cfg.name} SIM workspace.")\n        else:\n            st.info(f"Opened a fresh {cfg.name} workspace. Your {('FanDuel' if site=='DK' else 'DraftKings')} work is saved for this session.")\n'''
if old not in s:
    if new not in s:
        raise RuntimeError('platform reset block not found')
else:
    s=s.replace(old,new,1)

p.write_text(s)
print('Per-platform workspace persistence applied')
# trigger 2026-08-31
