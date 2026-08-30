from pathlib import Path

p=Path('pages/6_SIM.py')
s=p.read_text()
start=s.index('for game in players.Game.drop_duplicates().tolist():')
end=s.index('st.session_state["nuke_pregame_pool"]=updated_state', start)

new='''for game in players.Game.drop_duplicates().tolist():
    gp=players[players.Game.eq(game)].copy()
    teams=list(dict.fromkeys(gp.Team.astype(str).tolist()))
    label=" vs ".join(teams[:2]) if len(teams)>=2 else str(game)

    with st.expander(f"🏈 {label}",expanded=False):
        ge=env[env.Game.eq(str(game))].copy() if not env.empty else pd.DataFrame()
        if not ge.empty:
            env_show=ge[["Team","Opponent","Team Total","Team Total Rank","Game Total","Game Total Rank"]]
            st.dataframe(style_environment(env_show),use_container_width=True,hide_index=True)

        st.caption("Make as many player changes as you want, then click Apply changes once. Nothing reloads while you are checking/unchecking names.")
        with st.form(key=f"pool_form_{str(game)}_{editor_version}",clear_on_submit=False):
            game_action=st.selectbox("Game bulk action",["No bulk change","✅ Include entire game","🚫 Exclude entire game"],key=f"game_bulk_{str(game)}_{editor_version}")
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
                rows=[]
                for idx,row in tp.iterrows():
                    key=str(row.ID) if str(row.ID) else f"{row.Name}|{row.Team}|{row.Position}|{int(row.Salary)}"
                    cfg=updated_state.get(key,{"include":True,"boost":0.0,"role":"AUTO","usage":1.0})
                    rows.append({"_row":int(idx),"_key":key,"Include":bool(cfg.get("include",True)),"Pos":row.Position,"Player":row.Name,"Salary":int(row.Salary),"Auto Role":row.auto_role,"Boost":float(cfg.get("boost",0.0)),"Role":str(cfg.get("role","AUTO")),"Usage x":float(cfg.get("usage",1.0))})
                edit_df=pd.DataFrame(rows).set_index("_row")

                with team_col:
                    if trow is not None:
                        st.markdown(f"### {team} · {float(trow['Team Total']):.1f} · Rank #{int(trow['Team Total Rank'])}")
                    else:
                        st.markdown(f"### {team}")
                    team_actions[team]=st.selectbox(f"{team} bulk action",["No bulk change","✅ Include all","🚫 Exclude all"],key=f"team_bulk_{str(game)}_{team}_{editor_version}",label_visibility="collapsed")
                    edited_team=st.data_editor(
                        edit_df.drop(columns=["_key"]),use_container_width=True,hide_index=True,
                        disabled=["Pos","Player","Salary","Auto Role"],
                        column_order=["Include","Pos","Player","Salary","Auto Role","Boost","Role","Usage x"],
                        column_config={
                            "Include":st.column_config.CheckboxColumn("Include",width="small"),
                            "Pos":st.column_config.TextColumn("Pos",width="small"),
                            "Player":st.column_config.TextColumn("Player",width="medium"),
                            "Salary":st.column_config.NumberColumn("Salary",format="$%d",width="small"),
                            "Auto Role":st.column_config.TextColumn("Auto Role",width="small"),
                            "Boost":st.column_config.NumberColumn("Boost",min_value=-3.0,max_value=3.0,step=1.0,format="%.0f",width="small",help="Personal preference only. Changes candidate generation, not simulated fantasy points."),
                            "Role":st.column_config.SelectboxColumn("Role",options=["AUTO","QB1","RB1","RB2","RB3","WR1","WR2","WR3","TE1","BACKUP"],width="small"),
                            "Usage x":st.column_config.NumberColumn("Usage x",min_value=.25,max_value=2.25,step=.05,format="%.2f",width="small",help="Changes the football simulation itself. Leave at 1.00 unless you believe actual usage changes."),
                        },key=f"game_pool_{str(game)}_{team}_{editor_version}")
                    pending_by_team[team]=(edit_df,edited_team)
                    excluded_count=sum(not bool(updated_state.get(str(r.ID) if str(r.ID) else f"{r.Name}|{r.Team}|{r.Position}|{int(r.Salary)}",{}).get("include",True)) for _,r in tp.iterrows())
                    if excluded_count:
                        st.caption(f"🚫 Currently excluded: {excluded_count} · They stay visible here until you Apply changes, so you can re-check several at once.")

            apply_changes=st.form_submit_button(f"Apply changes for {label}",type="primary",use_container_width=True)

        if apply_changes:
            for team,(edit_df,edited_team) in pending_by_team.items():
                action=team_actions.get(team,"No bulk change")
                for idx,erow in edited_team.iterrows():
                    key=str(edit_df.loc[idx,"_key"])
                    include=bool(erow["Include"])
                    if action=="✅ Include all": include=True
                    elif action=="🚫 Exclude all": include=False
                    if game_action=="✅ Include entire game": include=True
                    elif game_action=="🚫 Exclude entire game": include=False
                    updated_state[key]={"include":include,"boost":float(erow["Boost"]),"role":str(erow["Role"]),"usage":float(erow["Usage x"])}
            st.session_state["nuke_pregame_pool"]=updated_state
            st.session_state["nuke_pool_editor_version"]=editor_version+1
            st.rerun()

'''

p.write_text(s[:start]+new+s[end:])
