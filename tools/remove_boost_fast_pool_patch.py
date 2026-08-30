from pathlib import Path
p=Path('pages/6_SIM.py')
s=p.read_text(encoding='utf-8')
# Remove boost helpers.
a=s.find('BOOST_VALUES=')
b=s.find('st.set_page_config',a)
if a!=-1 and b!=-1: s=s[:a]+s[b:]
s=s.replace('Work the slate one game at a time. Include/remove players and use the single Boost control: ▼ fades, ▲ boosts, up to 3x. It changes candidate-lineup generation only — it does NOT change the player\'s simulated fantasy points.','Work the slate one game at a time. Include/remove players, adjust role if needed, then apply the game once.')
s=s.replace('pool_state.setdefault(key,{"include":True,"boost":0.0,"role":"AUTO","usage":1.0})','pool_state.setdefault(key,{"include":True,"role":"AUTO","usage":1.0})')
s=s.replace('widths=[.7,.6,2.35,.9,.9,3.2,1.15,1.0]','widths=[.7,.6,2.5,.9,.9,1.15,1.0]')
s=s.replace('["Include","Pos","Player","Salary","Auto Role","Boost","Role","Usage x"]','["Include","Pos","Player","Salary","Auto Role","Role","Usage x"]')
s=s.replace('cfg=updated_state.get(key,{"include":True,"boost":0.0,"role":"AUTO","usage":1.0})','cfg=updated_state.get(key,{"include":True,"role":"AUTO","usage":1.0})')
start='''                        boost=cols[5].segmented_control(\n'''
if start in s:
    i=s.index(start)
    j=s.index('                        role_value=',i)
    s=s[:i]+s[j:]
s=s.replace('role=cols[6].selectbox','role=cols[5].selectbox')
s=s.replace('usage=cols[7].number_input','usage=cols[6].number_input')
s=s.replace('pending_rows.append({"_key":key,"Include":include,"Boost":clean_boost(boost),"Role":role,"Usage x":float(usage)})','pending_rows.append({"_key":key,"Include":include,"Role":role,"Usage x":float(usage)})')
s=s.replace('updated_state[key]={"include":include,"boost":float(erow["Boost"]),"role":str(erow["Role"]),"usage":float(erow["Usage x"])}','updated_state[key]={"include":include,"role":str(erow["Role"]),"usage":float(erow["Usage x"])}')
s=s.replace('cfg=updated_state.get(key,{"include":True,"boost":0.0,"role":"AUTO","usage":1.0})','cfg=updated_state.get(key,{"include":True,"role":"AUTO","usage":1.0})')
s=s.replace('        r["generation_boost"]=float(cfg.get("boost",0.0))\n','')
s=s.replace('''if not players.empty:\n    gb=pd.to_numeric(players.generation_boost,errors="coerce").fillna(0)\n    st.caption(f"Active pool: {len(players):,} players · Boosted: {(gb>0).sum():,} · Reduced/Faded: {(gb<0).sum():,}")\n''','''if not players.empty:\n    st.caption(f"Active pool: {len(players):,} players")\n''')
p.write_text(s,encoding='utf-8')
