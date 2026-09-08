from pathlib import Path

# pages/6_SIM.py
p=Path('pages/6_SIM.py')
s=p.read_text(encoding='utf-8')
old='''    flex_position="ANY"\n    no_offense_vs_dst=False\n    if site=="FD":\n        flex_position=st.selectbox(\n            "FLEX position", ["ANY","RB","WR","TE"], index=0, key="nuke_fd_flex_position",\n            help="FanDuel only. Choose RB to force every generated lineup to use a running back in FLEX (3 RB total). Changing this requires a new NUKE SIM run."\n        )\n        no_offense_vs_dst=st.checkbox(\n            "No players vs opposing defense", value=False, key="nuke_fd_no_offense_vs_dst",\n            help="When checked, if a defense is selected, NUKE will not use any QB/RB/WR/TE from that defense's opponent in the same lineup. Changing this requires a new NUKE SIM run."\n        )\n'''
new='''    flex_position="ANY"\n    if site=="FD":\n        flex_position=st.selectbox(\n            "FLEX position", ["ANY","RB","WR","TE"], index=0, key="nuke_fd_flex_position",\n            help="FanDuel only. Choose RB to force every generated lineup to use a running back in FLEX (3 RB total). Changing this requires a new NUKE SIM run."\n        )\n    no_offense_vs_dst=st.checkbox(\n        "No players vs opposing defense", value=True, key="nuke_no_offense_vs_dst",\n        help="DraftKings and FanDuel. When checked, if a defense is selected, NUKE will not use any QB/RB/WR/TE from that defense's opponent in the same lineup. Changing this requires a new NUKE SIM run."\n    )\n'''
if old not in s:
    raise SystemExit('sidebar target not found')
s=s.replace(old,new,1)
p.write_text(s,encoding='utf-8')

# nuke_workspace.py
p=Path('nuke_workspace.py')
s=p.read_text(encoding='utf-8')
old='''    "min_salary_DK", "min_salary_FD", "nuke_fd_flex_position",\n'''
new='''    "min_salary_DK", "min_salary_FD", "nuke_fd_flex_position", "nuke_no_offense_vs_dst",\n'''
if old not in s:
    raise SystemExit('workspace target not found')
s=s.replace(old,new,1)
p.write_text(s,encoding='utf-8')

# Guide/About
p=Path('pages/11_GUIDE.py')
s=p.read_text(encoding='utf-8')
needle='''        st.caption("FanDuel: use **FLEX position** to choose Any, RB, WR, or TE. Selecting RB forces every generated lineup to use 3 RBs, placing an RB in FLEX. Because this changes candidate construction, rerun NUKE Sim after changing the FLEX position setting.")\n'''
replacement=needle+'''        st.caption("DraftKings & FanDuel: **No players vs opposing defense** is enabled by default. When checked, a lineup containing a defense cannot contain any QB/RB/WR/TE from that defense's opponent. Turn it off only if you intentionally want offense-vs-defense combinations, then rerun NUKE Sim.")\n'''
if needle not in s:
    raise SystemExit('guide target not found')
s=s.replace(needle,replacement,1)
p.write_text(s,encoding='utf-8')
