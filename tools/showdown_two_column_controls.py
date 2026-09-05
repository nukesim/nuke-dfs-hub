from pathlib import Path

p = Path('pages/13_SHOWDOWN_SIM.py')
s = p.read_text(encoding='utf-8')

s = s.replace('with st.expander("Line movement history", expanded=True):', 'with st.expander("Line movement history", expanded=False):', 1)

old = '''control_state = dict(st.session_state.get("showdown_player_controls", {}) or {})
team_tabs = st.tabs([team_a, team_b])
for tab, team in zip(team_tabs, [team_a, team_b]):
    with tab:
        tp = players[players["Team"].astype(str).eq(team)].copy().reset_index()
        rows = []
        for _, r in tp.iterrows():
            key = str(r["Player Key"])
            cfg = control_state.get(key, {})
            rows.append({
                "_idx": int(r["index"]),
                "Player": r["Name"],
                "Pos": r["Pos"],
                "Salary": int(r["FLEX Salary"]),
                "Boost %": float(cfg.get("boost", 0.0)),
                "Min %": int(cfg.get("min", 0)),
                "Max %": int(cfg.get("max", 100)),
            })
        edit = pd.DataFrame(rows).set_index("_idx")
        edited = st.data_editor(
            edit, use_container_width=True, hide_index=True,
            disabled=["Player", "Pos", "Salary"],
            column_config={
                "Player": st.column_config.TextColumn("Player", width="medium"),
                "Pos": st.column_config.TextColumn("Pos", width="small"),
                "Salary": st.column_config.NumberColumn("FLEX Salary", format="$%d", width="small"),
                "Boost %": st.column_config.NumberColumn("Boost %", min_value=-50.0, max_value=50.0, step=5.0, format="%.0f%%", width="small", help="Changes this player's simulated baseline before each game outcome is drawn."),
                "Min %": st.column_config.NumberColumn("Min %", min_value=0, max_value=100, step=5, format="%d%%", width="small"),
                "Max %": st.column_config.NumberColumn("Max %", min_value=0, max_value=100, step=5, format="%d%%", width="small"),
            },
            key=f"showdown_controls_{team}_{slate_sig}",
        )
        for idx, er in edited.iterrows():
            key = str(players.iloc[int(idx)]["Player Key"])
            mn = int(er["Min %"]); mx = int(er["Max %"])
            if mn > mx:
                mn = mx
            control_state[key] = {"boost": float(er["Boost %"]), "min": mn, "max": mx}
'''

new = '''control_state = dict(st.session_state.get("showdown_player_controls", {}) or {})
team_columns = st.columns(2)
for col, team in zip(team_columns, [team_a, team_b]):
    with col:
        st.markdown(f"#### {team}")
        tp = players[players["Team"].astype(str).eq(team)].copy().reset_index()
        rows = []
        for _, r in tp.iterrows():
            key = str(r["Player Key"])
            cfg = control_state.get(key, {})
            rows.append({
                "_idx": int(r["index"]),
                "Player": r["Name"],
                "Pos": r["Pos"],
                "Salary": int(r["FLEX Salary"]),
                "Boost %": float(cfg.get("boost", 0.0)),
                "Min %": int(cfg.get("min", 0)),
                "Max %": int(cfg.get("max", 100)),
            })
        edit = pd.DataFrame(rows).set_index("_idx")
        edited = st.data_editor(
            edit,
            use_container_width=True,
            hide_index=True,
            disabled=["Player", "Pos", "Salary"],
            column_config={
                "Player": st.column_config.TextColumn("Player", width="medium"),
                "Pos": st.column_config.TextColumn("Pos", width="small"),
                "Salary": st.column_config.NumberColumn("FLEX", format="$%d", width="small"),
                "Boost %": st.column_config.NumberColumn("Boost %", min_value=-50.0, max_value=50.0, step=5.0, format="%.0f%%", width="small", help="Changes this player's simulated baseline before each game outcome is drawn."),
                "Min %": st.column_config.NumberColumn("Min %", min_value=0, max_value=100, step=5, format="%d%%", width="small"),
                "Max %": st.column_config.NumberColumn("Max %", min_value=0, max_value=100, step=5, format="%d%%", width="small"),
            },
            key=f"showdown_controls_{team}_{slate_sig}",
        )
        for idx, er in edited.iterrows():
            key = str(players.iloc[int(idx)]["Player Key"])
            mn = int(er["Min %"]); mx = int(er["Max %"])
            if mn > mx:
                mn = mx
            control_state[key] = {"boost": float(er["Boost %"]), "min": mn, "max": mx}
'''

if old not in s:
    raise SystemExit('player controls block not found')
s = s.replace(old, new, 1)

p.write_text(s, encoding='utf-8')
print('patched Showdown team controls to two columns and collapsed line movement')
