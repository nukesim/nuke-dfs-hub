from pathlib import Path
p=Path('pages/6_SIM.py')
s=p.read_text(encoding='utf-8')
old='''            preferred=["Portfolio Slot","QB","RB1","RB2","WR1","WR2","WR3","TE","FLEX","DST","FLEX Pos","Stack","Contest Rank","Sim ROI %","1st %","Top 0.1%","Top 1%","Cash %","Avg Finish","Avg Payout","Strongest Path","Secondary Path","Path Score","Lineup Thesis","NUKE Score","Median","Ceiling 95","Salary","Portfolio Reason"]\n'''
new='''            defense_col="D" if site=="FD" else "DST"\n            preferred=["Portfolio Slot","QB","RB1","RB2","WR1","WR2","WR3","TE","FLEX",defense_col,"FLEX Pos","Stack","Contest Rank","Sim ROI %","1st %","Top 0.1%","Top 1%","Cash %","Avg Finish","Avg Payout","Strongest Path","Secondary Path","Path Score","Lineup Thesis","NUKE Score","Median","Ceiling 95","Salary","Portfolio Reason"]\n'''
if old not in s:
    raise SystemExit('preferred export order block not found')
s=s.replace(old,new,1)
p.write_text(s,encoding='utf-8')