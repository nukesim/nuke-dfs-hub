from pathlib import Path
p=Path('pages/6_SIM.py')
s=p.read_text(encoding='utf-8')
old='''    min_salary=st.number_input("Minimum salary",cfg.min_salary_input,cfg.max_salary_input,cfg.default_min_salary,100,key=f"min_salary_{site}")\n    st.markdown("**LINEUP RULES**")\n    no_offense_vs_dst=st.checkbox(\n        "No players vs opposing defense", value=True, key="nuke_no_offense_vs_dst",\n        help="DraftKings and FanDuel. When checked, if a defense is selected, NUKE will not use any QB/RB/WR/TE from that defense's opponent in the same lineup. Changing this requires a new NUKE SIM run."\n    )\n    flex_position="ANY"\n'''
new='''    min_salary=st.number_input("Minimum salary",cfg.min_salary_input,cfg.max_salary_input,cfg.default_min_salary,100,key=f"min_salary_{site}")\n    flex_position="ANY"\n'''
if old not in s:
    raise SystemExit('sidebar rule block not found')
s=s.replace(old,new,1)
marker='''    st.caption(f"{PORTFOLIO_ENGINE_VERSION}: tournament upside + player/team/game concentration controls. Duplication is not used to select your portfolio.")\n\nst.subheader("🏈 Current Slate")\n'''
replacement='''    st.caption(f"{PORTFOLIO_ENGINE_VERSION}: tournament upside + player/team/game concentration controls. Duplication is not used to select your portfolio.")\n\nwith st.container(border=True):\n    st.markdown("### 🛡️ Lineup Rules")\n    no_offense_vs_dst=st.checkbox(\n        "No players vs opposing defense",\n        value=True,\n        key="nuke_no_offense_vs_dst",\n        help="DraftKings and FanDuel. When checked, NUKE will not place QB/RB/WR/TE from a defense's opponent in the same lineup as that defense. Changing this requires a new NUKE SIM run.",\n    )\n    st.caption("ON by default for both DraftKings and FanDuel. Example: if CHI D/ST is in a lineup, no offensive player from Chicago's opponent can appear in that lineup.")\n\nst.subheader("🏈 Current Slate")\n'''
if marker not in s:
    raise SystemExit('current slate marker not found')
s=s.replace(marker,replacement,1)
p.write_text(s,encoding='utf-8')
