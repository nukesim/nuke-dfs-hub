from pathlib import Path

# Main NUKE SIM UI: FanDuel-only FLEX position lock.
p = Path('pages/6_SIM.py')
s = p.read_text()
s = s.replace(
'    min_salary=st.number_input("Minimum salary",cfg.min_salary_input,cfg.max_salary_input,cfg.default_min_salary,100,key=f"min_salary_{site}")\n    candidates=st.number_input("Candidate lineups",100,5000,candidates,100,key="candidate_lineups")',
'    min_salary=st.number_input("Minimum salary",cfg.min_salary_input,cfg.max_salary_input,cfg.default_min_salary,100,key=f"min_salary_{site}")\n    flex_position="ANY"\n    if site=="FD":\n        flex_position=st.selectbox(\n            "FLEX position", ["ANY","RB","WR","TE"], index=0, key="nuke_fd_flex_position",\n            help="FanDuel only. Choose RB to force every generated lineup to use a running back in FLEX (3 RB total). Changing this requires a new NUKE SIM run."\n        )\n    candidates=st.number_input("Candidate lineups",100,5000,candidates,100,key="candidate_lineups")'
)
s = s.replace(
'        lineups=generate_lineups(players,int(candidates),int(min_salary),int(seed),site=site)',
'        lineups=generate_lineups(players,int(candidates),int(min_salary),int(seed),site=site,flex_position=flex_position if site=="FD" else None)'
)
p.write_text(s)

# Candidate engine: optionally force the one extra RB/WR/TE roster spot.
p = Path('nuke_sim.py')
s = p.read_text()
s = s.replace(
'def generate_lineups(players,n_lineups=600,min_salary=None,seed=26,site="DK"):',
'def generate_lineups(players,n_lineups=600,min_salary=None,seed=26,site="DK",flex_position=None):'
)
s = s.replace(
'    cfg=get_platform(site); salary_cap=int(cfg.salary_cap); min_salary=int(cfg.default_min_salary if min_salary is None else min_salary); n_lineups=int(n_lineups)\n',
'    cfg=get_platform(site); salary_cap=int(cfg.salary_cap); min_salary=int(cfg.default_min_salary if min_salary is None else min_salary); n_lineups=int(n_lineups)\n    flex_position=str(flex_position or "ANY").upper().strip()\n    if flex_position not in {"ANY","RB","WR","TE"}: flex_position="ANY"\n'
)
s = s.replace(
'        ids=flex[(sal[flex]>=lo)&(sal[flex]<=hi)&(~np.isin(flex,chosen))]\n        if not len(ids):continue',
'        ids=flex[(sal[flex]>=lo)&(sal[flex]<=hi)&(~np.isin(flex,chosen))]\n        if flex_position!="ANY":\n            ids=ids[pos[ids]==flex_position]\n        if not len(ids):continue'
)
s = s.replace(
'        if not(counts["QB"]==1 and counts["RB"]>=2 and counts["WR"]>=3 and counts["TE"]>=1 and counts["DST"]==1):continue\n',
'        if not(counts["QB"]==1 and counts["RB"]>=2 and counts["WR"]>=3 and counts["TE"]>=1 and counts["DST"]==1):continue\n        if flex_position!="ANY" and counts.get(flex_position,0)!={"RB":3,"WR":4,"TE":2}[flex_position]:continue\n'
)
s = s.replace(
'            if total<min_salary or total>salary_cap or key in keys or not _valid_lineup(chosen,p,min_salary,max_salary=salary_cap,site=site):continue\n',
'            if total<min_salary or total>salary_cap or key in keys or not _valid_lineup(chosen,p,min_salary,max_salary=salary_cap,site=site):continue\n            if flex_position!="ANY":\n                counts={k:int(np.sum(pos[arr]==k)) for k in ["RB","WR","TE"]}\n                if counts.get(flex_position,0)!={"RB":3,"WR":4,"TE":2}[flex_position]:continue\n'
)
p.write_text(s)

# Persist control in NUKE workspace.
p = Path('nuke_workspace.py')
s = p.read_text()
s = s.replace(
'    "min_salary_DK", "min_salary_FD",\n',
'    "min_salary_DK", "min_salary_FD", "nuke_fd_flex_position",\n'
)
p.write_text(s)

# Guide/About: explain main-slate FanDuel FLEX lock and rerun requirement.
p = Path('pages/11_GUIDE.py')
s = p.read_text()
needle='        st.info("NUKE Sim is designed to model ranges of outcomes, not predict one exact future result.")\n'
replacement='        st.info("NUKE Sim is designed to model ranges of outcomes, not predict one exact future result.")\n        st.caption("FanDuel: use **FLEX position** to choose Any, RB, WR, or TE. Selecting RB forces every generated lineup to use 3 RBs, placing an RB in FLEX. Because this changes candidate construction, rerun NUKE Sim after changing the FLEX position setting.")\n'
if needle in s and 'FanDuel: use **FLEX position**' not in s:
    s=s.replace(needle,replacement)
p.write_text(s)
