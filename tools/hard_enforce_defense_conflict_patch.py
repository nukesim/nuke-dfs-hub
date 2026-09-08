from pathlib import Path
p=Path('nuke_sim.py')
s=p.read_text(encoding='utf-8')
old='def _valid_lineup(indices,p,min_salary,max_salary=None,site="DK",no_offense_vs_dst=False):'
new='def _valid_lineup(indices,p,min_salary,max_salary=None,site="DK",no_offense_vs_dst=True):'
if old in s:
    s=s.replace(old,new,1)
old2='def generate_lineups(players,n_lineups=600,min_salary=None,seed=26,site="DK",flex_position=None,locked_indices=None,no_offense_vs_dst=False):'
new2='def generate_lineups(players,n_lineups=600,min_salary=None,seed=26,site="DK",flex_position=None,locked_indices=None,no_offense_vs_dst=True):'
if old2 in s:
    s=s.replace(old2,new2,1)
needle='''    rng=np.random.default_rng(seed); p=players.reset_index(drop=True)\n'''
repl='''    # Hard rule: offense vs opposing defense is never allowed on DK or FD.\n    # Keep the argument for backward compatibility, but do not allow callers to disable the rule.\n    no_offense_vs_dst=True\n    rng=np.random.default_rng(seed); p=players.reset_index(drop=True)\n'''
if needle not in s:
    raise SystemExit('generate_lineups insertion point not found')
s=s.replace(needle,repl,1)
p.write_text(s,encoding='utf-8')