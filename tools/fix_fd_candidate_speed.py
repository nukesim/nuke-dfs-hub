from pathlib import Path

# Fix SIM UI dispatch + platform label.
p=Path('pages/6_SIM.py')
s=p.read_text()
s=s.replace('st.write("1/5 · Generating correlated DraftKings candidates...")','st.write(f"1/5 · Generating correlated {get_platform(site).name} candidates...")')
s=s.replace('lineups=generate_lineups(players,int(candidates),int(min_salary),int(seed))','lineups=generate_lineups(players,int(candidates),int(min_salary),int(seed),site=site)')
p.write_text(s)

# Fix FanDuel fallback path in candidate engine. It was still hard-coded to DK's 50K cap
# and validating with the default DK site, which caused tens of thousands of guaranteed
# rejections when FD minimum salary was 59.4K.
p=Path('nuke_sim.py')
s=p.read_text()
s=s.replace('if total<min_salary or total>50000 or key in keys or not _valid_lineup(chosen,p,min_salary):continue',
            'if total<min_salary or total>salary_cap or key in keys or not _valid_lineup(chosen,p,min_salary,max_salary=salary_cap,site=site):continue')
p.write_text(s)
print('Fixed FanDuel candidate dispatch, label, fallback cap, and validation site')
