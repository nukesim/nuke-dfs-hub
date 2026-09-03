from pathlib import Path

path=Path("pages/6_SIM.py")
text=path.read_text(encoding="utf-8")

old='''        game_action=st.selectbox("Game bulk action",["No bulk change","✅ Include entire game","🚫 Exclude entire game"],key=f"game_bulk_{str(game)}_{editor_version}")
        visible_teams=teams[:2]
        team_cols=st.columns(len(visible_teams)) if visible_teams else [st.container()]
        pending_by_team={}
        team_actions={}
        for team_col,team in zip(team_cols,visible_teams):
            tp=gp[gp.Team.eq(team)].copy()
            pos_order={"QB":0,"RB":1,"WR":2,"TE":3,"DST":4}
            tp["_pos_order"]=tp.Position.map(pos_order).fillna(9)
            tp=tp.sort_values(["_pos_order","Salary"],ascending=[True,False])
            trow=ge[ge.Team.eq(team)].iloc[0] if not ge.empty and ge.Team.eq(team).any() else None
            with team_col:
                if trow is not None:
                    st.markdown(f"### {team} · {float(trow['Team Total']):.1f} · Rank #{int(trow['Team Total Rank'])}")
                else:
                    st.markdown(f"### {team}")
                team_actions[team]=st.selectbox(f"{team} bulk action",["No bulk change","✅ Include all","🚫 Exclude all"],key=f"team_bulk_{str(game)}_{team}_{editor_version}",label_visibility="collapsed")
                rows=[]
                for idx,row in tp.iterrows():
                    key=str(row.ID) if str(row.ID) else f"{row.Name}|{row.Team}|{row.Position}|{int(row.Salary)}"
                    cfg=updated_state.get(key,{"include":True,"role":"AUTO","usage":1.0})
                    rows.append({"_row":int(idx),"_key":key,"Include":bool(cfg.get("include",True)),"Pos":row.Position,"Player":row.Name,"Status":str(row.get("Availability","Available")),"Salary":int(row.Salary),"Auto Role":row.auto_role,"Role":str(cfg.get("role","AUTO")),"Usage x":float(cfg.get("usage",1.0))})
                edit_df=pd.DataFrame(rows).set_index("_row")
                edited_team=st.data_editor(
                    edit_df.drop(columns=["_key"]),use_container_width=True,hide_index=True,
                    disabled=["Pos","Player","Status","Salary","Auto Role"],
                    column_order=["Include","Pos","Player","Status","Salary","Auto Role","Role","Usage x"],
                    column_config={
                        "Include":st.column_config.CheckboxColumn("Include",width="small"),
                        "Pos":st.column_config.TextColumn("Pos",width="small"),
                        "Player":st.column_config.TextColumn("Player",width="medium"),
                        "Status":st.column_config.TextColumn("Status",width="small",help="Automated injury/availability status. OUT/inactive players default to excluded; questionable players remain available."),
                        "Salary":st.column_config.NumberColumn("Salary",format="$%d",width="small"),
                        "Auto Role":st.column_config.TextColumn("Auto Role",width="small"),
                        "Role":st.column_config.SelectboxColumn("Role",options=["AUTO","QB1","RB1","RB2","RB3","WR1","WR2","WR3","TE1","BACKUP"],width="small"),
                        "Usage x":st.column_config.NumberColumn("Usage x",min_value=.25,max_value=2.25,step=.05,format="%.2f",width="small",help="Changes the football simulation itself. Leave at 1.00 unless you believe actual usage changes."),
                    },key=f"game_pool_{str(game)}_{team}_{editor_version}"
                )
                pending_by_team[team]=(edit_df,edited_team)
                excluded_count=sum(not bool(updated_state.get(str(r.ID) if str(r.ID) else f"{r.Name}|{r.Team}|{r.Position}|{int(r.Salary)}",{}).get("include",True)) for _,r in tp.iterrows())
                if excluded_count:
                    st.caption(f"🚫 Currently excluded: {excluded_count}")
'''

