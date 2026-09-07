from pathlib import Path

p=Path('pages/6_SIM.py')
s=p.read_text()
old='''        scope=st.radio("Exposure scope",["Portfolio", "All contest-simmed lineups",f"Top {int(exposure_n)} NUKEM lineups"],horizontal=True)\n        er=portfolio if scope=="Portfolio" and portfolio is not None and not portfolio.empty else contest_results if scope.startswith("All") and contest_results is not None else results.head(int(exposure_n))\n'''
new='''        scope=st.radio("Exposure scope",["Portfolio", "All contest-simmed lineups", "All generated NUKE lineups"],horizontal=True)\n        if scope=="Portfolio" and portfolio is not None and not portfolio.empty:\n            er=portfolio\n        elif scope=="All contest-simmed lineups" and contest_results is not None and not contest_results.empty:\n            er=contest_results\n        else:\n            er=results\n'''
if old not in s:
    raise SystemExit('Exposure scope block not found')
s=s.replace(old,new)
p.write_text(s)
