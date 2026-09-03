from pathlib import Path

path=Path("pages/6_SIM.py")
text=path.read_text(encoding="utf-8")
old='''c1,c2,c3,c4,c5=st.columns(5)\nc1.metric("Players",len(players))\nc2.metric("Teams",players.Team.nunique())\nc3.metric("Games",players.Game.nunique())\nc4.metric("Salary Floor",f"${int(min_salary):,}")\nc5.metric("Slate",slate_source)\n'''
new='''c1,c2,c3,c4=st.columns(4)\nc1.metric("Players",len(players))\nc2.metric("Teams",players.Team.nunique())\nc3.metric("Games",players.Game.nunique())\nc4.metric("Salary Floor",f"${int(min_salary):,}")\nst.markdown(f"**Slate:** {slate_source}")\n'''
if old not in text:
    raise SystemExit("Slate metric block not found; refusing to guess")
path.write_text(text.replace(old,new,1),encoding="utf-8")
print("Updated NUKE SIM slate summary layout")