new='''        st.markdown("**Game Action**")
        game_action=st.selectbox("Game bulk action",["No bulk change","✅ Include entire game","🚫 Exclude entire game"],key=f"game_bulk_{str(game)}_{editor_version}",label_visibility="collapsed")
        visible_teams=teams[:2]
        team_cols=st.columns(len(visible_teams),gap="medium") if visible_teams else [st.container()]
        pending_by_team={}
        team_actions={}
        for team_col,team in zip(team_cols,visible_teams):
            tp=gp[gp.Team.eq(team)].copy()
            pos_order={"QB":0,"RB":1,"WR":2,"TE":3,"DST":4}
            tp["_pos_order"]=tp.Position.map(pos_order).fillna(9)
            tp=tp.sort_values(["_pos_order","Salary"],ascending=[True,False])
            trow=ge[ge.Team.eq(team)].iloc[0] if not ge.empty and ge.Team.eq(team).any() else None
            with team_col:
                with st.container(border=True):
                    if trow is not None:
                        team_total=float(trow['Team Total'])
                        team_rank=int(trow['Team Total Rank'])
                        rank_badge="🏆" if team_rank<=3 else ""
                        st.markdown(
                            f"""<div style='display:flex;align-items:center;gap:.55rem;flex-wrap:wrap;margin-bottom:.25rem'>
                            <span style='font-size:1.55rem;font-weight:800;letter-spacing:.01em'>{team}</span>
                            <span style='padding:.18rem .48rem;border:1px solid rgba(250,250,250,.16);border-radius:999px;font-size:.78rem;font-weight:700'>TEAM TOTAL {team_total:.1f}</span>
                            <span style='padding:.18rem .48rem;border:1px solid rgba(250,250,250,.16);border-radius:999px;font-size:.78rem;font-weight:700'>{rank_badge} SLATE RANK #{team_rank}</span>
                            </div>""",
                            unsafe_allow_html=True,
                        )
                    else:
                        st.markdown(f"### {team}")
                    st.caption("Team Action")
                    team_actions[team]=st.selectbox(f"{team} bulk action",["No bulk change","✅ Include all","🚫 Exclude all"],key=f"team_bulk_{str(game)}_{team}_{editor_version}",label_visibility="collapsed")
                    rows=[]
                    for idx,row in tp.iterrows():
                        key=str(row.ID) if str(row.ID) else f"{row.Name}|{row.Team}|{row.Position}|{int(row.Salary)}"
                        cfg=updated_state.get(key,{"include":True,"role":"AUTO","usage":1.0})
                        rows.append({"_row":int(idx),"_key":key,"Include":bool(cfg.get("include",True)),"Pos":row.Position,"Player":row.Name,"Status":str(row.get("Availability","Available")),"Salary":f"${int(row.Salary):,}","Model Role":row.auto_role,"Role":str(cfg.get("role","AUTO")),"Usage x":float(cfg.get("usage",1.0))})
                    edit_df=pd.DataFrame(rows).set_index("_row")
                    all_available=bool(len(edit_df)) and edit_df["Status"].astype(str).str.lower().eq("available").all()
                    visible_cols=["Include","Pos","Player"]
                    disabled_cols=["Pos","Player","Salary","Model Role"]
                    if not all_available:
                        visible_cols.append("Status")
                        disabled_cols.append("Status")
                    visible_cols += ["Salary","Model Role","Role","Usage x"]
                    edited_team=st.data_editor(
                        edit_df.drop(columns=["_key"]),use_container_width=True,hide_index=True,
                        disabled=disabled_cols,
                        column_order=visible_cols,
                        column_config={
                            "Include":st.column_config.CheckboxColumn("In",width="small",help="Include this player in the active SIM pool."),
                            "Pos":st.column_config.TextColumn("Pos",width="small"),
                            "Player":st.column_config.TextColumn("Player",width="medium"),
                            "Status":st.column_config.TextColumn("Status",width="small",help="Automated injury/availability status. Healthy players are hidden from this column to reduce clutter."),
                            "Salary":st.column_config.TextColumn("Salary",width="small"),
                            "Model Role":st.column_config.TextColumn("Model Role",width="small",help="NUKE's automatically inferred depth-chart role."),
                            "Role":st.column_config.SelectboxColumn("Override",options=["AUTO","QB1","RB1","RB2","RB3","WR1","WR2","WR3","TE1","BACKUP"],width="small",help="Optional role override. Leave AUTO to use NUKE's model role."),
                            "Usage x":st.column_config.NumberColumn("Usage",min_value=.25,max_value=2.25,step=.05,format="%.2f",width="small",help="Changes the football simulation itself. Leave at 1.00 unless you believe actual usage changes."),
                        },key=f"game_pool_{str(game)}_{team}_{editor_version}"
                    )
                    pending_by_team[team]=(edit_df,edited_team)
                    excluded_count=sum(not bool(updated_state.get(str(r.ID) if str(r.ID) else f"{r.Name}|{r.Team}|{r.Position}|{int(r.Salary)}",{}).get("include",True)) for _,r in tp.iterrows())
                    if excluded_count:
                        st.caption(f"🚫 {excluded_count} excluded from {team}")
'''

if old not in text:
    raise SystemExit("Expected game pool form block not found; refusing partial patch")
text=text.replace(old,new,1)
path.write_text(text,encoding="utf-8")
print("Polished game-by-game player pool UI")
