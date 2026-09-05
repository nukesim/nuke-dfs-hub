from pathlib import Path

page = Path('pages/13_SHOWDOWN_SIM.py')
sim = Path('nuke_showdown_sim.py')
ps = page.read_text(encoding='utf-8')
ss = sim.read_text(encoding='utf-8')

# --- page imports/constants ---
ps = ps.replace(
    'DEFAULT_SHOWDOWN_CSV = Path(__file__).resolve().parents[1] / "data" / "showdown_current.csv"\n',
    'DEFAULT_SHOWDOWN_CSV = Path(__file__).resolve().parents[1] / "data" / "showdown_current.csv"\n'
    'ODDS_CURRENT_CSV = Path(__file__).resolve().parents[1] / "data" / "nfl_odds_current.csv"\n'
    'ODDS_HISTORY_CSV = Path(__file__).resolve().parents[1] / "data" / "nfl_odds_history.csv"\n',
    1,
)

# clear per-slate player controls
ps = ps.replace(
    '        "showdown_sim_scripts", "showdown_sim_seed",\n',
    '        "showdown_sim_scripts", "showdown_sim_seed", "showdown_player_controls",\n',
    1,
)

# Insert sportsbook + line movement after metric row.
anchor = 'm4.metric("Cap", "$50,000")\n\nwith st.expander("Simulation Settings", expanded=True):\n'
insert = '''m4.metric("Cap", "$50,000")\n\nst.subheader("📈 Sportsbook & Line Movement")\nodds_now = pd.DataFrame()\nodds_hist = pd.DataFrame()\ntry:\n    if ODDS_CURRENT_CSV.exists():\n        odds_now = pd.read_csv(ODDS_CURRENT_CSV)\n        odds_now = odds_now[odds_now["Team"].astype(str).isin([team_a, team_b])].copy()\n        if not odds_now.empty:\n            event_ids = odds_now["Event ID"].dropna().astype(str).unique().tolist()\n            if event_ids:\n                odds_now = odds_now[odds_now["Event ID"].astype(str).eq(event_ids[0])].copy()\n    if ODDS_HISTORY_CSV.exists() and not odds_now.empty:\n        odds_hist = pd.read_csv(ODDS_HISTORY_CSV)\n        eid = str(odds_now.iloc[0]["Event ID"])\n        odds_hist = odds_hist[odds_hist["Event ID"].astype(str).eq(eid)].copy()\nexcept Exception:\n    odds_now = pd.DataFrame()\n    odds_hist = pd.DataFrame()\n\nif odds_now.empty:\n    st.info("Sportsbook consensus is not available for this game yet.")\nelse:\n    odds_now = odds_now.sort_values("Team")\n    game_total = float(odds_now["Game Total"].dropna().iloc[0]) if odds_now["Game Total"].notna().any() else None\n    book_count = int(odds_now["Book Count"].max()) if "Book Count" in odds_now.columns else 0\n    snapshot = str(odds_now["Snapshot UTC"].max()) if "Snapshot UTC" in odds_now.columns else ""\n    o1, o2, o3 = st.columns(3)\n    o1.metric("Game Total", f"{game_total:.1f}" if game_total is not None else "—")\n    for col, team in zip([o2, o3], [team_a, team_b]):\n        r = odds_now[odds_now["Team"].astype(str).eq(team)]\n        if not r.empty:\n            rr = r.iloc[0]\n            spread = float(rr.get("Spread", 0) or 0)\n            tt = float(rr.get("Team Total", 0) or 0)\n            col.metric(f"{team} · Team Total", f"{tt:.1f}", delta=f"Spread {spread:+.1f}")\n    books = str(odds_now.iloc[0].get("Books", ""))\n    st.caption(f"Consensus across {book_count} sportsbooks · Latest snapshot: {snapshot}" + (f" · {books}" if books else ""))\n\n    if not odds_hist.empty:\n        odds_hist["Snapshot UTC"] = pd.to_datetime(odds_hist["Snapshot UTC"], errors="coerce", utc=True)\n        odds_hist = odds_hist.dropna(subset=["Snapshot UTC"]).sort_values("Snapshot UTC")\n        first = odds_hist.groupby("Team", as_index=False).first()\n        last = odds_hist.groupby("Team", as_index=False).last()\n        with st.expander("Line movement history", expanded=True):\n            mov_rows = []\n            for team in [team_a, team_b]:\n                a = first[first["Team"].astype(str).eq(team)]\n                b = last[last["Team"].astype(str).eq(team)]\n                if not a.empty and not b.empty:\n                    mov_rows.append({\n                        "Team": team,\n                        "Open Spread": float(a.iloc[0]["Spread"]),\n                        "Current Spread": float(b.iloc[0]["Spread"]),\n                        "Spread Move": float(b.iloc[0]["Spread"] - a.iloc[0]["Spread"]),\n                        "Open Team Total": float(a.iloc[0]["Team Total"]),\n                        "Current Team Total": float(b.iloc[0]["Team Total"]),\n                        "Team Total Move": float(b.iloc[0]["Team Total"] - a.iloc[0]["Team Total"]),\n                    })\n            if mov_rows:\n                st.dataframe(pd.DataFrame(mov_rows), use_container_width=True, hide_index=True)\n            chart = odds_hist.pivot_table(index="Snapshot UTC", columns="Team", values="Team Total", aggfunc="last")\n            if not chart.empty:\n                st.caption("Team total movement")\n                st.line_chart(chart, use_container_width=True)\n            gt = odds_hist.drop_duplicates("Snapshot UTC").set_index("Snapshot UTC")[["Game Total"]]\n            if not gt.empty:\n                st.caption("Game total movement")\n                st.line_chart(gt, use_container_width=True)\n\nst.subheader("🎛️ Player Controls")\nst.caption("Boost changes the simulated baseline for that player. Min/Max exposure are enforced in the generated portfolio. Leave 0 / 100 for no player-specific exposure rule.")\ncontrol_state = dict(st.session_state.get("showdown_player_controls", {}) or {})\nteam_tabs = st.tabs([team_a, team_b])\nfor tab, team in zip(team_tabs, [team_a, team_b]):\n    with tab:\n        tp = players[players["Team"].astype(str).eq(team)].copy().reset_index()\n        rows = []\n        for _, r in tp.iterrows():\n            key = str(r["Player Key"])\n            cfg = control_state.get(key, {})\n            rows.append({\n                "_idx": int(r["index"]),\n                "Player": r["Name"],\n                "Pos": r["Pos"],\n                "Salary": int(r["FLEX Salary"]),\n                "Boost %": float(cfg.get("boost", 0.0)),\n                "Min %": int(cfg.get("min", 0)),\n                "Max %": int(cfg.get("max", 100)),\n            })\n        edit = pd.DataFrame(rows).set_index("_idx")\n        edited = st.data_editor(\n            edit, use_container_width=True, hide_index=True,\n            disabled=["Player", "Pos", "Salary"],\n            column_config={\n                "Player": st.column_config.TextColumn("Player", width="medium"),\n                "Pos": st.column_config.TextColumn("Pos", width="small"),\n                "Salary": st.column_config.NumberColumn("FLEX Salary", format="$%d", width="small"),\n                "Boost %": st.column_config.NumberColumn("Boost %", min_value=-50.0, max_value=50.0, step=5.0, format="%.0f%%", width="small", help="Changes this player's simulated baseline before each game outcome is drawn."),\n                "Min %": st.column_config.NumberColumn("Min %", min_value=0, max_value=100, step=5, format="%d%%", width="small"),\n                "Max %": st.column_config.NumberColumn("Max %", min_value=0, max_value=100, step=5, format="%d%%", width="small"),\n            },\n            key=f"showdown_controls_{team}_{slate_sig}",\n        )\n        for idx, er in edited.iterrows():\n            key = str(players.iloc[int(idx)]["Player Key"])\n            mn = int(er["Min %"]); mx = int(er["Max %"])\n            if mn > mx:\n                mn = mx\n            control_state[key] = {"boost": float(er["Boost %"]), "min": mn, "max": mx}\nst.session_state["showdown_player_controls"] = control_state\n\nboosts = {i: float(control_state.get(str(r["Player Key"]), {}).get("boost", 0.0)) for i, r in players.iterrows()}\nplayer_mins = {i: float(control_state.get(str(r["Player Key"]), {}).get("min", 0)) / 100.0 for i, r in players.iterrows()}\nplayer_maxes = {i: float(control_state.get(str(r["Player Key"]), {}).get("max", 100)) / 100.0 for i, r in players.iterrows()}\n\nwith st.expander("Simulation Settings", expanded=True):\n'''
if anchor not in ps:
    raise SystemExit('page metric/settings anchor not found')
