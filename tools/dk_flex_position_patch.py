from pathlib import Path
p=Path('pages/6_SIM.py')
s=p.read_text(encoding='utf-8')
old='''    flex_position="ANY"\n    if site=="FD":\n        flex_position=st.selectbox(\n            "FLEX position", ["ANY","RB","WR","TE"], index=0, key="nuke_fd_flex_position",\n            help="FanDuel only. Choose RB to force every generated lineup to use a running back in FLEX (3 RB total). Changing this requires a new NUKE SIM run."\n        )\n'''
new='''    flex_position=st.selectbox(\n        "FLEX position", ["ANY","RB","WR","TE"], index=0, key=f"nuke_flex_position_{site}",\n        help=(\n            "Choose which position must occupy FLEX. RB = 3 RB total, WR = 4 WR total, TE = 2 TE total. "\n            "ANY leaves FLEX unrestricted. Changing this requires a new NUKE SIM run."\n        )\n    )\n'''
if old not in s:
    raise SystemExit('FLEX block not found')
s=s.replace(old,new,1)
p.write_text(s,encoding='utf-8')
