from pathlib import Path

p=Path('pages/6_SIM.py')
s=p.read_text(encoding='utf-8')
start='selected_game=st.selectbox(\n'
end='st.session_state["nuke_pregame_pool"]=updated_state\n'
if start not in s or end not in s:
    raise SystemExit('player-pool block markers not found')
pre,rest=s.split(start,1)
body,post=rest.split(end,1)
body=start+body
indented='\n'.join(('    '+line if line else line) for line in body.split('\n'))
summary='''with pool_current_tab:\n    st.markdown("### 👥 Current Player Pool")\n    st.caption("A clean snapshot of everyone currently eligible to enter NUKE lineups. Apply game changes, then return here to verify the pool before running the SIM.")\n    pool_rows=[]\n    for _,row in players.iterrows():\n        key=str(row.ID) if str(row.ID) else f"{row.Name}|{row.Team}|{row.Position}|{int(row.Salary)}"\n        pcfg=updated_state.get(key,{"include":True,"role":"AUTO","usage":1.0})\n        if not bool(pcfg.get("include",True)):\n            continue\n        override=str(pcfg.get("role","AUTO")).upper()\n        model_role=str(getattr(row,"auto_role","AUTO"))\n        role=model_role if override=="AUTO" else override\n        pool_rows.append({\n            "Player":str(row.Name),\n            "Team":str(row.Team),\n            "Pos":str(row.Position),\n            "Salary":int(row.Salary),\n            "Role":role,\n            "Usage":float(pcfg.get("usage",1.0)),\n        })\n    current_pool=pd.DataFrame(pool_rows)\n    if current_pool.empty:\n        st.warning("No players are currently included in the SIM pool.")\n    else:\n        pos_order=["QB","RB","WR","TE","DST"]\n        counts=current_pool["Pos"].value_counts().to_dict()\n        m0,m1,m2,m3,m4,m5=st.columns(6)\n        m0.metric("Active",f"{len(current_pool):,}")\n        for col,pos in zip([m1,m2,m3,m4,m5],pos_order):\n            col.metric(pos,f"{int(counts.get(pos,0)):,}")\n        st.markdown("#### Active by Position")\n        pos_tabs=st.tabs([f"{pos} · {int(counts.get(pos,0))}" for pos in pos_order])\n        for tab,pos in zip(pos_tabs,pos_order):\n            with tab:\n                view=current_pool[current_pool["Pos"].eq(pos)].copy()\n                if view.empty:\n                    st.caption(f"No {pos} players are currently included.")\n                    continue\n                view=view.sort_values(["Salary","Team","Player"],ascending=[False,True,True])\n                view["Salary"]=view["Salary"].map(lambda x:f"${int(x):,}")\n                view["Usage"]=view["Usage"].map(lambda x:f"{float(x):.2f}x")\n                st.dataframe(view[["Player","Team","Salary","Role","Usage"]],use_container_width=True,hide_index=True,height=min(520,70+35*len(view)))\n'''
replacement='pool_game_tab,pool_current_tab=st.tabs(["🏈 Game-by-Game","👥 Current Player Pool"])\nwith pool_game_tab:\n'+indented+'\n'+summary+end
s=pre+replacement+post
p.write_text(s,encoding='utf-8')
