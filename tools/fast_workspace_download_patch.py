from pathlib import Path

p=Path('pages/6_SIM.py')
s=p.read_text(encoding='utf-8')
old='''        st.download_button("⬇️ SAVE WORKSPACE", workspace_bytes(st.session_state, st.session_state.get("nuke_workspace_slate_label","")), "nuke_sim_workspace.json", "application/json", use_container_width=True, key="save_nuke_workspace")\n'''
new='''        st.download_button("⬇️ SAVE WORKSPACE", workspace_bytes(st.session_state, st.session_state.get("nuke_workspace_slate_label","")), "nuke_sim_workspace.json", "application/json", use_container_width=True, key="save_nuke_workspace", on_click="ignore")\n'''
if old not in s:
    raise SystemExit('workspace download button target not found')
s=s.replace(old,new,1)
p.write_text(s,encoding='utf-8')
