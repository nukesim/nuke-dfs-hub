from pathlib import Path


def patch_app():
    p=Path('app.py')
    s=p.read_text(encoding='utf-8')
    imp='from default_slate import load_default_slate, SLATE_LABEL\n'
    add='from nuke_bridge import portable_to_hub_lineup\n'
    if add not in s:
        if imp not in s: raise SystemExit('app import anchor missing')
        s=s.replace(imp,imp+add,1)

    init_anchor='    st.session_state.setdefault("depth_df",None)\n'
    init_block='''    st.session_state.setdefault("depth_df",None)\n    st.session_state.setdefault("nuke_hub_bridge_ready",False)\n    st.session_state.setdefault("nuke_hub_bridge_version",0)\n    st.session_state.setdefault("nuke_hub_pool_ids",[])\n    st.session_state.setdefault("nuke_hub_role_adjustments",{})\n    st.session_state.setdefault("nuke_shared_portfolio_version",0)\n    st.session_state.setdefault("nuke_shared_portfolio_rows",[])\n    st.session_state.setdefault("nuke_hub_imported_portfolio_version",0)\n'''
    if 'nuke_hub_bridge_ready' not in s:
        if init_anchor not in s: raise SystemExit('app init anchor missing')
        s=s.replace(init_anchor,init_block,1)

    # Publish role adjustments whenever they are saved or cleared.
    save_anchor='''                st.session_state.model_df=model\n                st.session_state.model_errors=errs\n                st.rerun()\n            if o3.button("REMOVE ALL ROLE ADJUSTMENTS",use_container_width=True):\n'''
    save_block='''                st.session_state.model_df=model\n                st.session_state.model_errors=errs\n                st.session_state["nuke_hub_bridge_ready"]=True\n                st.session_state["nuke_hub_bridge_version"]=int(st.session_state.get("nuke_hub_bridge_version",0))+1\n                st.session_state["nuke_hub_pool_ids"]=list(st.session_state.pool_ids)\n                st.session_state["nuke_hub_role_adjustments"]=dict(st.session_state.projection_overrides)\n                st.rerun()\n            if o3.button("REMOVE ALL ROLE ADJUSTMENTS",use_container_width=True):\n'''
    if 'nuke_hub_role_adjustments"]=dict(st.session_state.projection_overrides)' not in s:
        if save_anchor not in s: raise SystemExit('app role save anchor missing')
        s=s.replace(save_anchor,save_block,1)

    clear_anchor='''                    st.session_state.model_df=model\n                    st.session_state.model_errors=errs\n                st.rerun()\n\n\nwith pooltab:\n'''
    clear_block='''                    st.session_state.model_df=model\n                    st.session_state.model_errors=errs\n                st.session_state["nuke_hub_bridge_ready"]=True\n                st.session_state["nuke_hub_bridge_version"]=int(st.session_state.get("nuke_hub_bridge_version",0))+1\n                st.session_state["nuke_hub_pool_ids"]=list(st.session_state.pool_ids)\n                st.session_state["nuke_hub_role_adjustments"]=dict(st.session_state.projection_overrides)\n                st.rerun()\n\n\nwith pooltab:\n'''
    if s.count('nuke_hub_role_adjustments"]=dict(st.session_state.projection_overrides)') < 2:
        if clear_anchor not in s: raise SystemExit('app role clear anchor missing')
        s=s.replace(clear_anchor,clear_block,1)

    pool_anchor='''    if a4.button("Apply Player Pool Changes",type="primary",use_container_width=True):\n        st.session_state.pool_ids=set(st.session_state.pending_pool_ids)\n        st.success(f"Player pool updated: {len(st.session_state.pool_ids)} players.")\n        st.rerun()\n'''
    pool_block='''    if a4.button("Apply Player Pool Changes",type="primary",use_container_width=True):\n        st.session_state.pool_ids=set(st.session_state.pending_pool_ids)\n        st.session_state["nuke_hub_bridge_ready"]=True\n        st.session_state["nuke_hub_bridge_version"]=int(st.session_state.get("nuke_hub_bridge_version",0))+1\n        st.session_state["nuke_hub_pool_ids"]=list(st.session_state.pool_ids)\n        st.session_state["nuke_hub_role_adjustments"]=dict(st.session_state.projection_overrides)\n        st.success(f"Player pool updated: {len(st.session_state.pool_ids)} players · synced to NUKE SIM.")\n        st.rerun()\n'''
    if 'synced to NUKE SIM' not in s:
        if pool_anchor not in s: raise SystemExit('app pool anchor missing')
        s=s.replace(pool_anchor,pool_block,1)

    tabs_anchor='''hub,modeltab,pooltab,qbplantab,buildtab,savedtab,exptab=st.tabs(["HUB","PLAYER MODEL","PLAYER POOL","QB PLAN","BUILD","SAVED LINEUPS","EXPOSURE & COMBOS"])\n'''
    bridge_ui='''# Shared Hub ↔ SIM session bridge. Import is always explicit so existing Hub lineups are never overwritten silently.\nshared_rows=st.session_state.get("nuke_shared_portfolio_rows",[])\nshared_ver=int(st.session_state.get("nuke_shared_portfolio_version",0))\nimported_ver=int(st.session_state.get("nuke_hub_imported_portfolio_version",0))\nif shared_rows and shared_ver>0:\n    with st.container(border=True):\n        b1,b2=st.columns([3,1])\n        b1.markdown("#### ☢️ NUKE SIM Portfolio Ready")\n        b1.caption(f"{len(shared_rows)} Portfolio Intelligence lineups are available from NUKE SIM. Import adds them to Saved Lineups and does not overwrite existing saved lineups.")\n        label="Imported" if imported_ver==shared_ver else "IMPORT SIM PORTFOLIO"\n        if b2.button(label,type="primary",use_container_width=True,disabled=(imported_ver==shared_ver),key=f"import_sim_portfolio_{shared_ver}"):\n            valid_ids=set(st.session_state.slate["Name + ID"].astype(str))\n            imported=0\n            skipped=0\n            next_id=next_saved_id()\n            for item in shared_rows:\n                lu=portable_to_hub_lineup(item)\n                if not lu or any(str(v) not in valid_ids for v in lu.values()):\n                    skipped+=1\n                    continue\n                st.session_state.saved_lineups[str(next_id)]=dict(lu)\n                next_id+=1\n                imported+=1\n            st.session_state["nuke_hub_imported_portfolio_version"]=shared_ver\n            if imported:\n                st.success(f"Imported {imported} NUKE SIM lineups into Saved Lineups" + (f" · skipped {skipped} slate mismatches" if skipped else ""))\n            else:\n                st.warning("No SIM lineups matched the Hub slate. Make sure both pages are using the same DraftKings slate.")\n            st.rerun()\n\n'''+tabs_anchor
    if '☢️ NUKE SIM Portfolio Ready' not in s:
        if tabs_anchor not in s: raise SystemExit('app tabs anchor missing')
        s=s.replace(tabs_anchor,bridge_ui,1)

    p.write_text(s,encoding='utf-8')


