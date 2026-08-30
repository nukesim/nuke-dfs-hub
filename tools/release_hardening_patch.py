from pathlib import Path


def patch_sim():
    p=Path('pages/6_SIM.py'); s=p.read_text(encoding='utf-8')
    imp='from nuke_bridge import sync_hub_pool_to_sim, portfolio_to_hub_rows\n'
    add='from nuke_run_audit import make_run_audit, audit_rows, reset_week_state, AUDIT_VERSION\n'
    if add not in s:
        if imp not in s: raise SystemExit('sim import anchor missing')
        s=s.replace(imp,imp+add,1)

    title='st.caption(f"Projection-free NFL DFS outcome + contest simulation inside the NUKE DFS Hub · {ENGINE_VERSION}.")\n'
    title_add=title+'''\nif st.session_state.pop("nuke_week_reset_notice",False):\n    st.success("New week started clean. Prior player-pool edits, SIM results, portfolios, saved Hub lineups, and run history were cleared.")\n\nwith st.expander("⚙️ Slate Session",expanded=False):\n    st.caption("Use this when moving to a new DraftKings slate. It clears weekly work while keeping the app itself and sidebar defaults intact.")\n    confirm_reset=st.checkbox("I understand this clears the current week's NUKE/Hub work",key="nuke_confirm_week_reset")\n    if st.button("🧹 START NEW WEEK / CLEAR SLATE SESSION",use_container_width=True,disabled=not confirm_reset):\n        reset_week_state(st.session_state)\n        st.rerun()\n'''
    if 'START NEW WEEK / CLEAR SLATE SESSION' not in s:
        if title not in s: raise SystemExit('sim title anchor missing')
        s=s.replace(title,title_add,1)

    audit_anchor='''        initial_takes={}\n        st.session_state["nuke_shared_portfolio_rows"]=portfolio_to_hub_rows(players,portfolio)\n'''
    audit_block='''        initial_takes={}\n        audit=make_run_audit(\n            slate=slate_source,preset=preset,seed=seed,fixed_seed=fixed_seed,candidates=candidates,\n            football_universes=sims,field_size=field_size,entry_fee=entry_fee,first_prize=first_prize,\n            contest_iterations=contest_iters,portfolio_size=len(portfolio),min_salary=min_salary,runtime=run_seconds,\n            football_engine=ENGINE_VERSION,portfolio_engine=PORTFOLIO_ENGINE_VERSION,candidate_health=candidate_diag,\n        )\n        st.session_state["nuke_last_run_audit"]=audit\n        history=list(st.session_state.get("nuke_run_history",[]))\n        history.insert(0,audit)\n        st.session_state["nuke_run_history"]=history[:20]\n        st.session_state["nuke_shared_portfolio_rows"]=portfolio_to_hub_rows(players,portfolio)\n'''
    if 'nuke_last_run_audit' not in s:
        if audit_anchor not in s: raise SystemExit('sim audit anchor missing')
        s=s.replace(audit_anchor,audit_block,1)

    results_anchor='''stage_times=st.session_state.get("nuke_stage_times",{})\n\nif stage_times:\n'''
    results_block='''stage_times=st.session_state.get("nuke_stage_times",{})\nlast_audit=st.session_state.get("nuke_last_run_audit",{})\n\nif last_audit:\n    st.subheader("🧾 Run Summary")\n    st.caption(f"{AUDIT_VERSION} · exact settings captured when this portfolio was created.")\n    a1,a2,a3,a4,a5,a6=st.columns(6)\n    a1.metric("Slate",str(last_audit.get("slate","—")))\n    a2.metric("Preset",str(last_audit.get("preset","—")))\n    a3.metric("Seed",str(last_audit.get("seed","—")),delta=str(last_audit.get("seed_mode","—")))\n    a4.metric("Field",f"{int(last_audit.get('field_size',0)):,}")\n    a5.metric("Portfolio",f"{int(last_audit.get('portfolio_size',0)):,}")\n    a6.metric("Runtime",f"{float(last_audit.get('runtime_seconds',0)):.1f}s")\n    with st.expander("Run details + recent history",expanded=False):\n        details=pd.DataFrame(audit_rows(last_audit),columns=["Setting","Value"])\n        st.dataframe(details,use_container_width=True,hide_index=True)\n        history=st.session_state.get("nuke_run_history",[])\n        if history:\n            st.markdown("#### Recent Runs")\n            hdf=pd.DataFrame(history)\n            cols=["timestamp","slate","preset","seed","field_size","portfolio_size","candidate_grade","runtime_seconds"]\n            hdf=hdf[[c for c in cols if c in hdf.columns]].rename(columns={"timestamp":"Run","slate":"Slate","preset":"Preset","seed":"Seed","field_size":"Field","portfolio_size":"Portfolio","candidate_grade":"Health","runtime_seconds":"Seconds"})\n            st.dataframe(hdf,use_container_width=True,hide_index=True)\n\nif stage_times:\n'''
    if 'Run details + recent history' not in s:
        if results_anchor not in s: raise SystemExit('sim results anchor missing')
        s=s.replace(results_anchor,results_block,1)
    p.write_text(s,encoding='utf-8')


def patch_app():
    p=Path('app.py'); s=p.read_text(encoding='utf-8')
    imp='from nuke_bridge import portable_to_hub_lineup\n'
    add='from nuke_run_audit import reset_week_state\n'
    if add not in s:
        if imp not in s: raise SystemExit('app import anchor missing')
        s=s.replace(imp,imp+add,1)
    config='st.set_page_config(page_title="NUKE NFL DFS Hub", page_icon="🏈", layout="wide")\n'
    block=config+'''\nif st.session_state.pop("nuke_week_reset_notice",False):\n    st.success("New week started clean. Prior slate-specific Hub and SIM work was cleared.")\n\n'''
    if 'Prior slate-specific Hub and SIM work was cleared' not in s:
        if config not in s: raise SystemExit('app config anchor missing')
        s=s.replace(config,block,1)
    p.write_text(s,encoding='utf-8')

patch_sim(); patch_app(); print('release hardening patched')
