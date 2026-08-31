from pathlib import Path

p=Path('app.py')
s=p.read_text()

old='''    cp=f("Position","Roster Position"); cnid=f("Name + ID","Name+ID","Name + Id")
    cn=f("Name"); cid=f("ID","Id"); cs=f("Salary"); cg=f("Game Info","GameInfo","game_id","Game","game")
'''
new='''    cp=f("Position","Roster Position"); cnid=f("Name + ID","Name+ID","Name + Id")
    cn=f("Name","Nickname"); cid=f("ID","Id"); cs=f("Salary"); cg=f("Game Info","GameInfo","game_id","Game","game")
'''
if old in s:
    s=s.replace(old,new,1)
elif new not in s:
    raise RuntimeError('normalize name anchor not found')

s=s.replace('if miss:raise ValueError("Missing DK columns: "+", ".join(miss))','if miss:raise ValueError(f"Missing {get_platform(SITE).name} columns: "+", ".join(miss))',1)

p.write_text(s)
print('FanDuel Hub parser fixed')
# trigger
