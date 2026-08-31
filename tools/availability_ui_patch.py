from pathlib import Path
p=Path('pages/6_SIM.py')
s=p.read_text()
imp='from nuke_availability import availability_status\n'
if imp not in s:
    s=s.replace('from fanduel_slate import load_fanduel_slate, has_fanduel_slate, FD_SLATE_LABEL\n','from fanduel_slate import load_fanduel_slate, has_fanduel_slate, FD_SLATE_LABEL\n'+imp,1)
anchor='''try:\n    players=prepare_slate(raw_slate,site=site)\nexcept Exception as e:\n    st.error(f"Could not read this slate: {e}")\n    st.stop()\n'''
insert=anchor+'''\n# Automated player availability protection. The scheduled feed is joined before the pool editor.\nplayers,availability_meta=availability_status(players)\nif availability_meta.get("loaded"):\n    red=int(availability_meta.get("red",0)); yellow=int(availability_meta.get("yellow",0))\n    updated=availability_meta.get("updated","")\n    if red:\n        st.warning(f"🚑 Player Availability · {red} OUT/inactive auto-excluded · {yellow} questionable/doubtful kept in pool" + (f" · Updated {updated}" if updated else ""))\n    else:\n        st.success(f"🚑 Player Availability ✓ · 0 OUT/inactive · {yellow} questionable/doubtful" + (f" · Updated {updated}" if updated else ""))\n    for warning in availability_meta.get("qb_warnings",[]):\n        st.warning(f"⚠️ Starting QB alert: {warning}")\nelse:\n    st.info("🚑 Player Availability feed not connected yet — no automatic injury exclusions are being applied.")\n'''
if 'players,availability_meta=availability_status(players)' not in s:
    if anchor not in s: raise RuntimeError('prepare_slate anchor missing')
    s=s.replace(anchor,insert,1)
# Default red-status players to excluded, but never override a user's existing choice.
old='''    pool_state.setdefault(key,{"include":True,"role":"AUTO","usage":1.0})'''
new='''    auto_exclude=bool(row.get("Auto Exclude",False))\n    pool_state.setdefault(key,{"include":not auto_exclude,"role":"AUTO","usage":1.0})'''
if old in s:
    s=s.replace(old,new,1)
# Surface status in the game editor without making it editable.
old2='''rows.append({"_row":int(idx),"_key":key,"Include":bool(cfg.get("include",True)),"Pos":row.Position,"Player":row.Name,"Salary":int(row.Salary),"Auto Role":row.auto_role,"Role":str(cfg.get("role","AUTO")),"Usage x":float(cfg.get("usage",1.0))})'''
new2='''rows.append({"_row":int(idx),"_key":key,"Include":bool(cfg.get("include",True)),"Pos":row.Position,"Player":row.Name,"Status":str(row.get("Availability","Available")),"Salary":int(row.Salary),"Auto Role":row.auto_role,"Role":str(cfg.get("role","AUTO")),"Usage x":float(cfg.get("usage",1.0))})'''
if old2 in s:
    s=s.replace(old2,new2,1)
s=s.replace('disabled=["Pos","Player","Salary","Auto Role"],','disabled=["Pos","Player","Status","Salary","Auto Role"],',1)
s=s.replace('column_order=["Include","Pos","Player","Salary","Auto Role","Role","Usage x"],','column_order=["Include","Pos","Player","Status","Salary","Auto Role","Role","Usage x"],',1)
needle='''"Player":st.column_config.TextColumn("Player",width="medium"),'''
if needle in s and '"Status":st.column_config.TextColumn' not in s:
    s=s.replace(needle,needle+'\n                        "Status":st.column_config.TextColumn("Status",width="small",help="Automated injury/availability status. OUT/inactive players default to excluded; questionable players remain available."),',1)
p.write_text(s)
print('patched availability protection into SIM')
