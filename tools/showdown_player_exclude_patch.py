from pathlib import Path

page = Path('pages/13_SHOWDOWN_SIM.py')
guide = Path('pages/11_GUIDE.py')

s = page.read_text(encoding='utf-8')
s = s.replace(
'''st.subheader("🎛️ Player Controls")\nst.caption("Boost changes the simulated baseline for that player. Min/Max exposure are enforced in the generated portfolio. Leave 0 / 100 for no player-specific exposure rule.")''',
'''st.subheader("🎛️ Player Controls")\nst.caption("Exclude removes a player from candidate generation entirely. Boost changes the simulated baseline for that player. Min/Max exposure are enforced in the generated portfolio. Leave 0 / 100 for no player-specific exposure rule.")''',
1)
s = s.replace(
'''                "Salary": int(r["FLEX Salary"]),\n                "Boost %": float(cfg.get("boost", 0.0)),''',
'''                "Salary": int(r["FLEX Salary"]),\n                "Exclude": bool(cfg.get("exclude", False)),\n                "Boost %": float(cfg.get("boost", 0.0)),''',
1)
s = s.replace(
'''                "Salary": st.column_config.NumberColumn(flex_label, format="$%d", width="small"),\n                "Boost %": st.column_config.NumberColumn("Boost %", min_value=-50.0, max_value=50.0, step=5.0, format="%.0f%%", width="small", help="Changes this player's simulated baseline before each game outcome is drawn."),''',
'''                "Salary": st.column_config.NumberColumn(flex_label, format="$%d", width="small"),\n                "Exclude": st.column_config.CheckboxColumn("Exclude", width="small", help="Remove this player from all generated Showdown lineups."),\n                "Boost %": st.column_config.NumberColumn("Boost %", min_value=-50.0, max_value=50.0, step=5.0, format="%.0f%%", width="small", help="Changes this player's simulated baseline before each game outcome is drawn."),''',
1)
s = s.replace(
'''            control_state[key] = {"boost": float(er["Boost %"]), "min": mn, "max": mx}\nst.session_state["showdown_player_controls"] = control_state\n\nboosts = {i: float(control_state.get(str(r["Player Key"]), {}).get("boost", 0.0)) for i, r in players.iterrows()}\nplayer_mins = {i: float(control_state.get(str(r["Player Key"]), {}).get("min", 0)) / 100.0 for i, r in players.iterrows()}\nplayer_maxes = {i: float(control_state.get(str(r["Player Key"]), {}).get("max", 100)) / 100.0 for i, r in players.iterrows()}''',
'''            control_state[key] = {"exclude": bool(er["Exclude"]), "boost": float(er["Boost %"]), "min": mn, "max": mx}\nst.session_state["showdown_player_controls"] = control_state\n\nexcluded_keys = {k for k, cfg in control_state.items() if bool((cfg or {}).get("exclude", False))}\nif excluded_keys:\n    players = players[~players["Player Key"].astype(str).isin(excluded_keys)].reset_index(drop=True)\n    st.caption(f"{len(excluded_keys)} player{'s' if len(excluded_keys) != 1 else ''} manually excluded from candidate generation.")\nif len(players) < 6:\n    st.error("Fewer than 6 players remain after exclusions. Re-enable at least enough players to build a legal single-game lineup.")\n    st.stop()\n\nboosts = {i: float(control_state.get(str(r["Player Key"]), {}).get("boost", 0.0)) for i, r in players.iterrows()}\nplayer_mins = {i: float(control_state.get(str(r["Player Key"]), {}).get("min", 0)) / 100.0 for i, r in players.iterrows()}\nplayer_maxes = {i: float(control_state.get(str(r["Player Key"]), {}).get("max", 100)) / 100.0 for i, r in players.iterrows()}''',
1)
page.write_text(s, encoding='utf-8')

g = guide.read_text(encoding='utf-8')
g = g.replace(
'''3. Review the player pool and make any Boost %, Min %, or Max % adjustments.''',
'''3. Review the player pool and make any Exclude, Boost %, Min %, or Max % adjustments.''',
1)
g = g.replace(
'''st.write("**Boost %** changes how strongly NUKE treats a player's baseline opportunity. **Min % / Max %** control portfolio exposure. **Max CPT/MVP exposure** limits how frequently a player can occupy the multiplier position. **Construction Mix** controls the desired team split across 5-1, 4-2, and 3-3 lineups. Salary controls can intentionally leave salary unused to create more differentiated constructions.")''',
'''st.write("**Exclude** removes a player from candidate generation entirely, so that player cannot appear in any generated lineup. Use Exclude when you do not want the player in your portfolio at all. **Boost %** changes how strongly NUKE treats a player's baseline opportunity. **Min % / Max %** control portfolio exposure when the player remains eligible. **Max CPT/MVP exposure** limits how frequently a player can occupy the multiplier position. **Construction Mix** controls the desired team split across 5-1, 4-2, and 3-3 lineups. Salary controls can intentionally leave salary unused to create more differentiated constructions.")''',
1)
g = g.replace(
'''**Showdown workspace:** restores the selected platform, game-specific controls, simulation settings, construction preferences, and completed Showdown results for that game.''',
'''**Showdown workspace:** restores the selected platform, player exclusions, player-level controls, simulation settings, construction preferences, and completed Showdown results for that game.''',
1)
guide.write_text(g, encoding='utf-8')
