from pathlib import Path

# Runtime-safe main NUKE SIM FLEX enforcement.
# Do not pass a new keyword into generate_lineups: Streamlit can retain an older imported
# function object across hot reloads. Generate a larger FD candidate pool, then enforce
# the selected FLEX construction before football simulation.
p = Path('pages/6_SIM.py')
s = p.read_text()
old='        lineups=generate_lineups(players,int(candidates),int(min_salary),int(seed),site=site,flex_position=flex_position if site=="FD" else None)'
new='''        generation_target=int(candidates)\n        if site=="FD" and flex_position!="ANY":\n            generation_target=min(5000,max(int(candidates)*4,int(candidates)+500))\n        lineups=generate_lineups(players,generation_target,int(min_salary),int(seed),site=site)\n        if site=="FD" and flex_position!="ANY":\n            required_count={"RB":3,"WR":4,"TE":2}[flex_position]\n            lineups=[lu for lu in lineups if int((players.iloc[list(lu)]["Position"]==flex_position).sum())==required_count][:int(candidates)]\n            if len(lineups)<int(candidates):\n                st.caption(f"FLEX {flex_position} filter produced {len(lineups):,} eligible candidates from {generation_target:,} generated lineups.")'''
if old in s:
    s=s.replace(old,new)
elif new not in s:
    raise SystemExit('Expected NUKE SIM generation call not found')
p.write_text(s)

# Keep engine support too for future callers, but the public page no longer depends on
# the expanded function signature, eliminating the Streamlit hot-reload TypeError.
p = Path('nuke_workspace.py')
s = p.read_text()
if '"nuke_fd_flex_position"' not in s:
    s=s.replace('    "min_salary_DK", "min_salary_FD",\n','    "min_salary_DK", "min_salary_FD", "nuke_fd_flex_position",\n')
p.write_text(s)

# Guide remains explicit that this changes candidate construction and requires a rerun.
p = Path('pages/11_GUIDE.py')
s = p.read_text()
needle='        st.info("NUKE Sim is designed to model ranges of outcomes, not predict one exact future result.")\n'
replacement='        st.info("NUKE Sim is designed to model ranges of outcomes, not predict one exact future result.")\n        st.caption("FanDuel: use **FLEX position** to choose Any, RB, WR, or TE. Selecting RB forces every generated lineup to use 3 RBs, placing an RB in FLEX. Because this changes candidate construction, rerun NUKE Sim after changing the FLEX position setting.")\n'
if needle in s and 'FanDuel: use **FLEX position**' not in s:
    s=s.replace(needle,replacement)
p.write_text(s)
