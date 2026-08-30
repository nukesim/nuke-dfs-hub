from pathlib import Path

# Portfolio engine: remove duplication from selection scoring/reasons while preserving field popularity as a soft field-shape signal.
p=Path('nuke_portfolio.py'); s=p.read_text(encoding='utf-8')
s=s.replace('field-duplication awareness, elite-lineup protection, and contest-size-aware', 'field-shape awareness, elite-lineup protection, and contest-size-aware')
s=s.replace('    # V3 field information: duplication/popularity is useful portfolio information, not a hard fade.\n    leverage=.34*(-_z(dup))+.18*(-_z(fieldpop)); leverage=np.clip(leverage,-.75,.75)\n    base=base+elite_bonus+leverage\n', '    # NFL main-slate portfolio selection does not optimize for lineup duplication.\n    # Field popularity remains a small field-shape signal without turning this into an ownership fade engine.\n    field_shape=.10*(-_z(fieldpop)); field_shape=np.clip(field_shape,-.30,.30)\n    base=base+elite_bonus+field_shape\n')
s=s.replace('            elif dup[bi] <= np.nanpercentile(dup,30) and first[bi] >= np.nanmedian(first): label="Low-Dup Leverage"\n            elif sc==0: label="Scenario Diversifier"', '            elif sc==0: label="Scenario Diversifier"')
s=s.replace('            reasons[bi]=f"{label} | {path[bi]} | {scenario[bi].split(\' | \')[-1]} | max overlap {worst} | expected dup {dup[bi]:.1f}"', '            reasons[bi]=f"{label} | {path[bi]} | {scenario[bi].split(\' | \')[-1]} | max overlap {worst}"')
p.write_text(s,encoding='utf-8')

# Portfolio Story: remove Low-Dup metric entirely; keep portfolio-vs-field exposure view because that is useful ownership leverage, not duplication.
p=Path('nuke_portfolio_story.py'); s=p.read_text(encoding='utf-8')
s=s.replace('    for label in ["Elite Ceiling","Low-Dup Leverage","Scenario Diversifier","Contrarian QB Path","GPP Upside"]:', '    for label in ["Elite Ceiling","Scenario Diversifier","Contrarian QB Path","GPP Upside"]:')
s=s.replace('    dup=pd.to_numeric(portfolio.get("Duplication Pressure",pd.Series(dtype=float)),errors="coerce").dropna()\n', '')
s=s.replace('    leverage_count=int(reason_df.loc[reason_df["Reason"].eq("Low-Dup Leverage"),"Lineups"].sum()) if not reason_df.empty else 0\n', '')
s=s.replace('        "leverage_lineups":leverage_count,\n', '')
s=s.replace('        "median_dup_pressure":float(dup.median()) if len(dup) else np.nan,\n', '')
p.write_text(s,encoding='utf-8')

# SIM UI: replace the six-card story header with five useful NFL main-slate cards.
p=Path('pages/6_SIM.py'); s=p.read_text(encoding='utf-8')
old='''            s1,s2,s3,s4,s5,s6=st.columns(6)\n            s1.metric("Lineups",f"{int(sm.get('lineups',len(portfolio))):,}")\n            s2.metric("Elite Ceiling",f"{int(sm.get('elite_lineups',0)):,}")\n            s3.metric("Low-Dup Leverage",f"{int(sm.get('leverage_lineups',0)):,}")\n            s4.metric("Top Scenario",str(sm.get('dominant_scenario','UNKNOWN')),delta=f"{float(sm.get('dominant_scenario_pct',0)):.1f}% of portfolio")\n            s5.metric("Top QB",str(sm.get('dominant_qb','UNKNOWN')),delta=f"{float(sm.get('dominant_qb_pct',0)):.1f}% exposure")\n            s6.metric("Top Game",str(sm.get('dominant_game','UNKNOWN')),delta=f"{float(sm.get('dominant_game_pct',0)):.1f}% exposure")\n'''
new='''            s1,s2,s3,s4,s5=st.columns(5)\n            s1.metric("Lineups",f"{int(sm.get('lineups',len(portfolio))):,}")\n            s2.metric("Elite Ceiling",f"{int(sm.get('elite_lineups',0)):,}")\n            s3.metric("Top Scenario",str(sm.get('dominant_scenario','UNKNOWN')),delta=f"{float(sm.get('dominant_scenario_pct',0)):.1f}% of portfolio")\n            s4.metric("Top QB",str(sm.get('dominant_qb','UNKNOWN')),delta=f"{float(sm.get('dominant_qb_pct',0)):.1f}% exposure")\n            s5.metric("Top Game",str(sm.get('dominant_game','UNKNOWN')),delta=f"{float(sm.get('dominant_game_pct',0)):.1f}% exposure")\n'''
if old not in s: raise SystemExit('story metric block not found')
s=s.replace(old,new,1)
p.write_text(s,encoding='utf-8')
print('removed NFL duplication focus')
