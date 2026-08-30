from pathlib import Path

p=Path('pages/6_SIM.py')
s=p.read_text(encoding='utf-8')

old='from nuke_game_pool import game_environment, style_environment\n'
new='from nuke_game_pool import game_environment, style_environment\nfrom nuke_odds import load_current_odds, load_odds_history, odds_status, movement_for_game\n'
if new not in s:
    if old not in s: raise SystemExit('import anchor not found')
    s=s.replace(old,new,1)

old='st.subheader("🎮 Game-by-Game Player Pool")\nst.caption("Work the slate one game at a time. Include/remove players, adjust role if needed, then apply the game once.")\nenv=game_environment(players)\nif not env.empty:\n    st.caption("Team/Game totals below are projection-free DK salary-market estimates until a live sportsbook feed is connected. Rank 1 = strongest on the slate.")\n'
new='''st.subheader("🎮 Game-by-Game Player Pool")\nst.caption("Work the slate one game at a time. Include/remove players, adjust role if needed, then apply the game once.")\ncurrent_odds=load_current_odds()\nodds_history=load_odds_history()\nodds_meta=odds_status(current_odds)\nenv=game_environment(players,current_odds)\nif not env.empty:\n    sportsbook_games=int(env[env["Source"].eq("Sportsbook Consensus")]["Game"].nunique()) if "Source" in env.columns else 0\n    if sportsbook_games:\n        rem=odds_meta.get("credits_remaining")\n        rem_text=f" · {rem} free API credits remaining" if rem is not None else ""\n        st.caption(f"Sportsbook consensus is live for {sportsbook_games} slate games. Team totals are implied from consensus spread + game total. Auto-updated throughout the week{rem_text}. Rank 1 = strongest on the slate.")\n    else:\n        st.caption("Sportsbook lines are not loaded yet, so NUKE is temporarily using its DK salary-market estimates. Rank 1 = strongest on the slate.")\n'''
if old in s:
    s=s.replace(old,new,1)
elif 'current_odds=load_current_odds()' not in s:
    raise SystemExit('environment anchor not found')

old='''    if not ge.empty:\n        env_show=ge[["Team","Opponent","Team Total","Team Total Rank","Game Total","Game Total Rank"]]\n        st.dataframe(style_environment(env_show),use_container_width=True,hide_index=True)\n    st.caption("Only this game's controls are loaded. Make as many changes as you want, then click Apply changes once.")\n'''
new='''    if not ge.empty:\n        env_cols=["Team","Opponent","Spread","Team Total","Team Total Rank","Game Total","Game Total Rank","Books","Source"]\n        env_show=ge[[c for c in env_cols if c in ge.columns]]\n        st.dataframe(style_environment(env_show),use_container_width=True,hide_index=True)\n        book_rows=ge[ge["Source"].eq("Sportsbook Consensus")] if "Source" in ge.columns else pd.DataFrame()\n        if not book_rows.empty:\n            last_update=str(book_rows.iloc[0].get("Last Update",""))\n            st.caption(f"Consensus across {int(book_rows['Books'].max()) if 'Books' in book_rows.columns else 0} US sportsbooks · Last odds snapshot: {last_update}")\n            movement=movement_for_game(odds_history,teams)\n            if not movement.empty:\n                with st.expander("📈 Odds movement this week",expanded=False):\n                    chart_cols=[c for c in ["Game Total",f"{teams[0]} Team Total",f"{teams[1]} Team Total"] if c in movement.columns]\n                    if chart_cols:\n                        chart_df=movement[["Timestamp"]+chart_cols].copy().set_index("Timestamp")\n                        st.line_chart(chart_df,use_container_width=True)\n                    first,last=movement.iloc[0],movement.iloc[-1]\n                    m1,m2,m3=st.columns(3)\n                    gt0=float(first.get("Game Total",0)); gt1=float(last.get("Game Total",0))\n                    a_col=f"{teams[0]} Team Total"; b_col=f"{teams[1]} Team Total"\n                    a0=float(first.get(a_col,0)); a1=float(last.get(a_col,0)); b0=float(first.get(b_col,0)); b1=float(last.get(b_col,0))\n                    m1.metric("Game Total",f"{gt1:.1f}",delta=f"{gt1-gt0:+.1f} vs first snapshot")\n                    m2.metric(f"{teams[0]} Team Total",f"{a1:.1f}",delta=f"{a1-a0:+.1f}")\n                    m3.metric(f"{teams[1]} Team Total",f"{b1:.1f}",delta=f"{b1-b0:+.1f}")\n                    spread_cols=[c for c in [f"{teams[0]} Spread",f"{teams[1]} Spread"] if c in movement.columns]\n                    if spread_cols:\n                        st.caption("Spread movement")\n                        st.line_chart(movement[["Timestamp"]+spread_cols].set_index("Timestamp"),use_container_width=True)\n    st.caption("Only this game's controls are loaded. Make as many changes as you want, then click Apply changes once.")\n'''
if old in s:
    s=s.replace(old,new,1)
elif 'Odds movement this week' not in s:
    raise SystemExit('game display anchor not found')

p.write_text(s,encoding='utf-8')