def patch_sim():
    p=Path('pages/6_SIM.py')
    s=p.read_text(encoding='utf-8')
    imp='from nuke_portfolio_story import portfolio_story\n'
    add='from nuke_bridge import sync_hub_pool_to_sim, portfolio_to_hub_rows\n'
    if add not in s:
        if imp not in s: raise SystemExit('sim import anchor missing')
        s=s.replace(imp,imp+add,1)

    pool_anchor='''pool_state=st.session_state.get("nuke_pregame_pool",{})\neditor_version=int(st.session_state.get("nuke_pool_editor_version",0))\n\nfor _,row in players.iterrows():\n'''
    pool_block='''pool_state=st.session_state.get("nuke_pregame_pool",{})\neditor_version=int(st.session_state.get("nuke_pool_editor_version",0))\n\n# Pull committed Hub player-pool and role adjustments only when the Hub version changes.\nhub_bridge_version=int(st.session_state.get("nuke_hub_bridge_version",0))\nlast_hub_version=int(st.session_state.get("nuke_sim_hub_bridge_version",-1))\nif st.session_state.get("nuke_hub_bridge_ready",False) and hub_bridge_version!=last_hub_version:\n    pool_state=sync_hub_pool_to_sim(\n        players,\n        pool_state,\n        st.session_state.get("nuke_hub_pool_ids",[]),\n        st.session_state.get("nuke_hub_role_adjustments",{}),\n    )\n    st.session_state["nuke_pregame_pool"]=pool_state\n    st.session_state["nuke_sim_hub_bridge_version"]=hub_bridge_version\n    st.session_state["nuke_pool_editor_version"]=editor_version+1\n    editor_version+=1\n    hub_pool_n=len(st.session_state.get("nuke_hub_pool_ids",[]))\n    hub_adj_n=len(st.session_state.get("nuke_hub_role_adjustments",{}))\n    st.success(f"Synced from Hub · {hub_pool_n if hub_pool_n else 'all'} players in committed pool · {hub_adj_n} role adjustments")\n\nfor _,row in players.iterrows():\n'''
    if 'Synced from Hub ·' not in s:
        if pool_anchor not in s: raise SystemExit('sim pool anchor missing')
        s=s.replace(pool_anchor,pool_block,1)

    publish_anchor='''        initial_takes={}\n        for k,v in {"nuke_sim_results":results,"nuke_sim_players":players.copy(),"nuke_sim_exposure":exposure,"nuke_path_exposure":pexposure,"nuke_contest_results":contest_results,"nuke_contest_summary":contest_summary,"nuke_portfolio":portfolio,"nuke_portfolio_paths":portfolio_paths,"nuke_portfolio_stats":portfolio_stats,"nuke_sim_runtime":run_seconds,"nuke_stage_times":stage_times,"nuke_candidate_diagnostics":candidate_diag,"nuke_player_takes":initial_takes}.items():\n'''
    publish_block='''        initial_takes={}\n        st.session_state["nuke_shared_portfolio_rows"]=portfolio_to_hub_rows(players,portfolio)\n        st.session_state["nuke_shared_portfolio_version"]=int(st.session_state.get("nuke_shared_portfolio_version",0))+1\n        for k,v in {"nuke_sim_results":results,"nuke_sim_players":players.copy(),"nuke_sim_exposure":exposure,"nuke_path_exposure":pexposure,"nuke_contest_results":contest_results,"nuke_contest_summary":contest_summary,"nuke_portfolio":portfolio,"nuke_portfolio_paths":portfolio_paths,"nuke_portfolio_stats":portfolio_stats,"nuke_sim_runtime":run_seconds,"nuke_stage_times":stage_times,"nuke_candidate_diagnostics":candidate_diag,"nuke_player_takes":initial_takes}.items():\n'''
    if 'nuke_shared_portfolio_rows"]=portfolio_to_hub_rows(players,portfolio)' not in s:
        if publish_anchor not in s: raise SystemExit('sim initial publish anchor missing')
        s=s.replace(publish_anchor,publish_block,1)

    rebuild_anchor='''                st.session_state["nuke_portfolio"]=new_portfolio\n                st.session_state["nuke_portfolio_paths"]=new_paths\n                st.session_state["nuke_portfolio_stats"]=new_stats\n'''
    rebuild_block='''                st.session_state["nuke_portfolio"]=new_portfolio\n                st.session_state["nuke_portfolio_paths"]=new_paths\n                st.session_state["nuke_portfolio_stats"]=new_stats\n                st.session_state["nuke_shared_portfolio_rows"]=portfolio_to_hub_rows(sim_players,new_portfolio)\n                st.session_state["nuke_shared_portfolio_version"]=int(st.session_state.get("nuke_shared_portfolio_version",0))+1\n'''
    if 'portfolio_to_hub_rows(sim_players,new_portfolio)' not in s:
        if rebuild_anchor not in s: raise SystemExit('sim rebuild publish anchor missing')
        s=s.replace(rebuild_anchor,rebuild_block,1)

    p.write_text(s,encoding='utf-8')


patch_app()
patch_sim()
print('Hub ↔ SIM bridge patched')
