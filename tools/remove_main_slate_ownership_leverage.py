from pathlib import Path

# Remove the modeled-field ownership comparison UI and wording from main-slate NUKE SIM.
p = Path('pages/6_SIM.py')
s = p.read_text()
s = s.replace(
'            st.caption("What this portfolio is betting on, where it is different from the modeled field, and where concentration risk lives.")',
'            st.caption("What this portfolio is betting on, why lineups earned portfolio slots, and where concentration risk lives.")'
)
block = '''            leverage_df=story.get("leverage_df",pd.DataFrame())\n            if leverage_df is not None and not leverage_df.empty:\n                st.markdown("#### ⚡ Portfolio vs Modeled Field")\n                st.caption("Positive leverage = NUKE is using the player more than the projection-free Field Engine ownership prior. Negative leverage = portfolio fade. This is a portfolio stance, not a live ownership projection.")\n                lev1,lev2=st.columns(2)\n                with lev1:\n                    st.markdown("**Largest Overweights**")\n                    st.dataframe(leverage_df.head(12),use_container_width=True,hide_index=True,height=390)\n                with lev2:\n                    st.markdown("**Largest Underweights / Fades**")\n                    st.dataframe(leverage_df.sort_values("Leverage +/-",ascending=True).head(12),use_container_width=True,hide_index=True,height=390)\n\n'''
s = s.replace(block, '')
needle='            st.markdown("#### 🚨 Portfolio Risk Check")\n'
if needle in s and 'simulation quality, scenario coverage' not in s:
    s=s.replace(needle, '            st.caption("Portfolio selection is driven by simulation quality, scenario coverage, correlation, exposure limits, and diversification — not modeled ownership estimates.")\n            st.markdown("#### 🚨 Portfolio Risk Check")\n')
p.write_text(s)

# Remove ownership/duplication leverage from portfolio selection and labels.
p = Path('nuke_portfolio.py')
s = p.read_text()
s = s.replace(
'    # V3 field information: duplication/popularity is useful portfolio information, not a hard fade.\n    leverage=.34*(-_z(dup))+.18*(-_z(fieldpop)); leverage=np.clip(leverage,-.75,.75)\n    base=base+elite_bonus+leverage\n',
'    # Main-slate portfolio selection intentionally does not use modeled ownership or duplication estimates.\n    # Candidate quality, simulated tournament outcomes, correlation and portfolio diversification drive selection.\n    base=base+elite_bonus\n'
)
s = s.replace(
'            elif dup[bi] <= np.nanpercentile(dup,30) and first[bi] >= np.nanmedian(first): label="Low-Dup Leverage"\n            elif sc==0: label="Scenario Diversifier"\n',
'            elif sc==0: label="Scenario Diversifier"\n'
)
s = s.replace(
'            reasons[bi]=f"{label} | {path[bi]} | {scenario[bi].split(\' | \')[-1]} | max overlap {worst} | expected dup {dup[bi]:.1f}"\n',
'            reasons[bi]=f"{label} | {path[bi]} | {scenario[bi].split(\' | \')[-1]} | max overlap {worst}"\n'
)
p.write_text(s)

# Stop calculating modeled ownership comparison tables for Portfolio Story.
p = Path('nuke_portfolio_story.py')
s = p.read_text()
s = s.replace('from nuke_field import projection_free_player_ownership\n', '')
start = s.find('    pexp=portfolio_player_exposure(players,portfolio)\n    field=projection_free_player_ownership(players)\n')
end = s.find('    qb_df=portfolio_qb_exposure(portfolio)\n', start)
if start != -1 and end != -1:
    s = s[:start] + '    leverage_df=pd.DataFrame()\n\n' + s[end:]
s = s.replace('    dup=pd.to_numeric(portfolio.get("Duplication Pressure",pd.Series(dtype=float)),errors="coerce").dropna()\n', '')
s = s.replace('        "median_dup_pressure":float(dup.median()) if len(dup) else np.nan,\n', '')
p.write_text(s)
