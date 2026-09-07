from pathlib import Path

p=Path('pages/6_SIM.py')
s=p.read_text()
s=s.replace(
'    presets={"QUICK":(250,350,50,200),"STANDARD":(400,750,75,350),"DEEP":(700,1200,100,500)}\n    candidates,sims,exposure_n,contest_iters=presets[preset]\n',
'    presets={"QUICK":(250,350,200),"STANDARD":(400,750,350),"DEEP":(700,1200,500)}\n    candidates,sims,contest_iters=presets[preset]\n'
)
s=s.replace('    exposure_n=st.number_input("Exposure sample",10,150,exposure_n,10,key="exposure_sample")\n','')
s=s.replace('        exposure=exposure_table(players,results,int(exposure_n))\n','        exposure=exposure_table(players,results,len(results))\n')
p.write_text(s)

p=Path('nuke_workspace.py')
s=p.read_text()
s=s.replace('    "dfs_site", "sim_preset", "candidate_lineups", "football_universes", "exposure_sample",\n','    "dfs_site", "sim_preset", "candidate_lineups", "football_universes",\n')
p.write_text(s)
