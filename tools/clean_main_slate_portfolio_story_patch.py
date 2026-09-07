from pathlib import Path

# Portfolio story: collapse legacy Low-Dup labels into GPP Upside and show only the
# actual path name in Top Scenario (QB and game already have their own metrics).
p = Path('nuke_portfolio_story.py')
s = p.read_text()
s = s.replace(
'''def _reason_bucket(value):
    s=str(value or "")
    for label in ["Elite Ceiling","Low-Dup Leverage","Scenario Diversifier","Contrarian QB Path","GPP Upside"]:
        if label.lower() in s.lower():
            return label
    return "Other"
''',
'''def _reason_bucket(value):
    s=str(value or "")
    if "low-dup leverage" in s.lower():
        return "GPP Upside"
    for label in ["Elite Ceiling","Scenario Diversifier","Contrarian QB Path","GPP Upside"]:
        if label.lower() in s.lower():
            return label
    return "Other"
'''
)
s = s.replace(
'    dominant_scenario=str(scenario_df.iloc[0]["Scenario"]) if not scenario_df.empty else "UNKNOWN"\n',
'    dominant_scenario=str(scenario_df.iloc[0]["Scenario"]).split("|")[0].strip() if not scenario_df.empty else "UNKNOWN"\n'
)
p.write_text(s)

# Main NUKE SIM UI: five compact story metrics instead of six, removing the
# low-duplication metric and giving the scenario/QB/game cards more width.
p = Path('pages/6_SIM.py')
s = p.read_text()
old='''            s1,s2,s3,s4,s5,s6=st.columns(6)
            s1.metric("Lineups",f"{int(sm.get('lineups',len(portfolio))):,}")
            s2.metric("Elite Ceiling",f"{int(sm.get('elite_lineups',0)):,}")
            s3.metric("Low-Dup Leverage",f"{int(sm.get('leverage_lineups',0)):,}")
            s4.metric("Top Scenario",str(sm.get('dominant_scenario','UNKNOWN')),delta=f"{float(sm.get('dominant_scenario_pct',0)):.1f}% of portfolio")
            s5.metric("Top QB",str(sm.get('dominant_qb','UNKNOWN')),delta=f"{float(sm.get('dominant_qb_pct',0)):.1f}% exposure")
            s6.metric("Top Game",str(sm.get('dominant_game','UNKNOWN')),delta=f"{float(sm.get('dominant_game_pct',0)):.1f}% exposure")
'''
new='''            s1,s2,s3,s4,s5=st.columns([0.85,1.0,1.35,1.15,1.15])
            s1.metric("Lineups",f"{int(sm.get('lineups',len(portfolio))):,}")
            s2.metric("Elite Ceiling",f"{int(sm.get('elite_lineups',0)):,}")
            s3.metric("Top Scenario",str(sm.get('dominant_scenario','UNKNOWN')),delta=f"{float(sm.get('dominant_scenario_pct',0)):.1f}% of portfolio")
            s4.metric("Top QB",str(sm.get('dominant_qb','UNKNOWN')),delta=f"{float(sm.get('dominant_qb_pct',0)):.1f}% exposure")
            s5.metric("Top Game",str(sm.get('dominant_game','UNKNOWN')),delta=f"{float(sm.get('dominant_game_pct',0)):.1f}% exposure")
'''
if old not in s:
    raise SystemExit('Portfolio Story metric block not found')
s = s.replace(old,new)
p.write_text(s)
