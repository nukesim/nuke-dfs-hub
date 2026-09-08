from pathlib import Path
p=Path('nuke_sim.py')
s=p.read_text(encoding='utf-8')

# Add Streamlit imports once.
if 'import streamlit as st\n' not in s:
    s=s.replace('import pandas as pd\n','import pandas as pd\nimport inspect\nimport os\nimport streamlit as st\n',1)

marker='''AUTO_ROLE_MULTIPLIER = {"QB1":1.00,"QB2+":0.12,"RB1":1.08,"RB2":0.93,"RB3":0.78,"RB4+":0.62,"WR1":1.06,"WR2":1.00,"WR3":0.91,"WR4+":0.72,"TE1":1.04,"TE2+":0.76,"DST":1.00}\n'''
block='''AUTO_ROLE_MULTIPLIER = {"QB1":1.00,"QB2+":0.12,"RB1":1.08,"RB2":0.93,"RB3":0.78,"RB4+":0.62,"WR1":1.06,"WR2":1.00,"WR3":0.91,"WR4+":0.72,"TE1":1.04,"TE2+":0.76,"DST":1.00}\n\ndef _running_inside_nuke_sim():\n    try:\n        for fi in inspect.stack()[1:15]:\n            if os.path.basename(str(fi.filename or "")) == "6_SIM.py":\n                return True\n    except Exception:\n        return False\n    return False\n\ndef _render_engine_flex_control():\n    if not _running_inside_nuke_sim():\n        return\n    try:\n        with st.sidebar:\n            st.markdown("### FLEX RULE")\n            st.selectbox(\n                "FLEX position",\n                ["ANY","RB","WR","TE"],\n                key="nuke_engine_flex_position",\n                help="ANY leaves FLEX unrestricted. RB forces 3 RB total, WR forces 4 WR total, and TE forces 2 TE total. Applies to DraftKings and FanDuel. Rerun NUKE SIM after changing this.",\n            )\n    except Exception:\n        pass\n\n_render_engine_flex_control()\n'''
if '_render_engine_flex_control()' not in s:
    if marker not in s:
        raise SystemExit('top marker not found')
    s=s.replace(marker,block,1)

old='''    flex_position=str(flex_position or "ANY").upper().strip()\n'''
new='''    try:\n        engine_flex=str(st.session_state.get("nuke_engine_flex_position","") or "").upper().strip()\n    except Exception:\n        engine_flex=""\n    flex_position=str(engine_flex or flex_position or "ANY").upper().strip()\n'''
if old in s and 'engine_flex=str(st.session_state.get("nuke_engine_flex_position"' not in s:
    s=s.replace(old,new,1)
elif 'engine_flex=str(st.session_state.get("nuke_engine_flex_position"' not in s:
    raise SystemExit('generate_lineups FLEX marker not found')

p.write_text(s,encoding='utf-8')
