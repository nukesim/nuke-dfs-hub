from pathlib import Path

# Engine: enforce FanDuel max 4 players/team and optional zero offense vs opposing DST.
p=Path('nuke_sim.py')
s=p.read_text()
s=s.replace(
'''def _valid_lineup(indices,p,min_salary,max_salary=None,site="DK"):
    if max_salary is None: max_salary=get_platform(site).salary_cap
    if len(indices)!=9 or len(set(indices))!=9:return False
    r=p.iloc[indices]; sal=int(r.Salary.sum()); c=r.Position.value_counts().to_dict()
    if sal<min_salary or sal>max_salary:return False
    if not(c.get("QB",0)==1 and c.get("RB",0)>=2 and c.get("WR",0)>=3 and c.get("TE",0)>=1 and c.get("DST",0)==1):return False
    q=r[r.Position.eq("QB")]; return not("auto_qb_eligible" in q.columns and not bool(q.iloc[0].auto_qb_eligible))

def generate_lineups(players,n_lineups=600,min_salary=None,seed=26,site="DK",flex_position=None,locked_indices=None):''',
'''def _valid_lineup(indices,p,min_salary,max_salary=None,site="DK",no_offense_vs_dst=False):
    if max_salary is None: max_salary=get_platform(site).salary_cap
    if len(indices)!=9 or len(set(indices))!=9:return False
    r=p.iloc[indices]; sal=int(r.Salary.sum()); c=r.Position.value_counts().to_dict()
    if sal<min_salary or sal>max_salary:return False
    if not(c.get("QB",0)==1 and c.get("RB",0)>=2 and c.get("WR",0)>=3 and c.get("TE",0)>=1 and c.get("DST",0)==1):return False
    if get_platform(site).code=="FD" and int(r.Team.value_counts().max())>4:return False
    if no_offense_vs_dst:
        d=r[r.Position.eq("DST")]
        if not d.empty:
            dr=d.iloc[0]
            if ((r.Game.eq(dr.Game)) & (~r.Team.eq(dr.Team)) & r.Position.ne("DST")).any():return False
    q=r[r.Position.eq("QB")]; return not("auto_qb_eligible" in q.columns and not bool(q.iloc[0].auto_qb_eligible))

def generate_lineups(players,n_lineups=600,min_salary=None,seed=26,site="DK",flex_position=None,locked_indices=None,no_offense_vs_dst=False):''')
# Every full validator call gets the toggle.
s=s.replace('max_salary=salary_cap,site=site):continue', 'max_salary=salary_cap,site=site,no_offense_vs_dst=no_offense_vs_dst):continue')
# Existing DST rule permits one opposing player. Make threshold configurable.
s=s.replace('if opposing>=2:continue', 'if opposing>=(1 if no_offense_vs_dst else 2):continue')
s=s.replace('if current_opp>=1:\n                ids=ids[~((game[ids]==game[d])&(team[ids]!=team[d]))]', 'if current_opp>=(0 if no_offense_vs_dst else 1):\n                ids=ids[~((game[ids]==game[d])&(team[ids]!=team[d]))]')
# Fast-path validation also needs FD's max-four-per-team rule.
needle='''        if not(counts["QB"]==1 and counts["RB"]>=2 and counts["WR"]>=3 and counts["TE"]>=1 and counts["DST"]==1):continue
        if flex_position!="ANY"'''
repl='''        if not(counts["QB"]==1 and counts["RB"]>=2 and counts["WR"]>=3 and counts["TE"]>=1 and counts["DST"]==1):continue
        if get_platform(site).code=="FD":
            team_counts=pd.Series(team[arr]).value_counts()
            if not team_counts.empty and team_counts.max()>4:continue
        if flex_position!="ANY"'''
s=s.replace(needle,repl)
p.write_text(s)

# UI: sidebar toggle and pass it into candidate generation.
p=Path('pages/6_SIM.py')
s=p.read_text()
needle='''    flex_position="ANY"
    if site=="FD":
        flex_position=st.selectbox(
            "FLEX position", ["ANY","RB","WR","TE"], index=0, key="nuke_fd_flex_position",
            help="FanDuel only. Choose RB to force every generated lineup to use a running back in FLEX (3 RB total). Changing this requires a new NUKE SIM run."
        )'''
repl='''    flex_position="ANY"
    no_offense_vs_dst=False
    if site=="FD":
        flex_position=st.selectbox(
            "FLEX position", ["ANY","RB","WR","TE"], index=0, key="nuke_fd_flex_position",
            help="FanDuel only. Choose RB to force every generated lineup to use a running back in FLEX (3 RB total). Changing this requires a new NUKE SIM run."
        )
        no_offense_vs_dst=st.checkbox(
            "No players vs opposing defense", value=False, key="nuke_fd_no_offense_vs_dst",
            help="When checked, if a defense is selected, NUKE will not use any QB/RB/WR/TE from that defense's opponent in the same lineup. Changing this requires a new NUKE SIM run."
        )'''
s=s.replace(needle,repl)
s=s.replace('lineups=generate_lineups(players,generation_target,int(min_salary),int(seed),site=site,locked_indices=locked_indices)', 'lineups=generate_lineups(players,generation_target,int(min_salary),int(seed),site=site,locked_indices=locked_indices,no_offense_vs_dst=no_offense_vs_dst)')
p.write_text(s)
