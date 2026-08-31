from pathlib import Path

p=Path('pages/6_SIM.py')
s=p.read_text()
old='lineups=generate_lineups(players,int(candidates),int(min_salary),int(seed))'
new='lineups=generate_lineups(players,int(candidates),int(min_salary),int(seed),site=site)'
if old not in s and new not in s:
    raise RuntimeError('candidate generation call not found')
s=s.replace(old,new)
s=s.replace('st.write("1/5 · Generating correlated DraftKings candidates...")','st.write(f"1/5 · Generating correlated {get_platform(site).name} candidates...")')
p.write_text(s)
print('Patched SIM candidate generation to pass selected platform')
