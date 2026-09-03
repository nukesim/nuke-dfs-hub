from pathlib import Path

p=Path('pages/6_SIM.py')
s=p.read_text(encoding='utf-8')

imp='from fd_export import lineup_to_fd_slots, ANALYSIS_ROSTER_HEADERS\n'
newimp=imp+'from nuke_workspace import workspace_bytes, load_workspace_bytes, apply_workspace\n'
if 'from nuke_workspace import' not in s:
    if imp not in s: raise SystemExit('import anchor not found')
    s=s.replace(imp,newimp,1)

old='''with st.sidebar:\n    st.header("SIM CONTROL ROOM")\n    previous_site=st.session_state.get("nuke_sim_active_site")\n    site=st.segmented_control("Platform",options=["DK","FD"],format_func=lambda x: "DraftKings" if x=="DK" else "FanDuel",default=st.session_state.get("dfs_site","DK"),key="dfs_site") or "DK"'''
new='''with st.sidebar:\n    st.header("SIM CONTROL ROOM")\n    with st.expander("💾 WORKSPACE", expanded=False):\n        st.caption("Save your slate work and come back later in the week. Player pool, role/usage changes, contest settings, portfolio controls, and Player Takes are restored. Latest odds/injury data refresh when you run again.")\n        workspace_upload=st.file_uploader("Load workspace", type=["json"], key="nuke_workspace_upload", label_visibility="collapsed")\n        if workspace_upload is not None and st.button("↩️ LOAD WORKSPACE", use_container_width=True, key="load_nuke_workspace"):\n            try:\n                ws=load_workspace_bytes(workspace_upload.getvalue())\n                apply_workspace(st.session_state,ws)\n                st.session_state["nuke_workspace_loaded_notice"]=f"Workspace loaded · {ws.get('slate_label') or 'saved slate'}"\n                st.rerun()\n            except Exception as e:\n                st.error(f"Could not load workspace: {e}")\n        st.download_button("⬇️ SAVE WORKSPACE", workspace_bytes(st.session_state, st.session_state.get("nuke_workspace_slate_label","")), "nuke_sim_workspace.json", "application/json", use_container_width=True, key="save_nuke_workspace")\n        st.caption("Workspace files contain your NUKE settings only — not account credentials or API keys.")\n    if st.session_state.pop("nuke_workspace_loaded_notice",None):\n        st.success("Workspace loaded.")\n    previous_site=st.session_state.get("nuke_sim_active_site")\n    site=st.segmented_control("Platform",options=["DK","FD"],format_func=lambda x: "DraftKings" if x=="DK" else "FanDuel",default=st.session_state.get("dfs_site","DK"),key="dfs_site") or "DK"'''
if old in s:
    s=s.replace(old,new,1)
elif '💾 WORKSPACE' not in s:
    raise SystemExit('sidebar anchor not found')

repls={
'    preset=st.selectbox("Preset",["QUICK","STANDARD","DEEP"],index=0)': '    preset=st.selectbox("Preset",["QUICK","STANDARD","DEEP"],index=0,key="sim_preset")',
'    candidates=st.number_input("Candidate lineups",100,5000,candidates,100)': '    candidates=st.number_input("Candidate lineups",100,5000,candidates,100,key="candidate_lineups")',
'    sims=st.number_input("Football universes",250,10000,sims,250)': '    sims=st.number_input("Football universes",250,10000,sims,250,key="football_universes")',
'    exposure_n=st.number_input("Exposure sample",10,150,exposure_n,10)': '    exposure_n=st.number_input("Exposure sample",10,150,exposure_n,10,key="exposure_sample")',
'        fixed_seed=st.checkbox("Use reproducible seed",value=False,help="Off by default: every RUN NUKE SIM click gets a fresh random simulation. Turn this on only when you want to reproduce a specific run.")': '        fixed_seed=st.checkbox("Use reproducible seed",value=False,help="Off by default: every RUN NUKE SIM click gets a fresh random simulation. Turn this on only when you want to reproduce a specific run.",key="use_reproducible_seed")',
'    field_size=st.number_input("Field size",2,100000,2222,1)': '    field_size=st.number_input("Field size",2,100000,2222,1,key="field_size")',
'    entry_fee=st.number_input("Entry fee ($)",.25,10000.,100.,1.)': '    entry_fee=st.number_input("Entry fee ($)",.25,10000.,100.,1.,key="entry_fee")',
'    first_prize=st.number_input("1st prize ($)",1.,10000000.,50000.,100.)': '    first_prize=st.number_input("1st prize ($)",1.,10000000.,50000.,100.,key="first_prize")',
'    contest_iters=st.number_input("Contest iterations",50,5000,contest_iters,50)': '    contest_iters=st.number_input("Contest iterations",50,5000,contest_iters,50,key="contest_iterations")',
'    portfolio_size=st.number_input("Portfolio size",1,150,150,1)': '    portfolio_size=st.number_input("Portfolio size",1,150,150,1,key="portfolio_size")',
'    max_overlap=st.slider("Max player overlap",4,8,7,1)': '    max_overlap=st.slider("Max player overlap",4,8,7,1,key="max_player_overlap")',
'    path_balance=st.slider("Path diversification",0.,3.,1.25,.25)': '    path_balance=st.slider("Path diversification",0.,3.,1.25,.25,key="path_diversification")',
'    max_player_exp=st.slider("Max player exposure %",10,100,45,5)': '    max_player_exp=st.slider("Max player exposure %",10,100,45,5,key="max_player_exposure")',
'    max_qb_exp=st.slider("Max QB exposure %",5,100,30,5)': '    max_qb_exp=st.slider("Max QB exposure %",5,100,30,5,key="max_qb_exposure")',
'    max_team_exp=st.slider("Max team exposure %",10,100,80,5)': '    max_team_exp=st.slider("Max team exposure %",10,100,80,5,key="max_team_exposure")',
'    max_game_exp=st.slider("Max game exposure %",10,100,70,5)': '    max_game_exp=st.slider("Max game exposure %",10,100,70,5,key="max_game_exposure")',
}
for oldx,newx in repls.items():
    if oldx in s: s=s.replace(oldx,newx,1)
    elif newx not in s: raise SystemExit('control target not found: '+oldx)

anchor='''except Exception as e:\n    st.error(f"Could not load slate: {e}")\n    st.stop()\n\nst.subheader("🏆 Contest Payouts")'''
rep='''except Exception as e:\n    st.error(f"Could not load slate: {e}")\n    st.stop()\n\nst.session_state["nuke_workspace_slate_label"]=slate_source\n\nst.subheader("🏆 Contest Payouts")'''
if anchor in s:
    s=s.replace(anchor,rep,1)
elif 'nuke_workspace_slate_label' not in s:
    raise SystemExit('slate label anchor not found')

p.write_text(s,encoding='utf-8')
print('patched NUKE SIM workspace support')
# trigger after workflow exists