ps = ps.replace(anchor, insert, 1)

ps = ps.replace(
    'players, meta["teams"], n_sims=n_sims, seed=seed\n        )',
    'players, meta["teams"], n_sims=n_sims, seed=seed, boosts=boosts\n        )',
    1,
)
ps = ps.replace(
    'max_player_pct=max_player, max_cpt_pct=max_cpt,\n        )',
    'max_player_pct=max_player, max_cpt_pct=max_cpt,\n            player_mins=player_mins, player_maxes=player_maxes,\n        )',
    1,
)

# --- sim engine: boost support ---
ss = ss.replace(
    'def simulate_player_outcomes(players, teams, n_sims=5000, seed=26):',
    'def simulate_player_outcomes(players, teams, n_sims=5000, seed=26, boosts=None):',
    1,
)
ss = ss.replace(
    '    base = np.array([_base_projection(r) for _, r in players.iterrows()], dtype=float)\n',
    '    base = np.array([_base_projection(r) for _, r in players.iterrows()], dtype=float)\n'
    '    boosts = boosts or {}\n'
    '    for i in range(len(base)):\n'
    '        base[i] *= max(0.05, 1.0 + float(boosts.get(i, 0.0)) / 100.0)\n',
    1,
)

# replace portfolio builder with per-player min/max aware greedy selection
start = ss.index('def build_portfolio(')
end = ss.index('\ndef exposure_table(', start)
new_builder = '''def build_portfolio(results, players, count=20, max_player_pct=.75, max_cpt_pct=.35, player_mins=None, player_maxes=None):\n    if results.empty:\n        return results\n    target = max(1, int(count))\n    player_mins = player_mins or {}\n    player_maxes = player_maxes or {}\n    global_player_max = max(1, int(np.floor(target * float(max_player_pct) + 1e-9)))\n    global_cpt_max = max(1, int(np.floor(target * float(max_cpt_pct) + 1e-9)))\n    min_counts = {i: int(np.ceil(target * max(0.0, min(1.0, float(player_mins.get(i, 0.0)))))) for i in range(len(players))}\n    max_counts = {}\n    for i in range(len(players)):\n        personal = max(0.0, min(1.0, float(player_maxes.get(i, 1.0))))\n        personal_count = int(np.floor(target * personal + 1e-9))\n        max_counts[i] = min(global_player_max, personal_count)\n    player_counts = Counter()\n    cpt_counts = Counter()\n    chosen = []\n    used = set()\n    band = results.head(min(len(results), 6000)).reset_index(drop=True)\n\n    for _ in range(target):\n        best_idx = None\n        best_value = None\n        for ridx, r in band.iterrows():\n            if ridx in used:\n                continue\n            cpt = int(r["_cpt"])\n            inds = [cpt] + list(map(int, r["_flex"]))\n            if cpt_counts[cpt] >= global_cpt_max:\n                continue\n            if any(player_counts[i] >= max_counts.get(i, global_player_max) for i in inds):\n                continue\n            deficit_bonus = 0.0\n            for i in inds:\n                need = max(0, min_counts.get(i, 0) - player_counts[i])\n                deficit_bonus += need * 1000.0\n            value = deficit_bonus + float(r.get("NUKE Score", 0.0))\n            if best_value is None or value > best_value:\n                best_value = value\n                best_idx = ridx\n        if best_idx is None:\n            break\n        r = band.iloc[best_idx]\n        cpt = int(r["_cpt"]); inds = [cpt] + list(map(int, r["_flex"]))\n        chosen.append(r)\n        used.add(best_idx)\n        cpt_counts[cpt] += 1\n        player_counts.update(inds)\n\n    return pd.DataFrame(chosen).reset_index(drop=True) if chosen else results.iloc[0:0].copy()\n\n'''
ss = ss[:start] + new_builder + ss[end+1:]

page.write_text(ps, encoding='utf-8')
sim.write_text(ss, encoding='utf-8')
print('patched Showdown odds, movement, boosts, min/max exposure')
