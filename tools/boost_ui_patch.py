from pathlib import Path

p = Path("pages/6_SIM.py")
s = p.read_text(encoding="utf-8")

anchor = 'from nuke_game_pool import game_environment, style_environment\n\n'
insert = '''from nuke_game_pool import game_environment, style_environment\n\nTAKE_LEVELS=[\n    "🧊 -3 Hard Fade",\n    "⬇️⬇️ -2 Fade",\n    "⬇️ -1 Slight Fade",\n    "— 0 Neutral",\n    "⬆️ +1 Boost",\n    "⬆️⬆️ +2 Strong Boost",\n    "🚀 +3 Smash",\n]\nTAKE_TO_BOOST={label:float(level) for level,label in zip(range(-3,4),TAKE_LEVELS)}\n\ndef boost_to_take(value):\n    try:\n        level=max(-3,min(3,int(round(float(value)))))\n    except Exception:\n        level=0\n    return TAKE_LEVELS[level+3]\n\ndef take_to_boost(value):\n    return float(TAKE_TO_BOOST.get(str(value),0.0))\n\n'''
if anchor not in s:
    raise SystemExit("import anchor not found")
s = s.replace(anchor, insert, 1)

s = s.replace(
    'st.caption("Work the slate one game at a time. Include/remove players and add a personal pre-sim Boost. Boost changes candidate-lineup generation only — it does NOT change the player\'s simulated fantasy points.")',
    'st.caption("Work the slate one game at a time. Include/remove players and choose a Take level from Hard Fade to Smash. Takes change candidate-lineup generation only — they do NOT change the player\'s simulated fantasy points.")',
    1,
)

old_row='rows.append({"_row":int(idx),"_key":key,"Include":bool(cfg.get("include",True)),"Pos":row.Position,"Player":row.Name,"Salary":int(row.Salary),"Auto Role":row.auto_role,"Boost":float(cfg.get("boost",0.0)),"Role":str(cfg.get("role","AUTO")),"Usage x":float(cfg.get("usage",1.0))})'
new_row='rows.append({"_row":int(idx),"_key":key,"Include":bool(cfg.get("include",True)),"Pos":row.Position,"Player":row.Name,"Salary":int(row.Salary),"Auto Role":row.auto_role,"Take":boost_to_take(cfg.get("boost",0.0)),"Role":str(cfg.get("role","AUTO")),"Usage x":float(cfg.get("usage",1.0))})'
if old_row not in s:
    raise SystemExit("row anchor not found")
s=s.replace(old_row,new_row,1)

old_order='column_order=["Include","Pos","Player","Salary","Auto Role","Boost","Role","Usage x"],'
new_order='column_order=["Include","Pos","Player","Salary","Auto Role","Take","Role","Usage x"],'
if old_order not in s:
    raise SystemExit("column order anchor not found")
s=s.replace(old_order,new_order,1)

old_col='"Boost":st.column_config.NumberColumn("Boost",min_value=-3.0,max_value=3.0,step=1.0,format="%.0f",width="small",help="Personal preference only. Changes candidate generation, not simulated fantasy points."),'
new_col='"Take":st.column_config.SelectboxColumn("Take",options=TAKE_LEVELS,width="medium",help="Click a level: Hard Fade (-3), Fade (-2), Slight Fade (-1), Neutral, Boost (+1), Strong Boost (+2), or Smash (+3). Changes candidate generation only, not simulated fantasy points."),'
if old_col not in s:
    raise SystemExit("Boost column anchor not found")
s=s.replace(old_col,new_col,1)

old_save='updated_state[key]={"include":include,"boost":float(erow["Boost"]),"role":str(erow["Role"]),"usage":float(erow["Usage x"])}'
new_save='updated_state[key]={"include":include,"boost":take_to_boost(erow["Take"]),"role":str(erow["Role"]),"usage":float(erow["Usage x"])}'
if old_save not in s:
    raise SystemExit("save anchor not found")
s=s.replace(old_save,new_save,1)

p.write_text(s,encoding="utf-8")
print("patched boost UI to click-select Take levels")
